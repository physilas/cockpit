"""Process-isolated CPU games with batched CPU/Metal PPO updates in the parent.

Only permitted observations reach the policy. Each process owns its engine RNG;
no threads share the engine's global random module. Training seeds are namespaced
separately from deterministic validation and final-test seeds.
"""
from concurrent.futures import ProcessPoolExecutor
import multiprocessing

import torch

from .agents import HeuristicAgent, ModelAgent
from .environment import CrewEnv
from .evaluate import evaluate, summarize_episodes
from .nn_model import ActorCritic

_model = None
_env_options = None


def _initialize(model_config, env_options):
    global _model, _env_options
    torch.set_num_threads(1)
    _model = ActorCritic(**model_config)
    _env_options = env_options


def _collect(task):
    from .train import collect_rollout
    state, steps, namespace, torch_seed, gamma, gae_lambda, uniform_mix, discount_unit, ai_role = task
    _model.load_state_dict(state)
    torch.manual_seed(torch_seed)
    env = CrewEnv(**_env_options)
    return collect_rollout(_model, env, steps, seed=namespace, episodes_done=0,
        gamma=gamma, gae_lambda=gae_lambda, uniform_mix=uniform_mix, discount_unit=discount_unit,
        partner=HeuristicAgent() if ai_role else None, ai_role=ai_role or 'both')


def _evaluate(task):
    state, games, seed = task
    _model.load_state_dict(state)
    return evaluate(ModelAgent(_model), games=games, seed=seed, **_env_options)['episodes']


class ParallelGames:
    def __init__(self, workers, model_config, env_options):
        self.workers = workers
        self.pool = ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context('spawn'),
            initializer=_initialize, initargs=(model_config, env_options))

    def collect(self, model, steps, *, seed, update, gamma, gae_lambda, uniform_mix, discount_unit, partner_fraction=0.0):
        state = {k: v.detach().cpu() for k, v in model.state_dict().items()}
        count = min(self.workers, max(1, steps))
        tasks = []
        for i in range(count):
            ai_role = ('pilot', 'kopilot')[(update + i) % 2] if (update * count + i) % 100 < round(100 * partner_fraction) else None
            # Evenly interleave partner batches instead of grouping the first 25.
            if partner_fraction:
                period = max(1, round(1 / partner_fraction))
                ai_role = ('pilot', 'kopilot')[(update // period + i) % 2] if (update + i) % period == 0 else None
            tasks.append((state, (steps + count - 1) // count, f'parallel:{seed}:{update}:{i}',
                          seed + update * 1009 + i, gamma, gae_lambda, uniform_mix, discount_unit, ai_role))
        outputs = list(self.pool.map(_collect, tasks))
        device = next(model.parameters()).device
        batch = {k: torch.cat([o[0][k] for o in outputs]).to(device) for k in outputs[0][0]}
        return batch, [r for _, records in outputs for r in records]

    def evaluate(self, model, *, games, seed):
        state = {k: v.detach().cpu() for k, v in model.state_dict().items()}
        tasks, offset = [], 0
        for i in range(min(self.workers, games)):
            n = games // self.workers + int(i < games % self.workers) if games >= self.workers else 1
            tasks.append((state, n, seed + offset))
            offset += n
        records = [r for group in self.pool.map(_evaluate, tasks) for r in group]
        return summarize_episodes(records)

    def close(self):
        self.pool.shutdown(wait=True, cancel_futures=True)
