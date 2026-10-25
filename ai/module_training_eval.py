"""Explicit route/card development cases for the all-module research phase.

No training curriculum is passed to evaluation environments. Each result belongs
to one requested route AND card combination; pooling is descriptive only.
"""
from collections import defaultdict
import itertools
import json
import math
from pathlib import Path

from backend.katalog import landekatalog
from backend.zusatzregeln import KARTEN

from .agents import ModelAgent
from .evaluate import summarize_episodes
from .throttle import CpuBudget


def case_key(case):
    """Stable join key shared by curriculum counters and evaluation records."""
    airport, abilities = case.get('airport'), case.get('abilities')
    if not isinstance(airport, str) or not airport or not isinstance(abilities, (list, tuple)):
        raise ValueError('A case needs an airport and an explicit abilities list.')
    if any(not isinstance(card, str) for card in abilities) or len(set(abilities)) != len(abilities):
        raise ValueError('Case abilities must be distinct strings.')
    return airport + '|' + ','.join(sorted(abilities))


def _official_cases():
    return {
        (scenario['engine_code'], tuple(cards)): sorted(scenario['modules'])
        for scenario in landekatalog()['scenarios'] if scenario['kind'] == 'logbook'
        for cards in itertools.combinations(sorted(KARTEN), scenario['ability_count'])
    }


def load_cases(matrix_path):
    """Validate the complete 21-route/186-case official rule matrix."""
    payload = json.loads(Path(matrix_path).read_text(encoding='utf-8'))
    rows = payload.get('cases') if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError('The matrix must contain a cases list.')
    official = _official_cases()
    result, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Each matrix case must be an object.')
        key = case_key(row)
        pair = (row['airport'], tuple(sorted(row['abilities'])))
        modules = row.get('modules')
        if pair not in official or not isinstance(modules, list) or sorted(modules) != official[pair]:
            raise ValueError(f'Case does not match the official engine scenario: {key}')
        if key in seen:
            raise ValueError(f'Duplicate route/card case: {key}')
        seen.add(key)
        result.append({**row, 'abilities': sorted(row['abilities']), 'modules': sorted(modules)})
    pairs = {(row['airport'], tuple(row['abilities'])) for row in result}
    if len(result) != 186 or len({row['airport'] for row in result}) != 21 or pairs != set(official):
        raise ValueError('Expected exactly all 186 official cases on 21 routes.')
    return result


