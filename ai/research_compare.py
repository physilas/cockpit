"""Resumable paired development benchmark for public simulator search/shields.

No production policy is replaced. Both roles use independent observation-only
agents; real engine wall time applies to realtime routes, including search.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
import json
import hashlib
import multiprocessing
from pathlib import Path
import time

from .checkpoints import load_checkpoint, weight_fingerprint
from .evaluate import summarize_episodes
from .module_training_eval import case_key, _development_seed
from .modules import ModuleEnv
from .preview_matrix_eval import catalogue_cases
from .rollout_search import GuidedBlueprint, RolloutSearchAgent, SearchConfig
from .safety_guard import ShieldedBlueprint
from .coherent_safety import coherent_safe_actions


_blueprint = None
_search_config = None
_information_config = None
_profile = None
_model = None
_contract_beam = None
_contract_model = None


def initialize(checkpoint, config, information_config=None, profile='legacy', contract_beam=24, guide_margin=12.):
    import torch
    global _blueprint, _search_config, _information_config, _profile, _model, _contract_beam, _contract_model
    torch.set_num_threads(1)
    model, _ = load_checkpoint(checkpoint)
    model.eval()
    _blueprint, _search_config = GuidedBlueprint(model), config
    _information_config, _profile, _model = information_config, profile, model
    _contract_beam=contract_beam
    from .intern_strength_compare import with_margin
    _contract_model=with_margin(model,guide_margin)


def run_task(task):
    case, mode, games, seed, audit, skip_plain = task
    _development_seed(seed, games)
    airport = case['airport']
    blueprint = _blueprint
    if _profile == 'robust':
        from .robust_policy import RobustBlueprint
        blueprint = RobustBlueprint(airport, _model)
    skip_search = skip_plain and mode in ('round', 'game', 'uct') and not case['modules'] and not case['abilities']
    effective = 'shield' if skip_search else mode
    if effective == 'baseline':
        make_agent = lambda: blueprint
    elif effective == 'shield':
        make_agent = lambda: ShieldedBlueprint(airport, blueprint)
    elif effective == 'uct':
        from .information_search import InformationSearchAgent
        make_agent = lambda: InformationSearchAgent(airport, blueprint, **_information_config)
    elif effective == 'contract':
        from .contract_planner import ContractAgent
        make_agent = lambda: ContractAgent(airport,blueprint,beam=_contract_beam)
    elif effective == 'advice':
        from .contract_environment import ContractBlueprint
        make_agent = lambda: ContractBlueprint(airport,_contract_model,beam=_contract_beam)
    else:
        options = {**_search_config, 'horizon': 'game' if mode == 'game' else 'round'}
        make_agent = lambda: RolloutSearchAgent(airport, blueprint, config=SearchConfig(**options))
    agents = {role: make_agent() for role in ('pilot', 'kopilot')}
    env = ModuleEnv(airport, abilities=case['abilities'], assistance_version=0,
                    round_reward=0., sync_weight=0., task_weight=0.)
    records = []
    started = time.monotonic()
    for ordinal in range(games):
        env.reset(seed=seed + ordinal)
        decisions = overrides = paired_samples = simulations = unsafe = 0
        stranded_events = range_dead_events = 0
        previous_stranded = 0
        previous_range_dead = False
        decision_times = []
        total = 0.
        while not env.done:
            agent = agents[env.current_role]
            view, raw = env.view(), env.action_mask()
            tick = time.monotonic()
            action = agent.select(view, raw)
            decision_times.append(time.monotonic() - tick)
            decisions += 1
            if effective in ('round', 'game', 'uct', 'contract'):
                overrides += int(action != agent.last_report['baseline'])
                paired_samples += agent.last_report.get('samples', 0)
                simulations += agent.last_report.get('simulations', 0)
            elif effective=='advice':
                overrides+=int(action!=blueprint.select(view,raw))
            if audit:
                _, safety = coherent_safe_actions(airport, view, raw)
                unsafe += int(str(action) in safety['rejected'] and not safety['fallback'])
            _, reward, _, _, _ = env.step(action)
            total += reward
            public = env.view()
            stranded = sum(cell['planes'] for cell in public['track'] if cell['distance']>public['distance'])
            stranded_events += int(stranded>previous_stranded)
            previous_stranded = stranded
            maximum = 2 if 'wind' in public['modules_state']['modules'] else (
                int(12>=public['aero_blue'])+int(12>=public['aero_orange']))
            range_dead = public['distance']>maximum*max(0,public['height']//1000)
            range_dead_events += int(range_dead and not previous_range_dead)
            previous_range_dead = range_dead
        record = env.episode_record(seed + ordinal, 'both', total)
        record.update(decisions=decisions, search_overrides=overrides, paired_samples=paired_samples,
                      search_simulations=simulations,
                      avoidable_immediate_losses=unsafe,
                      stranded_plane_events=stranded_events, stranded_planes=previous_stranded,
                      irreversible_range_events=range_dead_events,
                      decision_seconds=sum(decision_times), max_decision_seconds=max(decision_times, default=0.))
        records.append(record)
    return dict(case=case, mode=mode, search_skipped=bool(skip_search), case_key=case_key(case), wall_seconds=time.monotonic()-started,
                clock_model='engine_wall_clock', release_evidence=False, qualification_used=False,
                **summarize_episodes(records))


def atomic_json(path, data):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def research_fingerprint():
    digest = hashlib.sha256()
    for name in ('belief_simulator.py', 'rollout_search.py', 'safety_guard.py', 'research_compare.py',
                 'information_search.py', 'robust_policy.py'):
        digest.update(Path(__file__).with_name(name).read_bytes())
    digest.update(Path(__file__).with_name('contract_planner.py').read_bytes())
    digest.update(Path(__file__).with_name('coherent_safety.py').read_bytes())
    for name in ('assignment_belief.py','contract_advice.py','contract_environment.py'):
        digest.update(name.encode());digest.update(Path(__file__).with_name(name).read_bytes())
    return digest.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint', default='ai/releases/crew4-allroutes-2026-10-26-v1/best.pt')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--airports', nargs='*')
    p.add_argument('--one-card-set-per-route', action='store_true')
    p.add_argument('--modes', nargs='+', choices=('baseline', 'shield', 'round', 'game', 'uct', 'contract','advice'), default=['baseline', 'shield', 'round'])
    p.add_argument('--contract-beam', type=int, default=24)
    p.add_argument('--guide-margin',type=float,choices=(4.,8.,12.),default=12.)
    p.add_argument('--profile', choices=('legacy', 'robust'), default='legacy')
    p.add_argument('--skip-plain-search', action='store_true')
    p.add_argument('--simulations', type=int, default=128)
    p.add_argument('--games', type=int, default=5)
    p.add_argument('--seed', type=int, default=14900000)
    p.add_argument('--workers', type=int, default=3)
    p.add_argument('--samples', type=int, default=4)
    p.add_argument('--candidates', type=int, default=6)
    p.add_argument('--max-seconds', type=float, default=2.)
    p.add_argument('--minimum-gain', type=float, default=.03)
    p.add_argument('--audit', action='store_true')
    p.add_argument('--resume', action='store_true')
    args = p.parse_args()
    if not 1 <= args.workers <= 8 or not 1 <= args.games <= 100 or not 1<=args.contract_beam<=128:
        p.error('Use 1..8 workers and 1..100 games per exact case.')
    cases = catalogue_cases()
    if args.airports:
        unknown = set(args.airports) - {row['airport'] for row in cases}
        if unknown:
            p.error(f'Unknown airports: {sorted(unknown)}')
        cases = [row for row in cases if row['airport'] in args.airports]
    if args.one_card_set_per_route:
        cases = list({row['airport']: row for row in reversed(cases)}.values())
    cases = sorted(cases, key=case_key)
    _development_seed(args.seed, (len(cases)-1)*100 + args.games)
    config = asdict(SearchConfig(samples=args.samples, candidates=args.candidates,
                    max_seconds=args.max_seconds, minimum_samples=min(4, args.samples),
                    minimum_gain=args.minimum_gain))
    from .information_search import InformationSearchAgent
    information_config = dict(simulations=args.simulations, width=args.candidates,
                              max_seconds=args.max_seconds, minimum_visits=min(4, args.simulations))
    InformationSearchAgent('MUC', None, **information_config)  # Validate before spawning.
    model, _ = load_checkpoint(args.checkpoint)
    metadata = dict(checkpoint=args.checkpoint, weights_sha256=weight_fingerprint(model),
                    cases=cases, modes=args.modes, games=args.games, seed=args.seed,
                    search=config, information_search=information_config, profile=args.profile,
                    skip_plain_search=args.skip_plain_search,
                    contract_beam=args.contract_beam,
                    guide_margin=args.guide_margin,
                    audit=args.audit, research_sha256=research_fingerprint())
    del model
    rows = {}
    if args.output.exists():
        if not args.resume:
            p.error('Preserve prior reports; use a new output or explicit --resume.')
        old = json.loads(args.output.read_text())
        if old['config'] != metadata:
            p.error('Resume configuration must exactly match the saved report.')
        rows = old['results']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tasks = [(case, mode, args.games, args.seed + i*100, args.audit, args.skip_plain_search)
             for i, case in enumerate(cases) for mode in args.modes
             if case_key(case)+'/'+mode not in rows]
    report = dict(config=metadata, complete=False, release_evidence=False, results=rows)
    atomic_json(args.output, report)
    pool = ProcessPoolExecutor(args.workers, mp_context=multiprocessing.get_context('spawn'),
            initializer=initialize, initargs=(args.checkpoint, config, information_config, args.profile,args.contract_beam,args.guide_margin))
    try:
        # Finish inexpensive controls first; hard module searches precede
        # expensive searches on already strong custom/base routes.
        tasks.sort(key=lambda task: (task[1] in ('round','game','uct','contract','advice'), not bool(task[0]['modules'])))
        futures = [pool.submit(run_task, task) for task in tasks]
        for future in as_completed(futures):
            row = future.result()
            rows[row['case_key']+'/'+row['mode']] = row
            atomic_json(args.output, report)
            print(json.dumps({k: row[k] for k in ('case_key','mode','games','wins','wall_seconds')}), flush=True)
    except BaseException:
        # Python 3.13's context manager otherwise waits for every queued long
        # search after the first failure, concealing the actual error for hours.
        for worker in pool._processes.values():
            worker.terminate()
        pool.shutdown(wait=True, cancel_futures=True)
        raise
    else:
        pool.shutdown(wait=True)
    report['complete'] = True
    atomic_json(args.output, report)


if __name__ == '__main__':
    main()
