"""Validated, additive profile-15 preview publication with all-case evidence."""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path

from .ability_fingerprint import ROOT, SOURCES, ability_fingerprint
from .ability_compare import freeze
from .checkpoints import load_checkpoint, save_checkpoint, weight_fingerprint
from .export_browser import export_models
from .module_training_eval import case_key
from .modules import CARDS, MODULES
from .preview_matrix_eval import catalogue_cases
from .publish import portable_config


def prepare(source, folder):
    folder = Path(folder)
    if folder.exists():raise ValueError('Candidate folder already exists.')
    model,payload = load_checkpoint(source)
    config = deepcopy(payload['train_config'])
    for key in ('quality','preview','recommended','display_name','name','id','release_id','approved','crew_number','ui_hidden'):
        config.pop(key,None)
    cases = sorted(catalogue_cases(),key=case_key)
    config.update(assistance_version=15,schema_version=3,action_mask_version=2,max_steps=256,
        planner_sha256=ability_fingerprint(),source_checkpoint=str(source),
        source_weights_sha256=weight_fingerprint(model),new_tensor_training=False,
        phase_kind='public_ability_and_wind_horizon',recommended=False,
        publication_status='candidate_pending_independent_confirmation',
        supported_modules=list(MODULES),supported_cards=list(CARDS),ability_count='case_specific',
        supported_cases=[dict(airport=c['airport'],abilities=c['abilities']) for c in cases],
        supported_airports=sorted({c['airport'] for c in cases}))
    target=folder/'best.pt'
    save_checkpoint(target,model,train_config=portable_config(config,ROOT),total_steps=payload.get('total_steps',0))
    return target


def compare_totals(report):
    result={}
    for mode in ('baseline','candidate'):
        rows=[r for r in report['results'].values() if r['mode']==mode]
        episodes=[e for row in rows for e in row['episodes']]
        by_route={}
        for row in rows:by_route.setdefault(row['case']['airport'],[]).append(row['win_rate'])
        result[mode]=dict(games=len(episodes),wins=sum(e['status']=='gewonnen' for e in episodes),
            equal_route_win_rate=sum(sum(v)/len(v) for v in by_route.values())/len(by_route),
            synchronisation_bonuses=sum(e['synchronisation_bonuses'] for e in episodes),
            switch_refills=sum(e['switch_refills'] for e in episodes),
            coffee_reversals=sum(e['coffee_reversals'] for e in episodes),
            stranded_plane_events=sum(e['stranded_plane_events'] for e in episodes),
            avoidable_immediate_losses=sum(e['avoidable_immediate_losses'] for e in episodes),
            truncations=sum(e['status']=='unentschieden_abgebrochen' for e in episodes))
    return result


def validate(report, manifest):
    expected=freeze(manifest['checkpoint'],manifest['games'],manifest['cohort'],manifest['focus'],manifest['confirmation'],manifest.get('baseline_report'))
    if manifest!=expected or report.get('config')!=manifest:
        raise ValueError('Current candidate/source/evaluation must match the frozen evidence.')
    if not report.get('complete') or not report.get('release_evidence') or report.get('reused_previous_baseline_games',0) or not manifest['confirmation'] or manifest['focus'] or manifest['games']<5:
        raise ValueError('A complete independent confirmation with >=5 games on every case is required.')
    cases=sorted(catalogue_cases(),key=case_key)
    if manifest['cases']!=cases or len(report['results'])!=2*len(cases):
        raise ValueError('Missing route/card cases, including zero-win cases.')
    for case in cases:
        pair=[]
        for mode in ('baseline','candidate'):
            row=report['results'][case_key(case)+'/'+mode]
            episodes=row['episodes']
            seeds=[f"{manifest['cohort']}:{case_key(case)}:{i}" for i in range(manifest['games'])]
            if (row['case']!=case or row['mode']!=mode or row['games']!=manifest['games']
                    or len(episodes)!=manifest['games'] or [e['seed'] for e in episodes]!=seeds
                    or row['wins']!=sum(e['status']=='gewonnen' for e in episodes)
                    or row['win_rate']!=row['wins']/row['games']):
                raise ValueError('Inconsistent or unpaired game evidence.')
            method=row.get('execution_method')
            identity_eligible='wind' not in case['modules'] and 'synchronisation' not in case['abilities'] and 'realtime' not in case['modules']
            if method not in ('played','identical_policy_reuse') or method=='identical_policy_reuse' and (mode!='candidate' or not identity_eligible):
                raise ValueError('Invalid analytical policy-identity reuse.')
            pair.append(episodes)
        candidate_row=report['results'][case_key(case)+'/candidate']
        if candidate_row['execution_method']=='identical_policy_reuse' and pair[0]!=pair[1]:
            raise ValueError('Identity reuse must retain exact control episode evidence.')
        if 'wind' not in case['modules'] and 'synchronisation' not in case['abilities']:
            # Runtime varies; the complete sequence length, outcome and counters may not.
            for a,b in zip(*pair):
                for key in ('status','reason','decisions','coffee_reversals','synchronisation_bonuses','switch_refills'):
                    if a.get(key)!=b.get(key):raise ValueError('Unchanged case regressed: '+case_key(case)+'/'+key)
    totals=compare_totals(report)
    a,b=totals['baseline'],totals['candidate']
    if (b['wins']<a['wins']+5 or b['equal_route_win_rate']<=a['equal_route_win_rate']
            or b['avoidable_immediate_losses'] or b['truncations']):
        raise ValueError('The frozen confirmation did not pass the predeclared improvement gate.')
    return totals


