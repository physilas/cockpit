"""Bounded PPO transfer from Crew 1 to schema-2 kerosene, without cards.

Example: python -m ai.train_fuel --steps 60000 --workers 6 --cpu-duty-cycle .5
Training uses string seed namespaces; validation and final tests stay separate.
"""
import argparse
import json
from pathlib import Path
import time

import torch

from .checkpoints import load_checkpoint, save_checkpoint, planner_fingerprint, weight_fingerprint, model_schema
from .fuel import FUEL_ACTIONS, FUEL_FEATURES
from .nn_model import ActorCritic,ResidualActorCritic
from .parallel import ParallelGames
from .train import ppo_update


def expand_base_model(source):
    """Preserve all legacy logits/values exactly; new inputs start at zero."""
    if source.config['observation_size'] != 349 or source.config['action_count'] != 121 or hasattr(source, 'roles'):
        raise ValueError('Expected the shared schema-1 Crew model.')
    model = ActorCritic(len(FUEL_FEATURES), len(FUEL_ACTIONS), source.config['hidden_size'], source.config['hidden_layers'])
    state = model.state_dict()
    for key, value in source.state_dict().items():
        if key == 'encoder.0.weight':
            state[key].zero_()
            state[key][:, :value.shape[1]].copy_(value)
        elif key.startswith('actor.'):
            state[key].zero_()
            state[key][:value.shape[0]].copy_(value)
        else:
            state[key].copy_(value)
    model.load_state_dict(state)
    return model



def freeze_legacy_policy(model):
    """Learn appended inputs/actions while keeping the base-game actor intact."""
    for parameter in model.encoder.parameters():
        parameter.requires_grad_(False)
    model.encoder[0].weight.requires_grad_(True)
    model.encoder[0].weight.register_hook(lambda grad: torch.cat((torch.zeros_like(grad[:,:349]),grad[:,349:]),dim=1))
    model.actor.weight.register_hook(lambda grad: torch.cat((torch.zeros_like(grad[:121]),grad[121:]),dim=0))
    model.actor.bias.register_hook(lambda grad: torch.cat((torch.zeros_like(grad[:121]),grad[121:]),dim=0))


