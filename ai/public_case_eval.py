"""Explicit public module/card development games using the real engine clock.

No curriculum, training wrapper, proxy timer, or altered terminal outcome is
used here. Results describe this exact route/card case and remain development
evidence; quality approval requires a separate independent qualification
protocol. An explicitly requested preview can remain unqualified.
"""
import math

from .agents import ModelAgent
from .evaluate import summarize_episodes
from .module_training_eval import _development_seed, _official_cases, case_key
from .modules import ModuleEnv
from .throttle import CpuBudget


def run_public_case(model, case, games, seed, cpu_duty_cycle=.7, assistance_version=11):
    """Run guided self-play with deterministic policy choices on one case.

    Decisions see only the current role's own hand and public state. Future
    dice and private partner faces remain inside the engine. This function
    changes no Torch RNG/thread settings and restores the model's train mode.
    Real realtime deadlines depend on elapsed engine wall time; their outcomes
    can therefore depend on runtime despite identical seeds/policy choices.
    """
    _development_seed(seed, games)
    key = case_key(case)
    pair = (case['airport'], tuple(sorted(case['abilities'])))
    official = _official_cases()
    if pair not in official or not isinstance(case.get('modules'), (list, tuple)):
        raise ValueError(f'Unknown official route/card case: {key}')
    if sorted(case['modules']) != official[pair]:
        raise ValueError(f'Case modules do not match the official engine route: {key}')
    config = getattr(model, 'config', {})
    if (config.get('kind') != 'guided_residual' or config.get('observation_size') != 489
            or config.get('action_count') != 217):
        raise ValueError('Use a guided schema-3 player with 489 features and 217 actions.')
    if assistance_version not in (10, 11):
        raise ValueError('Public module development uses explicit profile 10 or 11.')
    if not math.isfinite(cpu_duty_cycle) or not 0 < cpu_duty_cycle <= .7:
        raise ValueError('Evaluation duty cycle must be in (0, .7].')
    budget = CpuBudget(cpu_duty_cycle)
    env = ModuleEnv(case['airport'], abilities=list(case['abilities']),
                    assistance_version=assistance_version, max_steps=256,
                    round_reward=0., sync_weight=0., task_weight=0.)
    agent = ModelAgent(model)
    records = []
    was_training = model.training
    model.eval()
    try:
        for ordinal in range(games):
            game_seed = seed + ordinal
            _, info = env.reset(seed=game_seed)
            actual = env.view()['modules_state']
            if (env.game.landung.get_code() != case['airport']
                    or sorted(actual['cards']) != sorted(case['abilities'])
                    or sorted(actual['modules']) != sorted(case['modules'])):
                raise RuntimeError('The engine selected a different route/card case.')
            total_reward = 0.
            departures = decisions = 0
            while not env.done:
                reference = info['reference_action_mask']
                action = agent.select(env.view(), info['action_mask'], reference_mask=reference)
                departures += int(not reference[action])
                decisions += 1
                _, reward, _, _, info = env.step(action)
                total_reward += reward
                budget.pause()
            record = env.episode_record(game_seed, 'both', total_reward)
            record.update(airport=case['airport'], abilities=sorted(case['abilities']),
                          modules=sorted(case['modules']), case_key=key,
                          reference_departures=departures, decisions=decisions)
            records.append(record)
    finally:
        model.train(was_training)
    summary = summarize_episodes(records)
    departures = sum(record['reference_departures'] for record in records)
    decisions = sum(record['decisions'] for record in records)
    return {'complete': True, 'airport': case['airport'],
            'abilities': sorted(case['abilities']), 'modules': sorted(case['modules']),
            'case_key': key, 'assistance_version': assistance_version,
            'clock_model': 'engine_wall_clock', 'release_evidence': False,
            'qualification_used': False, 'reference_departures': departures,
            'decisions': decisions,
            'reference_departure_rate': departures / decisions if decisions else 0.,
            **summary}
