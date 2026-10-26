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
        selection[str(crew)]={'candidate':identity,'checkpoint':checkpoint.relative_to(root).as_posix(),
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

def update_crew4(comparison,*,release_id='crew4-allroutes-2026-10-26-v2',root=ROOT):
    report=json.loads(Path(comparison).read_text())
    if report.get('complete') is not True or set(report.get('models',{}))!={'baseline','league'}:
        raise ValueError('A complete paired baseline/league comparison is required.')
    baseline,candidate=report['models']['baseline'],report['models']['league']
    expected={case_key(c) for c in load_cases(MATRIX)}
    if any(row.get('complete') is not True or set(row['cases'])!=expected for row in (baseline,candidate)):
        raise ValueError('Both players need all 186 cases.')
    scores={name:list(selection_score(row['cases'])) for name,row in report['models'].items()}
    delta=next((a-b for a,b in zip(scores['league'],scores['baseline']) if abs(a-b)>1e-12),0.)
    if candidate['weights_sha256']==baseline['weights_sha256'] or delta<=0:
        return dict(promoted=False,scores=scores,reason='No fresh advantage over the published baseline.')
    evidence=Path(comparison).with_name(Path(comparison).stem+'-league.json')
    if json.loads(evidence.read_text())!=candidate:raise ValueError('Evidence mismatch.')
    catalog_path=root/'frontend/web/js/ai-models.js'
    old=json.loads(catalog_path.read_text().split(' = ',1)[1].strip().rstrip(';'))
    visible=[m for m in old['models'] if not m.get('ui_hidden')]
    if len(visible)!=4 or {m.get('crew_number') for m in visible}!={1,2,3,4}:
        raise ValueError('Preserve exactly four canonical crews.')
    published=next(m for m in visible if m['crew_number']==4)
    from .checkpoints import load_checkpoint,weight_fingerprint
    if weight_fingerprint(load_checkpoint(root/'ai/releases'/published['id'])[0])!=baseline['weights_sha256']:
        raise ValueError('Baseline is not the currently published Crew 4.')
    checkpoint,catalog=publish_preview(candidate['checkpoint'],evidence,release_id,'Crew 4',root=root)
    new_id=release_id+'/best.pt'
    for model in catalog['models']:
        if model['id']==published['id']:model['ui_hidden']=True
        if model['id']==new_id:model.update(ui_hidden=False,crew_number=4,recommended=False)
    catalog['models'].sort(key=lambda m:(m.get('ui_hidden',True),m.get('crew_number',999)))
    catalog_path.write_text('/* AUTO-GENERATED; canonical menu selection by ai.consolidate_crews */\nwindow.COCKPIT_AI_CATALOG = '+json.dumps(catalog,ensure_ascii=False,separators=(',',':'))+';\n')
    selection=dict(promoted=True,scores=scores,previous_id=published['id'],new_id=new_id,
       comparison=str(comparison),release_evidence=False)
    (checkpoint.parent/'selection.json').write_text(json.dumps(selection,indent=2)+'\n')
    (checkpoint.parent/'README.md').write_text('# Crew 4 · Partnerliga\n\n'
       'Neue Entwicklungsvorschau nach gemischtem Training mit Crews 1/2/3 und Selbstspiel in beiden Rollen.\n'
       'Alle 21 Standardrouten/186 Kartenfälle, einschließlich Nullquoten.\n'
       'Vorab gewählter Trainingsstand; nur bei frischem Vorteil über veröffentlichter Crew 4 übernommen.\n'
       'Einzelquoten in development.json, keine unabhängige Qualifikation.\n')
    return selection

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('comparison',type=Path)
    a=p.parse_args();print(json.dumps(consolidate(a.comparison),indent=2))
if __name__=='__main__':main()
