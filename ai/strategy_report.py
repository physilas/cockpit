"""Paired, route-balanced analysis of a complete research comparison.

All card cases remain visible, including zero-win cases. Intervals describe
the fixed development cohort, without selection/multiple-comparison claims.
This command never selects, publishes or mutates a policy.
"""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
from statistics import mean, variance

from .module_training_eval import case_key


def paired_analysis(report, baseline, candidate):
    if report.get('complete') is not True or baseline==candidate:
        raise ValueError('Use a complete paired comparison and distinct modes.')
    cases=report['config']['cases']
    if len({case_key(c) for c in cases})!=len(cases):
        raise ValueError('Duplicate case in comparison.')
    by_route=defaultdict(list)
    for case in cases:
        key=case_key(case)
        rows=[]
        for mode in (baseline,candidate):
            row=report['results'][key+'/'+mode]
            records=row['episodes']
            indexed={r['seed']:r for r in records}
            if len(indexed)!=len(records) or len(records)!=row['games'] or row['case_key']!=key:
                raise ValueError('Invalid episode identity/count.')
            rows.append(indexed)
        if not rows[0] or rows[0].keys()!=rows[1].keys():
            raise ValueError('Each policy must play the same nonempty seed cohort.')
        pairs=list(zip((rows[0][s] for s in sorted(rows[0])),(rows[1][s] for s in sorted(rows[1]))))
        differences=[int(b['status']=='gewonnen')-int(a['status']=='gewonnen') for a,b in pairs]
        by_route[case['airport']].append(dict(case_key=key,abilities=case['abilities'],
            baseline_wins=sum(a['status']=='gewonnen' for a,b in pairs),
            candidate_wins=sum(b['status']=='gewonnen' for a,b in pairs),games=len(pairs),
            delta=mean(differences),variance_of_mean=variance(differences)/len(pairs) if len(pairs)>1 else None,
            improved=sum(d>0 for d in differences),regressed=sum(d<0 for d in differences),
            baseline_round=mean(a['round'] for a,b in pairs),candidate_round=mean(b['round'] for a,b in pairs),
            **{mode+'_'+metric:sum(r.get(metric,0) for r in rows[i].values())
               for i,mode in enumerate(('baseline','candidate'))
               for metric in ('avoidable_immediate_losses','stranded_plane_events','irreversible_range_events',
                              'coffee_reversals','decisions','decision_seconds')}))
    routes={}
    variance_total=0.
    intervals_available=True
    for airport,entries in sorted(by_route.items()):
        count=len(entries)
        routes[airport]=dict(cases=count,games=sum(x['games'] for x in entries),
            baseline_wins=sum(x['baseline_wins'] for x in entries),candidate_wins=sum(x['candidate_wins'] for x in entries),
            baseline_rate=mean(x['baseline_wins']/x['games'] for x in entries),
            candidate_rate=mean(x['candidate_wins']/x['games'] for x in entries),
            paired_delta=mean(x['delta'] for x in entries),
            baseline_round=mean(x['baseline_round'] for x in entries),candidate_round=mean(x['candidate_round'] for x in entries),
            **{metric:sum(x[metric] for x in entries) for metric in entries[0]
               if metric.startswith(('baseline_','candidate_')) and metric not in
               ('baseline_wins','candidate_wins','baseline_round','candidate_round')},
            exact_cases=entries)
        intervals_available &= all(x['variance_of_mean'] is not None for x in entries)
        variance_total+=sum(x['variance_of_mean'] or 0 for x in entries)/count**2
    delta=mean(r['paired_delta'] for r in routes.values())
    se=math.sqrt(variance_total)/len(routes)
    return dict(complete=True,release_evidence=False,qualification_used=False,
        baseline=baseline,candidate=candidate,route_count=len(routes),case_count=len(cases),
        baseline_route_mean=mean(r['baseline_rate'] for r in routes.values()),
        candidate_route_mean=mean(r['candidate_rate'] for r in routes.values()),paired_route_delta=delta,
        descriptive_normal_interval=[delta-1.96*se,delta+1.96*se] if intervals_available else None,
        interval_limit='Fixed development cohort; independent seed-pairs within each case assumed. No selection or multiple-comparison correction.',
        improved=sum(x['improved'] for entries in by_route.values() for x in entries),
        regressed=sum(x['regressed'] for entries in by_route.values() for x in entries),routes=routes)


def markdown(data):
    lines=['# Routenvergleich', '',
        f"{data['baseline']} → {data['candidate']}; {data['route_count']} Routen, {data['case_count']} konkrete Fälle.",
        f"Gleichgewichtetes Routenmittel: {data['baseline_route_mean']:.1%} → {data['candidate_route_mean']:.1%}.",
        'Entwicklungsevidenz; keine unabhängige Qualifikation.', '',
        '| Route | Fälle | Siege vorher | Siege nachher | Spiele je Spieler | Runde vorher → nachher |',
        '|---|---:|---:|---:|---:|---:|']
    for airport,r in data['routes'].items():
        lines.append(f"| {airport} | {r['cases']} | {r['baseline_wins']} | {r['candidate_wins']} | {r['games']} | {r['baseline_round']:.2f} → {r['candidate_round']:.2f} |")
    return '\n'.join(lines)+'\n'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('report',type=Path)
    p.add_argument('--baseline',default='shield')
    p.add_argument('--candidate',default='contract')
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.output.exists():
        p.error('Preserve earlier analyses; use a new output path.')
    data=paired_analysis(json.loads(args.report.read_text()),args.baseline,args.candidate)
    args.output.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    args.output.with_suffix('.md').write_text(markdown(data))
    print(markdown(data))


if __name__=='__main__':
    main()