def balanced_cases(cases):
    """Exact duplication: uniform route first, uniform valid cards within it.

    The full matrix has 1, 6 or 15 combinations per route. Their LCM is 30,
    resulting in 21 * 30 = 630 equally sampled curriculum entries.
    """
    grouped, seen = defaultdict(list), set()
    for case in cases:
        key = case_key(case)
        if key in seen:
            raise ValueError(f'Duplicate curriculum case: {key}')
        seen.add(key)
        grouped[case['airport']].append(case)
    if not grouped:
        raise ValueError('At least one curriculum case is required.')
    multiplicity = math.lcm(*(len(rows) for rows in grouped.values()))
    return [
        {**case, 'abilities': sorted(case['abilities']), 'modules': list(case['modules'])}
        for airport in sorted(grouped)
        for case in sorted(grouped[airport], key=case_key)
        for _ in range(multiplicity // len(grouped[airport]))
    ]


def _development_seed(seed, games):
    if type(games) is not int or games < 1 or type(seed) is not int:
        raise ValueError('Use a positive game count and integer development seed.')
    if not 14_000_000 <= seed or seed + games > 15_000_000:
        raise ValueError('Development must stay in [14,000,000, 15,000,000); qualification seeds are reserved.')


def run_case(model, case, games, seed, duty=.7, *, cpu_duty_cycle=None, capacity_guard=False):
    """Deterministic full self-play on ONE explicit development case.

    This uses the research environment's logical one-second decision clock.
    It does not constitute qualification of production realtime behavior.
    The caller may distribute independent calls across its bounded worker pool.
    """
    from .all_modules_environment import AllModulesEnv
    if type(capacity_guard) is not bool:
        raise ValueError('capacity_guard must be Boolean.')
    if capacity_guard:
        from .capacity_modules_environment import CapacityModulesEnv
        environment = CapacityModulesEnv
    else:
        environment = AllModulesEnv

    _development_seed(seed, games)
    key = case_key(case)
    pair = (case['airport'], tuple(sorted(case['abilities'])))
    if pair not in _official_cases():
        raise ValueError(f'Unknown official route/card case: {key}')
    duty = duty if cpu_duty_cycle is None else cpu_duty_cycle
    if not math.isfinite(duty) or not 0 < duty <= .7:
        raise ValueError('Evaluation duty cycle must be in (0, .7].')
    if model.config.get('observation_size') != 489 or model.config.get('action_count') != 217:
        raise ValueError('All-module evaluation requires schema-3 model dimensions.')
    cpu_budget = CpuBudget(duty)
    env = environment(case['airport'], abilities=list(case['abilities']),
                        assistance_version=9, max_steps=256, round_reward=0.,
                        sync_weight=0., task_weight=0.)
    agent, records = ModelAgent(model), []
    was_training = getattr(model, 'training', False)
    model.eval()
    try:
        for game_index in range(games):
            game_seed = seed + game_index
            _, info = env.reset(seed=game_seed)
            actual = env.view()['modules_state']
            if (env.game.landung.get_code() != case['airport'] or
                    sorted(actual['cards']) != sorted(case['abilities']) or
                    sorted(actual['modules']) != sorted(case['modules'])):
                raise RuntimeError('Evaluation environment selected a different route/card case.')
            total_reward = 0.
            while not env.done:
                guidance = ({'reference_mask': info['reference_action_mask']}
                            if model.config.get('kind') == 'guided_residual' else {})
                action = agent.select(env.view(), info['action_mask'], **guidance)
                _, reward, _, _, info = env.step(action)
                total_reward += reward
                cpu_budget.pause()
            record = env.episode_record(game_seed, 'both', total_reward)
            record.update(airport=case['airport'], abilities=sorted(case['abilities']),
                          modules=sorted(case['modules']), case_key=key)
            records.append(record)
    finally:
        model.train(was_training)
    return {'airport': case['airport'], 'abilities': sorted(case['abilities']),
            'modules': sorted(case['modules']), 'case_key': key,
            'clock_model': 'logical_one_second_per_decision',
            'research_capacity_guard': capacity_guard,
            'release_evidence': False,
            'training_budget_failures': sum(bool(row.get('training_budget_failure')) for row in records),
            **summarize_episodes(records)}


def evaluate_cases(model, cases, games_per_case, seed, workers=1, cpu_duty_cycle=.7):
    """Sequential helper; parallel callers should distribute ``run_case``."""
    if workers != 1:
        raise ValueError('This helper is sequential; distribute run_case in the existing worker pool.')
    rows = list(cases)
    keys = [case_key(case) for case in rows]
    if not rows or len(set(keys)) != len(keys):
        raise ValueError('Evaluation needs distinct nonempty route/card cases.')
    _development_seed(seed, games_per_case * len(rows))
    results = [run_case(model, case, games_per_case, seed + index * games_per_case,
                        cpu_duty_cycle=cpu_duty_cycle)
               for index, case in enumerate(rows)]
    return {'complete': True, 'release_evidence': False, 'games_per_case': games_per_case,
            'cases': results, 'by_case': {row['case_key']: row for row in results},
            'games': sum(row['games'] for row in results),
            'wins': sum(row['wins'] for row in results),
            'minimum_case_win_rate': min(row['win_rate'] for row in results),
            'training_budget_failures': sum(row['training_budget_failures'] for row in results)}
