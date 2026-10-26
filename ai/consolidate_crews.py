"""Publish one empirically selected preview per Crew, with all official cases.

Old model records, files, approvals and recorded evidence remain intact. Only
menu visibility changes. The new broad previews have no inherited approval.
"""
import argparse
import json
from pathlib import Path
from .crew_refresh import selection_score, MATRIX, ROOT
from .module_training_eval import load_cases, case_key
from .publish import publish_preview

GROUPS={1:('crew1',),2:('crew2-base','crew2-fuel'),3:('crew3-intern','crew3-leak'),
        4:('crew4-old','crew4-trained')}

def select(report):
    if report.get('complete') is not True or report.get('release_evidence') is not False:
        raise ValueError('Only complete development comparisons are selectable.')
    expected={case_key(c) for c in load_cases(MATRIX)}
    chosen={}
    for crew,candidates in GROUPS.items():
        for identity in candidates:
            row=report['models'][identity]
            if row.get('complete') is not True or set(row['cases'])!=expected:
                raise ValueError('All 186 official cases are required for every candidate.')
        # Exact ties retain the earlier historical candidate, not a post-hoc latest.
        chosen[crew]=max(candidates,key=lambda i:selection_score(report['models'][i]['cases']))
    return chosen

def consolidate(comparison,*,suffix='2026-10-26-v1',root=ROOT):
    report=json.loads(Path(comparison).read_text());chosen=select(report)
    catalog_path=root/'frontend/web/js/ai-models.js'
    previous=json.loads(catalog_path.read_text().split(' = ',1)[1].strip().rstrip(';'))
    old_ids={m['id'] for m in previous['models']};canonical=[];selection={}
    for crew,identity in chosen.items():
        row=report['models'][identity]
        release_id=f'crew{crew}-allroutes-{suffix}'
        evidence=Path(comparison).with_name(Path(comparison).stem+'-'+identity+'.json')
        if json.loads(evidence.read_text())!=row:raise ValueError('Separate evidence differs from comparison.')
        checkpoint,catalog=publish_preview(row['checkpoint'],evidence,release_id,f'Crew {crew}',root=root)
        canonical.append(release_id+'/best.pt')
        selection[str(crew)]={'candidate':identity,'checkpoint':str(checkpoint),
          'score':list(selection_score(row['cases'])),'new_release':release_id,
          'development_only':True,'cases':186,'routes':21}
        (checkpoint.parent/'selection.json').write_text(json.dumps({
          'selection_rule':report['selection'],'selected':selection[str(crew)],
          'candidates':{i:{'score':report['models'][i]['selection_score'],
                            'checkpoint':report['models'][i]['checkpoint']} for i in GROUPS[crew]},
          'comparison':str(comparison),'release_evidence':False},indent=2)+'\n')
        (checkpoint.parent/'README.md').write_text(f'# Crew {crew}\n\n'
          'Eine sichtbare Version, alle 21 Standardrouten mit 186 erlaubten Kartenfällen.\n'
          'Entwicklungsvorschau: auch Nullquoten sind auf Nutzerwunsch auswählbar.\n'
          'Auswahl nach gleichgewichteten Routenmitteln, Grundspielmittel als Tie-Break.\n'
          'Einzelwerte in development.json; keine unabhängige Qualifikation.\n'
          'Höhere Crew-Nummer garantiert keine höhere Spielstärke auf jeder Strecke.\n')
    raw=catalog_path.read_text();catalog=json.loads(raw.split(' = ',1)[1].strip().rstrip(';'))
    if not old_ids.issubset({m['id'] for m in catalog['models']}):raise RuntimeError('Historical records disappeared.')
    for model in catalog['models']:
        model['ui_hidden']=model['id'] not in canonical
        if model['id'] in canonical:
            model['crew_number']=canonical.index(model['id'])+1
            model['recommended']=model['crew_number']==1
    catalog['models'].sort(key=lambda m:(m['ui_hidden'],m.get('crew_number',999)))
    catalog_path.write_text('/* AUTO-GENERATED; canonical menu selection by ai.consolidate_crews */\nwindow.COCKPIT_AI_CATALOG = '+json.dumps(catalog,ensure_ascii=False,separators=(',',':'))+';\n')
    return selection

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('comparison',type=Path)
    a=p.parse_args();print(json.dumps(consolidate(a.comparison),indent=2))
if __name__=='__main__':main()