def publish(manifest_path, report_path, release_id='crew6-abilities-2026-10-28-v1'):
    manifest=json.loads(Path(manifest_path).read_text());report=json.loads(Path(report_path).read_text())
    totals=validate(report,manifest)
    model,payload=load_checkpoint(manifest['checkpoint'])
    if (payload['train_config'].get('assistance_version')!=15
            or payload['train_config'].get('planner_sha256')!=ability_fingerprint()):
        raise ValueError('Prepare a profile-15 candidate before confirmation.')
    folder=ROOT/'ai/releases'/release_id
    if folder.exists():raise ValueError('Do not overwrite a release.')
    old_catalog=json.loads((ROOT/'frontend/web/js/ai-models.js').read_text().split(' = ',1)[1].rstrip(';\n'))
    previous=[m for m in old_catalog['models'] if not m.get('ui_hidden')]
    folder.mkdir(parents=True)
    config=deepcopy(payload['train_config'])
    preview=dict(enabled=True,user_requested=True,evaluation_kind='development_with_independent_confirmation',
                 evaluation=f'ai/releases/{release_id}/development.json',positive_only=False,
                 supported_cases=[],case_results={})
    for case in manifest['cases']:
        row=report['results'][case_key(case)+'/candidate']
        preview['supported_cases'].append(dict(airport=case['airport'],abilities=case['abilities']))
        preview['case_results'][case_key(case)]={key:row[key] for key in ('games','wins','win_rate')}
    config.update(display_name='Crew 6 · Koordinator',crew_number=6,ui_hidden=False,recommended=False,
                  publication_status='experimental_preview',preview=preview,
                  quality=dict(approved=False,reason='User-requested preview with independent paired confirmation; no per-route guarantee.'))
    payload['train_config']=portable_config(config,ROOT)
    import torch
    target=folder/'best.pt';torch.save(payload,target)
    (folder/'development.json').write_text(json.dumps(dict(complete=True,assistance_version=15,max_steps=256,
        weights_sha256=weight_fingerprint(model),planner_sha256=ability_fingerprint(),cases={
            case_key(c):report['results'][case_key(c)+'/candidate'] for c in manifest['cases']}),indent=2)+'\n')
    (folder/'confirmation-protocol.json').write_bytes(Path(manifest_path).read_bytes())
    (folder/'comparison.json').write_bytes(Path(report_path).read_bytes())
    (folder/'previous-crews.json').write_text(json.dumps(previous,indent=2)+'\n')
    (folder/'comparison-summary.json').write_text(json.dumps(totals,indent=2)+'\n')
    (folder/'confirmation-input.pt.gz').write_bytes(gzip.compress(Path(manifest['checkpoint']).read_bytes(),mtime=0))
    (folder/'README.md').write_text('# Crew 6 · Koordinator\n\nNeue öffentliche Planung für Synchronisation und Wind; unveränderte Gewichte von Crew 5/4. '
        'Keine neu trainierten neuronalen Gewichte und keine Freigabe einer Mindestquote auf jeder Route. '
        'Alle alten Crews bleiben unverändert auswählbar.\n\n'
        'Die Bonusplanung zählt ungewürfelte Zusatzwürfel niemals als sichere Ressourcen. '
        'Der Windhorizont ist eine begrenzte optimistische Planungspräferenz; unbekannte künftige Würfe bleiben unbekannt. '
        'Bestätigung und alle Einzelfälle einschließlich Nullquoten stehen in den JSON-Dateien.\n')
    catalog=export_models(ROOT/'ai/releases',ROOT/'frontend/web',checkpoints=[target],merge=True)
    old_by_id={m['id']:m for m in previous}
    for model in catalog['models']:
        if model['id'] in old_by_id and model!=old_by_id[model['id']]:
            raise RuntimeError('Publication changed a previous crew.')
    return target,totals
