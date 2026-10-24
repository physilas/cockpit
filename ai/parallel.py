"""Process-isolated CPU games with batched CPU/Metal PPO updates in the parent.

Only permitted observations reach the policy. Each process owns its engine RNG;
no threads share the engine's global random module. Training seeds are namespaced
separately from deterministic validation and final-test seeds.
"""
from concurrent.futures import ProcessPoolExecutor
import math
import multiprocessing

import torch

from .agents import HeuristicAgent, ModelAgent
from .environment import CrewEnv
from .evaluate import evaluate, summarize_episodes
from .nn_model import ActorCritic
from .partners import make_partner

_model = None
_env_options = None
_partners = None
_cpu_duty_cycle = 1


def partner_assignment(ordinal, fraction, count):
    before, after = math.floor(ordinal*fraction), math.floor((ordinal+1)*fraction)
    if after == before:
        return None, None
    return (after-1) % count, ('pilot','kopilot')[((after-1)//count) % 2]


def _initialize(model_config, env_options, specs, cpu_duty_cycle):
    global _model, _env_options, _partners, _cpu_duty_cycle
    torch.set_num_threads(1)
    _model = ActorCritic(**model_config)
    _env_options = env_options
    _partners = [make_partner(spec) for spec in specs]
    _cpu_duty_cycle = cpu_duty_cycle


def _collect(task):
    from .train import collect_rollout
    state, steps, namespace, torch_seed, gamma, gae_lambda, uniform_mix, discount_unit, ai_role, partner_index = task
    _model.load_state_dict(state)
    torch.manual_seed(torch_seed)
    env = CrewEnv(**_env_options)
    return collect_rollout(_model, env, steps, seed=namespace, episodes_done=0,
        gamma=gamma, gae_lambda=gae_lambda, uniform_mix=uniform_mix, discount_unit=discount_unit,
        partner=_partners[partner_index] if ai_role else None, ai_role=ai_role or 'both',cpu_duty_cycle=_cpu_duty_cycle)


def _evaluate(task):
    state, games, seed = task
    _model.load_state_dict(state)
    options = {k: v for k, v in _env_options.items() if k != 'curriculum_airports'}
    return evaluate(ModelAgent(_model), games=games, seed=seed,cpu_duty_cycle=_cpu_duty_cycle, **options)['episodes']


class ParallelGames:
    def __init__(self, workers, model_config, env_options, *, partner_specs=None, cpu_duty_cycle=1):
        self.workers = workers
        self.pool = ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context('spawn'),
            initializer=_initialize, initargs=(model_config, env_options, partner_specs or [{'kind':'heuristic'}],cpu_duty_cycle))
        self.partner_count = len(partner_specs or [None])

    def collect(self, model, steps, *, seed, update, gamma, gae_lambda, uniform_mix, discount_unit, partner_fraction=0.0):
        state = {k: v.detach().cpu() for k, v in model.state_dict().items()}
        count = min(self.workers, max(1, steps))
        tasks = []
        for i in range(count):
            ordinal = update * count + i
            partner_index, ai_role = partner_assignment(ordinal, partner_fraction, self.partner_count)
            tasks.append((state, (steps + count - 1) // count, f'parallel:{seed}:{update}:{i}',
                          seed + update * 1009 + i, gamma, gae_lambda, uniform_mix, discount_unit, ai_role, partner_index))
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
