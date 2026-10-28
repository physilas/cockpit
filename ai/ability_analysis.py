"""Descriptive paired analysis; never promotes a candidate or retunes a policy."""
import argparse
import json
import random
from pathlib import Path
from .module_training_eval import case_key


def analyze(report, repetitions=2000):
    if report.get('complete') is not True:raise ValueError('Analyze complete comparisons only.')
    rows=report['results'];cases=report['config']['cases'];games=report['config']['games']
    official=[c for c in cases if c.get('case_scope')=='official_matrix']
    if not official:official=cases
    by_route={}
    for case in official:by_route.setdefault(case['airport'],[]).append(case)
    route_rows=[];weighted=[]
    for airport,subcases in sorted(by_route.items()):
        a=b=0
        for case in subcases:
            key=case_key(case)
            left,right=rows[key+'/baseline']['episodes'],rows[key+'/candidate']['episodes']
            if [e['seed'] for e in left]!=[e['seed'] for e in right]:raise ValueError('Unpaired comparison')
            av=[int(e['status']=='gewonnen') for e in left];bv=[int(e['status']=='gewonnen') for e in right]
            a+=sum(av);b+=sum(bv)
            weighted.append(([v-u for u,v in zip(av,bv)],1/(len(by_route)*len(subcases))))
        route_rows.append(dict(airport=airport,cases=len(subcases),games=games*len(subcases),baseline_wins=a,candidate_wins=b,
                               baseline_rate=a/(games*len(subcases)),candidate_rate=b/(games*len(subcases))))
    delta=sum(sum(d)/len(d)*w for d,w in weighted)
    rng=random.Random(20261028);bootstrap=[]
    for _ in range(repetitions):
        bootstrap.append(sum(sum(rng.choice(d) for _ in d)/len(d)*w for d,w in weighted))
    bootstrap.sort()
    def summary(selected):
        result={}
        for mode in ('baseline','candidate'):
            episodes=[e for c in selected for e in rows[case_key(c)+'/'+mode]['episodes']]
            result[mode]=dict(games=len(episodes),wins=sum(e['status']=='gewonnen' for e in episodes),
                **{field:sum(e.get(field,0) for e in episodes) for field in (
                    'synchronisation_bonuses','switch_refills','regular_switch_refills','bonus_switch_refills',
                    'coffee_reversals','stranded_plane_events','irreversible_range_events','avoidable_immediate_losses')},
                truncations=sum(e['status']=='unentschieden_abgebrochen' for e in episodes),
                max_cpu_decision_seconds=max([e.get('max_cpu_decision_seconds',0) for e in episodes] or [0]))
        return result
    return dict(complete=True,cohort=report['config']['cohort'],games_per_case=games,
                all_cases=summary(cases),official=summary(official),
                synchronization_cases=summary([c for c in cases if 'synchronisation' in c['abilities']]),
                wind_cases=summary([c for c in cases if 'wind' in c['modules']]),
                equal_route_delta=delta,paired_stratified_bootstrap_95=[bootstrap[int(.025*repetitions)],bootstrap[int(.975*repetitions)]],
                inference_limit='Small per-case samples; paired bootstrap describes this cohort, not a per-route guarantee.',routes=route_rows)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('report',type=Path);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();result=analyze(json.loads(args.report.read_text()))
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('routes',)},indent=2))


if __name__=='__main__':main()
