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