def successful_replay(batch, records, previous=None, *, limit=4096):
    """Keep ONLY training wins, never validation/test moves or hidden hands."""
    indices=[]
    offset=0
    for record in records:
        if record['status']=='gewonnen': indices.extend(range(offset,offset+record['steps']))
        offset+=record['steps']
    if offset!=len(batch['actions']):
        raise ValueError('Successful replay currently requires both-role self-play.')
    if not indices:return previous
    selected=torch.tensor(indices,device=batch['actions'].device)
    rows={k:batch[k][selected].detach() for k in ('observations','masks','actions')}
    if previous:rows={k:torch.cat((previous[k],rows[k])) for k in rows}
    return {k:v[-limit:] for k,v in rows.items()}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--resume', type=Path)
    p.add_argument('--residual-source', type=Path, help='New zero-output detail branch around an already trained fuel model.')
    p.add_argument('--self-imitation-coef', type=float, default=0.)
    p.add_argument('--source', type=Path, default=Path('ai/releases/crew-basegame-v1/best.pt'))
    p.add_argument('--run-dir', type=Path, default=Path('runs/kerosene-v1'))
    p.add_argument('--steps', type=int, default=60000)
    p.add_argument('--workers', type=int, default=6)
    p.add_argument('--cpu-duty-cycle', type=float, default=.5)
    p.add_argument('--seed', type=int, default=None)
    p.add_argument('--eval-seed', type=int, default=14000000)
    p.add_argument('--eval-games', type=int, default=80)
    p.add_argument('--eval-every', type=int, default=5)
    p.add_argument('--curriculum-airports', nargs='+')
    p.add_argument('--eval-airports', nargs='+')
    p.add_argument('--device', default='mps')
    p.add_argument('--freeze-legacy', action='store_true', default=None)
    p.add_argument('--assistance-version', type=int, choices=(3,4,5,6,7,8,9), default=None)
    args = p.parse_args()
    seed_omitted=args.seed is None
    args.seed=250925 if seed_omitted else args.seed
    if not 1 <= args.workers <= 8 or not 0 < args.cpu_duty_cycle <= .7 or min(args.steps, args.eval_games, args.eval_every) < 1:
        p.error('Resource cap: 1–8 workers, duty cycle in (0,.7]; positive budgets.')
    if not 0 <= args.self_imitation_coef <= .1:
        p.error("Self-imitation coefficient must be in [0,.1].")
    if args.resume and args.residual_source:
        p.error('Choose resume or a new residual phase, not both.')
    if args.run_dir.exists():
        p.error('Use a new run directory, preserving earlier results.')
    torch.set_num_threads(1)
    torch.manual_seed(args.seed)
    base, source_payload = load_checkpoint(args.source)
    resume = None
    module_source_payload = None
    if args.resume:
        model,resume = load_checkpoint(args.resume,args.device)
        previous = resume['train_config']
        if seed_omitted:args.seed=previous['seed']
        if previous['source_weights_sha256'] != weight_fingerprint(base) or previous['planner_sha256'] != planner_fingerprint(model_schema(model)['version']):
            p.error('Resume requires the same source weights and planner.')
        args.assistance_version = previous['assistance_version'] if args.assistance_version is None else args.assistance_version
        args.freeze_legacy = previous['freeze_legacy'] if args.freeze_legacy is None else args.freeze_legacy
        if any(previous[k] != getattr(args,k) for k in ('seed','assistance_version','freeze_legacy')):
            p.error('Resume must preserve training seeds, planner profile and trainable parameters.')
    elif args.residual_source:
        inherited,module_source_payload=load_checkpoint(args.residual_source,args.device)
        if model_schema(inherited)['version'] not in (2,3):
            p.error('Residual module transfer requires schema 2 or 3.')
        if args.freeze_legacy:
            p.error('Residual transfer freezes its source automatically; do not add --freeze-legacy.')
        if (module_source_payload.get('rule_pretraining_examples') or module_source_payload.get('policy_pretraining_examples')) and inherited.config.get('kind')=='residual':
            model=inherited
        else:
            model=ResidualActorCritic(inherited,inherited.config['observation_size'],inherited.config['action_count'],hidden_size=256).to(args.device)
        args.assistance_version=args.assistance_version or module_source_payload['train_config']['assistance_version']
        args.freeze_legacy=False
    else:
        model = expand_base_model(base).to(args.device)
        args.assistance_version = args.assistance_version or 3
        args.freeze_legacy = bool(args.freeze_legacy)
    if args.freeze_legacy:
        freeze_legacy_policy(model)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-4 if args.freeze_legacy or args.residual_source else 5e-5, eps=1e-5)
    if resume:
        optimizer.load_state_dict(resume['optimizer_state'])
        torch.set_rng_state(resume['torch_rng_state'].cpu())
        if args.device=='mps': torch.mps.set_rng_state(resume['mps_rng_state'].cpu())
    previous_config=resume['train_config'] if resume else {}
    args.curriculum_airports=args.curriculum_airports or previous_config.get('curriculum_airports',[])
    args.eval_airports=args.eval_airports or previous_config.get('eval_airports',[])
    config = dict(airport='LOG_OSL_GREEN', max_steps=256, assistance_version=args.assistance_version,
                  schema_version=model_schema(model)['version'], supported_modules=['kerosene'], ability_count=0,
                  round_reward=0., sync_weight=.05, sync_tolerance=1., task_weight=.02,
                  source_checkpoint=args.source.as_posix(), source_weights_sha256=weight_fingerprint(base),
                  source_total_steps=source_payload.get('total_steps', 0), seed=args.seed,
                  eval_seed=args.eval_seed, eval_games=args.eval_games, workers=args.workers,
                  cpu_duty_cycle=args.cpu_duty_cycle, threads=1, device=args.device,
                  planner_sha256=planner_fingerprint(model_schema(model)['version']), action_mask_version=2,
                  resumed_from=args.resume.as_posix() if args.resume else None,
                  residual_source=args.residual_source.as_posix() if args.residual_source else (resume['train_config'].get('residual_source') if resume else None),
                  rule_pretraining_examples=module_source_payload.get('rule_pretraining_examples',0) if module_source_payload else (resume['train_config'].get('rule_pretraining_examples',0) if resume else 0),
                  policy_pretraining_examples=module_source_payload.get('policy_pretraining_examples',0) if module_source_payload else (resume['train_config'].get('policy_pretraining_examples',0) if resume else 0),
                  inherited_module_steps=module_source_payload.get('module_training_steps',0) if module_source_payload else (resume['train_config'].get('inherited_module_steps',0) if resume else 0),
                  curriculum_airports=args.curriculum_airports, eval_airports=args.eval_airports,
                  self_imitation_coef=args.self_imitation_coef, freeze_legacy=args.freeze_legacy, learning_rate=optimizer.param_groups[0]['lr'], uniform_mix=.03, discount_unit='placement')
    args.run_dir.mkdir(parents=True)
    env_options = {k:config[k] for k in ('airport','max_steps','assistance_version','round_reward','sync_weight','sync_tolerance','task_weight')}
    env_options['curriculum_airports']=args.curriculum_airports
    pool = ParallelGames(args.workers, model.config, env_options, cpu_duty_cycle=args.cpu_duty_cycle)
    steps, episodes, update = ((resume[k] for k in ("total_steps","episodes","update")) if resume else (0,0,0))
    from backend.katalog import landekatalog
    module_routes={s['engine_code'] for s in landekatalog()['scenarios'] if s['modules'] or s['ability_count']}
    decisions_by_route=dict(resume.get('decisions_by_route',{})) if resume else {}
    if resume and not decisions_by_route and steps:
        if args.curriculum_airports:p.error('Old mixed-route checkpoint lacks route decision counters.')
        decisions_by_route[config['airport']]=steps
    config["resumed_from_steps"] = steps
    (args.run_dir/"config.json").write_text(json.dumps(config,indent=2)+"\n")
    replay = resume.get("successful_replay") if resume else None
    replay = {k:v.to(args.device) for k,v in replay.items()} if replay else None
    demo_generator = torch.Generator().manual_seed(args.seed+37)
    if resume and "demo_rng_state" in resume: demo_generator.set_state(resume["demo_rng_state"].cpu())
    started = time.monotonic()
    best_score = (-1.,-1.)

    def save(name):
        save_checkpoint(args.run_dir/name, model, train_config=config, total_steps=steps,
            module_training_steps=config['inherited_module_steps']+sum(v for k,v in decisions_by_route.items() if k in module_routes),
            decisions_by_route=decisions_by_route.copy(), episodes=episodes, update=update,
            optimizer_state=optimizer.state_dict(), torch_rng_state=torch.get_rng_state(),
            mps_rng_state=torch.mps.get_rng_state() if args.device=='mps' else torch.get_rng_state(),
            successful_replay={k:v.cpu() for k,v in replay.items()} if replay else None,
            demo_rng_state=demo_generator.get_state())

    def validate():
        nonlocal best_score
        result = pool.evaluate(model, games=args.eval_games, seed=args.eval_seed, airports=args.eval_airports)
        from .evaluate import summarize_episodes
        by_route={airport:summarize_episodes([r for r in result['episodes'] if r['scenario']==airport]) for airport in set(r['scenario'] for r in result['episodes'])}
        score=(min(r['win_rate'] for r in by_route.values()), result['win_rate'])
        summary = {k:v for k,v in result.items() if k!='episodes'}
        row = dict(steps=steps, update=update, elapsed_seconds=time.monotonic()-started, **summary)
        row['by_route']={k:{key:value for key,value in v.items() if key!='episodes'} for k,v in by_route.items()}
        with (args.run_dir/'validation.jsonl').open('a') as f:
            f.write(json.dumps(row)+'\n')
        # The initial policy must remain eligible: a first PPO update can be
        # worse than its source and must not silently replace that baseline.
        if score > best_score:
            best_score = score
            save('best.pt')
        print(json.dumps(dict(steps=steps, games=result['games'], win_rate=result['win_rate'],
                              elapsed_seconds=round(time.monotonic()-started), by_route={k:v['win_rate'] for k,v in by_route.items()}, loss_reasons=result['loss_reasons'])), flush=True)

    try:
        if not resume:
            save('warm.pt')
        validate()
        while steps < args.steps:
            batch, records = pool.collect(model, min(2048,args.steps-steps), seed=args.seed, update=update,
                gamma=.995, gae_lambda=.95, uniform_mix=.03, discount_unit='placement')
            if args.self_imitation_coef:
                replay = successful_replay(batch,records,replay,limit=4096)
            stats = ppo_update(model, optimizer, batch, epochs=4, minibatch_size=256,
                clip=.2, value_coef=.5, entropy_coef=.01, uniform_mix=.03,
                demonstrations=replay, demo_coef=args.self_imitation_coef if replay else 0,
                demo_generator=demo_generator)
            for record in records:
                route=record['scenario']
                decisions_by_route[route]=decisions_by_route.get(route,0)+record['steps']
            steps += len(batch['actions'])
            episodes += len(records)
            update += 1
            with (args.run_dir/'training.jsonl').open('a') as f:
                f.write(json.dumps(dict(steps=steps, update=update, episodes=episodes,
                    train_win_rate=sum(r['status']=='gewonnen' for r in records)/len(records),
                    successful_replay_size=len(replay['actions']) if replay else 0,
                    decisions_by_route=decisions_by_route.copy(), **stats))+'\n')
            save('latest.pt')
            if update % args.eval_every == 0 or steps >= args.steps:
                validate()
    finally:
        pool.close()


if __name__ == '__main__':
    main()
