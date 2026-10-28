"""Publish only a complete, frozen and paired-qualified round-policy candidate."""
import argparse
import json
import math
from pathlib import Path
from .round_strategy_evaluate import SOURCES,digest,paired_statistics,freeze
from .round_strategy_training import atomic
from .round_strategy import FEATURES


def validated(report):
    if report.get('complete') is not True:raise ValueError('A complete independent comparison is required.')
    protocol=report['protocol']
    expected_protocol=freeze(Path(protocol['weights']),Path(protocol['checkpoint']),protocol['cohort'],protocol['per_route'])
    if protocol!=expected_protocol:raise ValueError('Frozen comparison protocol or inherited engine/strategy changed.')
    if not protocol['cohort'].startswith('confirmation:'):raise ValueError('Fresh confirmation cohort required.')
    if any(digest(p)!=sha for p,sha in protocol['sources'].items()) or set(protocol['sources'])!=set(SOURCES):raise ValueError('Compared sources changed.')
    if digest(protocol['weights'])!=protocol['weights_sha256'] or digest(protocol['checkpoint'])!=protocol['checkpoint_sha256']:raise ValueError('Compared model changed.')
    expected={(job['seed'],job['mode']) for job in protocol['jobs']};actual={(r['seed'],r['mode']) for r in report['records']}
    if len(actual)!=len(report['records']) or actual!=expected:raise ValueError('All declared route/mode cases, including zero wins, must remain present.')
    cases={(job['seed'],job['mode']):job['case'] for job in protocol['jobs']}
    from .module_training_eval import case_key
    for row in report['records']:
        case=cases[row['seed'],row['mode']]
        if row.get('case')!=case_key(case) or set(row.get('modules',()))!=set(case['modules']) or set(row.get('abilities',()))!=set(case['abilities']):raise ValueError('Route, modules or ability set does not match the declared comparison.')
    weights=json.loads(Path(protocol['weights']).read_text())
    if weights.get('format')!=1 or weights.get('features')!=list(FEATURES):raise ValueError('Wrong public model schema.')
    matrices=[(weights.get('hidden_weight',[]),48,len(FEATURES)),(weights.get('actor_weight',[]),11,48)]
    if any(len(matrix)!=rows or any(len(row)!=cols for row in matrix) for matrix,rows,cols in matrices):raise ValueError('Wrong round-network shape.')
    vectors=[weights.get('hidden_bias',[]),weights.get('actor_bias',[])]
    if list(map(len,vectors))!=[48,11]:raise ValueError('Wrong round-network biases.')
    values=[v for matrix,_,_ in matrices for row in matrix for v in row]+[v for row in vectors for v in row]
    if any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>100 for v in values):raise ValueError('Unsafe or nonfinite round-network parameters.')
    stats=paired_statistics(report['records'])
    if not stats['qualification_granted']:raise ValueError('No independently confirmed improvement; candidate stays unpublished.')
    return stats


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);p.add_argument('--output',type=Path,default=Path('ai/round_strategy_weights.json'));args=p.parse_args()
    if args.output.exists():raise ValueError('Do not overwrite a released round model; version the next release.')
    report=json.loads(args.report.read_text());stats=validated(report);weights=json.loads(Path(report['protocol']['weights']).read_text())
    weights['release']={'qualification_granted':True,'cohort':report['protocol']['cohort'],'report_sha256':digest(args.report),'candidate_weights_sha256':report['protocol']['weights_sha256'],'execution':'briefing-v1','games_per_mode':stats['games_per_mode'],'wins':stats['wins'],'paired_p':stats['one_sided_p'],'strata':stats['strata'],'limitation':'AI self-play only; no human win-rate or all-card-set guarantee.'}
    atomic(args.output,weights);print(json.dumps({'weights':str(args.output),'bytes':args.output.stat().st_size,'statistics':stats}))


if __name__=='__main__':main()
