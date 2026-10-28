"""Prepare a separate public-policy candidate and publish only full case evidence.

Old checkpoints/catalogue entries survive. Source tensors are never called
newly trained when only the public planning policy changed.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path

import torch

from .checkpoints import load_checkpoint,save_checkpoint,weight_fingerprint
from .export_browser import export_models
from .module_training_eval import case_key
from .modules import CARDS,MODULES
from .preview_matrix_eval import catalogue_cases
from .publish import portable_config,publish_preview
from .strategy_confirmation import check_manifest,file_sha
from .strategy_fingerprint import public_strategy_fingerprint,ROOT


def prepare(source,folder,profile):
    folder=Path(folder)
    if folder.exists() or profile not in (13,14):raise ValueError('Use a new folder and public profile13/14.')
    model,payload=load_checkpoint(source)
    original=weight_fingerprint(model)
    config=deepcopy(payload['train_config'])
    for key in ('quality','preview','recommended','display_name','name','id','release_id','approved'):
        config.pop(key,None)
    cases=catalogue_cases()
    config.update(phase_kind='new_public_whole_hand_strategy' if profile==13 else 'new_public_coherent_neural_strategy',
        source_checkpoint=str(source),source_weights_sha256=original,source_phase_steps=payload.get('total_steps',0),
        assistance_version=profile,schema_version=3,action_mask_version=2,
        max_steps=256,
        planner_sha256=public_strategy_fingerprint(profile),supported_modules=list(MODULES),supported_cards=list(CARDS),
        ability_count='case_specific',supported_cases=[{'airport':r['airport'],'abilities':r['abilities']} for r in cases],
        supported_airports=sorted({r['airport'] for r in cases}),recommended=False,
        publication_status='frozen_candidate_pending_confirmation',
        new_tensor_training_in_this_preparation=False,new_environment_decisions_in_this_preparation=0)
    config=portable_config(config,ROOT)
    folder.mkdir(parents=True)
    target=folder/'best.pt'
    save_checkpoint(target,model,train_config=config,total_steps=payload.get('total_steps',0),
                    module_training_steps=payload.get('module_training_steps',0),
                    inherited_imitation_rows_seen=payload.get('imitation_rows_seen',0))
    if weight_fingerprint(load_checkpoint(target)[0])!=original:raise RuntimeError('Candidate preparation changed tensors.')
    (folder/'preparation.json').write_text(json.dumps(dict(source=str(source),profile=profile,
        weights_sha256=original,tensor_values_changed=False,new_training_decisions=0,
        planner_sha256=config['planner_sha256'],cases=len(cases)),indent=2)+'\n')
    return target


def finalize(manifest_path,evidence_path,release_id,name,crew_number):
    manifest=json.loads(Path(manifest_path).read_text());check_manifest(manifest)
    evidence=json.loads(Path(evidence_path).read_text())
    expected={case_key(r) for r in catalogue_cases()}
    if (evidence.get('complete') is not True or evidence.get('release_evidence') is not False
            or evidence.get('qualification_used') is not True or evidence.get('qualification_granted') is not False
            or evidence.get('frozen_manifest_sha256')!=file_sha(manifest_path)
            or set(evidence.get('cases',{}))!=expected
            or any(r.get('games')!=manifest['games'] for r in evidence['cases'].values())):
        raise ValueError('Finalization requires the complete frozen confirmation for all192 cases, including zero wins.')
    target,catalog=publish_preview(manifest['candidate_checkpoint'],evidence_path,release_id,name)
    payload=torch.load(target,map_location='cpu',weights_only=True)
    payload['train_config'].update(recommended=True,crew_number=crew_number,ui_hidden=False)
    torch.save(payload,target)
    catalog=export_models(ROOT/'ai/releases',ROOT/'frontend/web',checkpoints=[target],merge=True)
    description=('Öffentlicher Handplaner' if manifest['profile']==13 else 'Kohärente neuronale Crew')
    tensor_note=('Für Profil13 sind die NN-Tensoren die unveränderte dokumentierte Quelle; '
                 'der neue Teil ist die gemeinsame physikalische Handplanung und Arbitration.'
                 if manifest['profile']==13 else 'NN-Tensoren und Lernmetadaten stammen aus der dokumentierten Quelle.')
    (target.parent/'README.md').write_text(f'# {name}\n\n'
        f'{description} für alle27 registrierten Routen und192 konkreten Kartenfällen.\n'
        'Eigenständige Crew; die bisherigen Modelle und Spielstände bleiben erhalten.\n\n'
        'Die Planung verwendet ausschließlich eigene Würfel und öffentliche Informationen. '
        'Verdeckte Partnerwürfel werden durch ein ausdrücklich angenähertes Fair-Hand-Modell beschrieben. '
        'Die echte Partnerhand und zukünftige echte Zufallszahlen werden nicht gelesen.\n\n'
        f'{tensor_note}\n\n'
        f"Eingefrorene unabhängige Bestätigung: {manifest['games']} Partien je Fall, "
        'alle Einzelfälle einschließlich Nullquoten in development.json. '
        'Entwicklungsvorschau mit unabhängiger Bestätigung; keine Freigabe einer Mindestquote pro Route '
        'und keine Zusage menschlicher Gewinnraten.\n\n'
        f"Quelle: `{manifest['candidate_checkpoint']}`. Öffentliche Strategie: "
        f"`{manifest['public_strategy_sha256']}`.\n")
    (target.parent/'confirmation-protocol.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return target,catalog


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('prepare','finalize'))
    p.add_argument('--source',default='ai/releases/crew4-allroutes-2026-10-26-v1/best.pt')
    p.add_argument('--folder',type=Path);p.add_argument('--profile',type=int,choices=(13,14),default=13)
    p.add_argument('--manifest',type=Path);p.add_argument('--evidence',type=Path)
    p.add_argument('--release-id',default='crew5-planner-2026-10-28-v1')
    p.add_argument('--name',default='Crew 5 · Navigator');p.add_argument('--crew-number',type=int,default=5)
    args=p.parse_args()
    if args.action=='prepare':
        if args.folder is None:p.error('A new candidate folder is required.')
        print(prepare(args.source,args.folder,args.profile))
    else:
        if args.manifest is None or args.evidence is None or args.crew_number<1:p.error('Manifest, full evidence and Crew number are required.')
        print(finalize(args.manifest,args.evidence,args.release_id,args.name,args.crew_number)[0])


if __name__=='__main__':main()
