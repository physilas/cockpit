import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

from backend import bridge
from ai.ability_browser import decision
from ai.browser_bridge import decision as old_decision
from ai.ability_policy import ability_inputs
from ai.modules import ModuleEnv

ROOT=Path(__file__).resolve().parents[1]


class AbilityBrowserTests(unittest.TestCase):
    def test_exact_native_inputs_and_hidden_partner_boundary(self):
        env=ModuleEnv('LOG_KUL_YELLOW',abilities=['synchronisation'])
        env.reset(seed='development:ability-browser')
        with patch.object(bridge,'_spiel',env.game):
            actual=decision(assistance_version=15,schema_version=3)
            allowed,reference,plan=ability_inputs('LOG_KUL_YELLOW',env.view(),env.action_mask())
            self.assertEqual(env.observation(),actual['observation'])
            self.assertEqual(allowed,actual['action_mask'])
            self.assertEqual(reference,actual['reference_action_mask'])
            self.assertEqual(plan,actual['public_plan'])
            self.assertNotIn('own_dice',actual['public_state'])
            for die in env.game.kopilot_wuerfel:die.augenzahl=7-die.augenzahl
            env.rng.seed(1)
            self.assertEqual(actual,decision(assistance_version=15,schema_version=3))
            with self.assertRaises(ValueError):decision(assistance_version=15,schema_version=2)
            with self.assertRaises(ValueError):decision(assistance_version=15,schema_version=3,max_steps=32)

    def test_old_bridge_profiles_are_forwarded_unchanged(self):
        env=ModuleEnv('MUC');env.reset(seed='development:ability-old-bridge')
        with patch.object(bridge,'_spiel',env.game):
            for profile in (0,12,13,14):
                self.assertEqual(old_decision(assistance_version=profile,schema_version=3),
                                 decision(assistance_version=profile,schema_version=3))

    def test_browser_import_does_not_require_torch(self):
        subprocess.run([sys.executable,'-c',"import sys; import ai.ability_browser; assert 'torch' not in sys.modules"],
                       cwd=ROOT,check=True,timeout=10)

    def test_bundle_contains_exact_old_and_new_sources(self):
        import build
        sources=json.loads((ROOT/'frontend/web/js/engine-src.js').read_text().split('const ENGINE_SRC = ',1)[1].rstrip(';\n'))
        for name in build.PYTHON_DATEIEN+['ai/ability_planner.py','ai/ability_policy.py','ai/ability_browser.py']:
            self.assertEqual((ROOT/name).read_text(),sources[name])

    def test_published_profile13_fingerprint_still_matches_its_confirmation(self):
        from ai.strategy_fingerprint import public_strategy_fingerprint
        protocol=json.loads((ROOT/'ai/releases/crew5-planner-2026-10-28-v1/confirmation-protocol.json').read_text())
        self.assertEqual(protocol['public_strategy_sha256'],public_strategy_fingerprint(13))


@unittest.skipUnless(shutil.which('node'),'Node required for portable decision parity')
class AbilityJavaScriptTests(unittest.TestCase):
    def test_actual_native_profile15_choices_match_javascript_arbitration(self):
        import torch
        from ai.ability_policy import AbilityAgent
        from ai.checkpoints import load_checkpoint
        torch.set_num_threads(1)
        model=load_checkpoint(ROOT/'ai/releases/crew5-planner-2026-10-28-v1/best.pt')[0]
        catalog=json.loads((ROOT/'frontend/web/js/ai-models.js').read_text().split(' = ',1)[1].rstrip(';\n'))
        entry=next(m for m in catalog['models'] if m['id']=='crew5-planner-2026-10-28-v1/best.pt')
        cases=[];expected=[]
        for airport,cards in [('LOG_KUL_YELLOW',['synchronisation']),('LOG_GIG_YELLOW',['control']),
                              ('LOG_KEF_YELLOW',['synchronisation']),('LOG_PRG_GREEN',['adaptation','synchronisation'])]:
            env=ModuleEnv(airport,abilities=cards,clock=lambda:0.);env.reset(seed='development:ability-parity:'+airport)
            agent=AbilityAgent(airport,model)
            with patch.object(bridge,'_spiel',env.game):
                for _ in range(8):
                    actual=decision(env.current_role,json.dumps(env.reroll),env.steps,256,15,3)
                    cases.append(actual);action=agent.select(env.view(),env.action_mask());expected.append(action)
                    env.step(action)
                    if env.done:break
        code="""const fs=require('node:fs');global.window={};eval(fs.readFileSync(process.argv[1],'utf8'));
const f=JSON.parse(fs.readFileSync(0,'utf8')),p=window.CockpitPolicy.create(f.model,{schema:f.model.schema});
process.stdout.write(JSON.stringify(f.cases.map(d=>({chosen:p.select(d),first:p.rank(d)[0]}))));"""
        fixture=dict(model=json.loads((ROOT/'frontend/web'/entry['url']).read_text()),cases=cases)
        output=subprocess.run(['node','-e',code,str(ROOT/'frontend/web/js/ai-policy.js')],
                              input=json.dumps(fixture),capture_output=True,text=True,check=True,timeout=30)
        actual=json.loads(output.stdout)
        self.assertEqual(expected,[row['chosen'] for row in actual])
        self.assertEqual(expected,[row['first'] for row in actual])
        print(f'Profile15 Python/JavaScript parity: {len(cases)} decisions')
