"""Paired, seed-disjoint comparisons against a frozen cooperative partner league."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import math
import multiprocessing
from pathlib import Path

import torch

from .agents import ModelAgent, HeuristicAgent
from .checkpoints import load_checkpoint, weight_fingerprint, planner_fingerprint
from .evaluate import evaluate, summarize_episodes
from .partners import FrozenPartner


def _run(task):
    label, checkpoint, profile, airport, kind, frozen, role, seed, games, margin, beam, duty = task
    torch.set_num_threads(1)
    torch.manual_seed(seed)
    probing = label == 'candidate' and (margin is not None or beam is not None)
    probe_enabled = True
    if probing:
        # Development-only ablation: keep all values/beam decisions intact and
        # rescale only the returned shortlist distances. Never used in releases.
        from . import tactics
        original = tactics.plan_actions
        def shortlist_probe(*a, **kw):
            if not probe_enabled:
                return original(*a,**kw)
            if beam is not None:
                kw['beam']=beam
            ranks,sequences=original(*a,**kw)
            if margin is None:
                return ranks,sequences
            best=max(ranks.values(),default=0)
            from .actions import ACTIONS
            return {i:best-(best-v)*(3 if kw.get('version',1)>=4 and ACTIONS[i].kind=='place' else 1.5)/margin
                    for i,v in ranks.items()},sequences
        tactics.plan_actions=shortlist_probe
        tactics._cached_mask.cache_clear()
    model, _ = load_checkpoint(checkpoint)
    partner = None if kind == 'self' else HeuristicAgent() if kind == 'heuristic' else FrozenPartner(frozen, stochastic=kind == 'noisy')
    if probing and isinstance(partner,FrozenPartner):
        partner_select=partner.select
        def unprobed_partner(view,mask):
            nonlocal probe_enabled
            probe_enabled=False
            try:
                return partner_select(view,mask)
            finally:
                probe_enabled=True
        partner.select=unprobed_partner
    records = evaluate(ModelAgent(model), airport=airport, assistance_version=profile,
        partner=partner, ai_role=role, seed=seed, games=games, round_reward=0,cpu_duty_cycle=duty)['episodes']
    if probing:
        tactics.plan_actions=original
        tactics._cached_mask.cache_clear()
    return label, airport, kind, role, records


def paired_summary(baseline, candidate):
    """Normal interval with repeated roles/partners clustered by route + seed."""
    groups, improved, regressed = {}, 0, 0
    for key, old in baseline.items():
        new = candidate[key]
        delta = int(new['status'] == 'gewonnen')-int(old['status'] == 'gewonnen')
        improved += delta > 0
        regressed += delta < 0
        groups.setdefault((key[0], key[-1]), []).append(delta)
    values = [sum(v)/len(v) for v in groups.values()]
    mean = sum(values)/len(values)
    se = math.sqrt(sum((v-mean)**2 for v in values)/(len(values)*(len(values)-1))) if len(values)>1 else 1
    return {'paired_games': len(baseline), 'seed_clusters': len(values), 'improved': improved, 'regressed': regressed,
            'win_rate_delta': mean, 'delta_ci_low': max(-1,mean-1.96*se), 'delta_ci_high': min(1,mean+1.96*se)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--candidate-profile', type=int)
    p.add_argument('--candidate-margin', type=float, help='Development-only shortlist ablation; never publish this report.')
    p.add_argument('--candidate-beam', type=int, help='Development-only search-width ablation.')
    p.add_argument('--airports', nargs='+', default=['LOG_HND_GREEN','LOG_LHR_GREEN','LOG_YUL_GREEN','MUC_T3'])
    p.add_argument('--partners', nargs='+', choices=['self','heuristic','frozen','noisy'], default=['self','heuristic','frozen','noisy'])
    p.add_argument('--games', type=int, default=100, help='Games per route/partner/role.')
    p.add_argument('--seed', type=int, default=10_000_000)
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--cpu-duty-cycle',type=float,default=.5)
    p.add_argument('--output', type=Path, required=True)
    args=p.parse_args()
    if min(args.games,args.workers)<1 or args.candidate_margin is not None and args.candidate_margin<=0:
        p.error('Positive games and workers are required.')
    checkpoints={'baseline':args.baseline,'candidate':args.candidate}
    metadata={}
    for label,path in checkpoints.items():
        model,payload=load_checkpoint(path)
        metadata[label]={'weights_sha256':weight_fingerprint(model),
            'profile':args.candidate_profile if label=='candidate' and args.candidate_profile is not None else payload['train_config'].get('assistance_version',0)}
    tasks=[]
    for airport in args.airports:
        for kind in args.partners:
            for role in (('both',) if kind=='self' else ('pilot','kopilot')):
                for start in range(0,args.games,20):
                    for label,path in checkpoints.items():
                        tasks.append((label,str(path),metadata[label]['profile'],airport,kind,str(args.baseline),role,
                                      args.seed+start,min(20,args.games-start),args.candidate_margin,args.candidate_beam,args.cpu_duty_cycle))
    results={label:{} for label in checkpoints}
    buckets={}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    manifest={'models':metadata,'planner_sha256':planner_fingerprint(),'seed':args.seed,
              'airports':args.airports,'partners':args.partners,'games':args.games,
              'margin':args.candidate_margin,'beam':args.candidate_beam}
    journal=args.output.with_suffix('.episodes.jsonl')
    cached=[]
    if journal.exists():
        lines=journal.read_text().splitlines()
        if json.loads(lines[0])!=manifest:
            raise ValueError('Comparison journal belongs to a different experiment; use a new --output.')
        cached=[json.loads(line) for line in lines[1:]]
    else:
        journal.write_text(json.dumps(manifest)+'\n')
    def remember(output):
        label,airport,kind,role,records=output
        buckets.setdefault((label,airport,kind),[]).extend(records)
        for record in records:
            results[label][airport,kind,role,record['seed']]=record
    completed=set()
    for output in cached:
        remember(output)
        label,airport,kind,role,records=output
        completed.add((label,airport,kind,role,records[0]['seed']))
    remaining=[t for t in tasks if (t[0],t[3],t[4],t[6],t[7]) not in completed]
    print(f"CPU: {args.workers} Worker × {args.cpu_duty_cycle:.0%}; {len(cached)}/{len(tasks)} Blöcke gespeichert.",flush=True)
    with ProcessPoolExecutor(args.workers,mp_context=multiprocessing.get_context('spawn')) as pool:
        for i,output in enumerate(pool.map(_run,remaining),len(cached)+1):
            remember(output)
            with journal.open('a') as handle:
                handle.write(json.dumps(output)+'\n')
            label,airport,kind,role,records=output
            print(f"[{i}/{len(tasks)}] {label} {airport} {kind} {role}: "
                  f"{sum(r['status']=='gewonnen' for r in records)}/{len(records)}",flush=True)
    report={'format':1,'seed':args.seed,'games_per_role':args.games,'models':metadata,
            'planner_sha256':planner_fingerprint(),'development_margin':args.candidate_margin,
            'development_beam':args.candidate_beam,'routes':{},'comparison':paired_summary(**results)}
    for airport in args.airports:
        row={}
        for kind in args.partners:
            row[kind]={}
            for label in checkpoints:
                summary=summarize_episodes(buckets[label,airport,kind]);summary.pop('episodes')
                if kind!='self':
                    summary['by_role']={}
                    for role in ('pilot','kopilot'):
                        sub=summarize_episodes([r for r in buckets[label,airport,kind] if r['ai_role']==role])
                        sub.pop('episodes')
                        summary['by_role'][role]=sub
                row[kind][label]=summary
            print(f"{airport} {kind}: {row[kind]['baseline']['win_rate']:.1%} -> {row[kind]['candidate']['win_rate']:.1%}",flush=True)
        report['routes'][airport]=row
    for kind in args.partners:
        subset={label:{k:v for k,v in data.items() if k[1]==kind} for label,data in results.items()}
        report.setdefault('by_partner',{})[kind]=paired_summary(**subset)
    for role in ('pilot','kopilot'):
        subset={label:{k:v for k,v in data.items() if k[2]==role} for label,data in results.items()}
        if subset['baseline']:
            report.setdefault('by_role',{})[role]=paired_summary(**subset)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['comparison']),flush=True)


if __name__=='__main__':
    main()
