from pathlib import Path
import tempfile
import unittest
import torch
from ai.crew_refresh import selection_score, prepare, SOURCES, MATRIX
from ai.module_training_eval import load_cases, case_key, balanced_cases
from ai.checkpoints import load_checkpoint, weight_fingerprint
from ai.train_crew4 import initialize_phase

class CrewRefreshTests(unittest.TestCase):
    def test_selection_weights_routes_equally_not_card_counts(self):
        cases=load_cases(MATRIX)
        rows={case_key(c):{**c,'win_rate':float(c['airport']=='LOG_ATL_YELLOW')} for c in cases}
        self.assertAlmostEqual(selection_score(rows)[0],1/21)
        with self.assertRaises(ValueError):selection_score({})
        self.assertEqual(len(balanced_cases(cases)),630)

    def test_canonical_selection_requires_complete_exact_cases(self):
        from ai.consolidate_crews import select, GROUPS
        cases=load_cases(MATRIX)
        rows={case_key(c):{**c,'win_rate':0.} for c in cases}
        report={'complete':True,'release_evidence':False,'models':{
            i:{'complete':True,'cases':rows} for group in GROUPS.values() for i in group}}
        self.assertEqual(select(report),{1:'crew1',2:'crew2-base',3:'crew3-intern',4:'crew4-old'})
        report['models']['crew4-old']['complete']=False
        with self.assertRaises(ValueError):select(report)

    def test_league_does_not_publish_identical_or_numerically_tied_models(self):
        import json
        from ai.consolidate_crews import update_crew4
        rows={case_key(c):{**c,'win_rate':.3} for c in load_cases(MATRIX)}
        report={'complete':True,'release_evidence':False,'models':{
            'baseline':{'complete':True,'weights_sha256':'same','cases':rows},
            'league':{'complete':True,'weights_sha256':'same','cases':dict(reversed(list(rows.items())))}}}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'comparison.json';path.write_text(json.dumps(report))
            self.assertFalse(update_crew4(path,root=Path(tmp))['promoted'])
            report['models']['league']['weights_sha256']='different'
            path.write_text(json.dumps(report))
            self.assertFalse(update_crew4(path,root=Path(tmp))['promoted'])

    def test_positive_league_update_replaces_only_crew4_and_preserves_archive(self):
        import json
        from ai.consolidate_crews import update_crew4
        from ai.nn_model import ActorCritic, GuidedResidualActorCritic
        from ai.checkpoints import save_checkpoint, schema, planner_fingerprint
        from ai.modules import MODULES,CARDS
        cases=load_cases(MATRIX)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);torch.manual_seed(1)
            old=GuidedResidualActorCritic(ActorCritic(489,217,8,1),489,217,8,1,4.)
            new=GuidedResidualActorCritic(ActorCritic(489,217,8,1),489,217,8,1,4.)
            config={'assistance_version':12,'schema_version':3,'supported_modules':list(MODULES),
                    'supported_cards':list(CARDS),'ability_count':'case_specific'}
            old_path=root/'ai/releases/old4/best.pt';new_path=root/'runs/new/best.pt'
            for path,model in ((old_path,old),(new_path,new)):
                save_checkpoint(path,model,train_config=config,total_steps=1)
            peers=[dict(id=f'old{i}/best.pt',name=f'Crew {i}',crew_number=i,ui_hidden=False) for i in range(1,5)]
            catalog_path=root/'frontend/web/js/ai-models.js';catalog_path.parent.mkdir(parents=True)
            catalog_path.write_text('window.COCKPIT_AI_CATALOG = '+json.dumps({'schema':schema(),'models':peers})+';')
            def evidence(model,path,wins):
                return dict(complete=True,release_evidence=False,weights_sha256=weight_fingerprint(model),
                    assistance_version=12,planner_sha256=planner_fingerprint(3),checkpoint=str(path),
                    cases={case_key(c):{**c,'games':10,'wins':wins,'win_rate':wins/10} for c in cases})
            rows={'baseline':evidence(old,old_path,0),'league':evidence(new,new_path,1)}
            comparison=root/'compare.json'
            comparison.write_text(json.dumps(dict(complete=True,release_evidence=False,models=rows)))
            (root/'compare-league.json').write_text(json.dumps(rows['league']))
            result=update_crew4(comparison,root=root)
            self.assertTrue(result['promoted'])
            actual=json.loads(catalog_path.read_text().split(' = ',1)[1].strip().rstrip(';'))['models']
            visible=[m for m in actual if not m.get('ui_hidden')]
            self.assertEqual([m['crew_number'] for m in visible],[1,2,3,4])
            for peer in peers[:3]:self.assertEqual(next(m for m in visible if m['id']==peer['id']),peer)
            self.assertTrue(next(m for m in actual if m['id']=='old4/best.pt')['ui_hidden'])
            self.assertEqual(len(visible[-1]['preview']['supported_cases']),186)
            self.assertFalse(visible[-1]['quality']['approved'])

    def test_merge_export_preserves_canonical_menu_visibility(self):
        import json
        from ai.export_browser import export_models
        from ai.nn_model import ActorCritic
        from ai.checkpoints import save_checkpoint
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);checkpoint=root/'runs/old/best.pt'
            save_checkpoint(checkpoint,ActorCritic(hidden_size=8),train_config={},total_steps=1)
            output=root/'web'
            catalog=export_models(root/'runs',output)
            catalog['models'][0]['ui_hidden']=True
            path=output/'js/ai-models.js'
            path.write_text('window.COCKPIT_AI_CATALOG = '+json.dumps(catalog)+';')
            merged=export_models(root/'runs',output,checkpoints=[checkpoint],merge=True)
            self.assertTrue(merged['models'][0]['ui_hidden'])

    def test_adapter_preserves_old_foundation_and_phase_preserves_existing_tensors(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory(dir='runs') as tmp:
            folder=Path(tmp)/'sources'
            paths=prepare(folder)
            self.assertEqual(set(paths),set(SOURCES))
            old,_=load_checkpoint('ai/releases/crew-basegame-v1/best.pt')
            new,payload=load_checkpoint(paths['crew1'])
            self.assertEqual(weight_fingerprint(new.source),weight_fingerprint(old))
            self.assertTrue(all(not p.requires_grad for p in new.source.parameters()))
            self.assertEqual(new.config['action_count'],217)
            self.assertEqual(len(payload['train_config']['supported_cases']),186)
            source,_=load_checkpoint(paths['crew3-intern'])
            phase,_,_=initialize_phase(paths['crew3-intern'],assistance_version=12,guide_margin=4)
            self.assertEqual(weight_fingerprint(source),weight_fingerprint(phase))
