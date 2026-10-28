import json
from pathlib import Path
import shutil
import subprocess
import unittest

try:
    import torch
except ImportError:
    torch=None


@unittest.skipUnless(torch is not None and shutil.which('node'),'Torch and Node required for exact policy parity')
class PublicContractModelTests(unittest.TestCase):
    def _assert_96_actual_browser_decisions_match_native(self,crew):
        from backend import bridge
        from ai.checkpoints import load_checkpoint
        from ai.public_contract import PublicContractAgent
        from ai.export_browser import _model_data
        from ai.modules import ModuleEnv
        from ai.rollout_search import GuidedBlueprint
        from ai.strategy_bridge import strategy_decision
        torch.set_num_threads(1)
        root=Path(__file__).resolve().parents[1]
        model,_=load_checkpoint(root/f'ai/releases/crew{crew}-allroutes-2026-10-26-v1/best.pt')
        frames=[];expected=[]
        for airport,cards in (('MUC',[]),('LOG_KEF_YELLOW',['adaptation']),
                              ('LOG_PRG_YELLOW',['control','working-together']),('LOG_ATL_GREEN',[])):
            env=ModuleEnv(airport,abilities=cards,clock=lambda:0.)
            env.reset(seed='train:public-js-parity:'+airport)
            agent=PublicContractAgent(airport,model)
            for ordinal in range(24):
                if env.done:env.reset(seed=f'train:public-js-parity:{airport}:{ordinal}')
                chosen=agent.select(env.view(),env.action_mask())
                bridge._spiel=env.game
                frames.append(strategy_decision(reroll_json=json.dumps(env.reroll),steps=env.steps))
                expected.append(chosen)
                env.step(chosen)
        code="""const fs=require('node:fs');global.window={};eval(fs.readFileSync(process.argv[1],'utf8'));
const f=JSON.parse(fs.readFileSync(0,'utf8')),p=window.CockpitPolicy.create(f.model,{schema:f.model.schema});
process.stdout.write(JSON.stringify(f.frames.map(d=>({chosen:p.select(d),first:p.rank(d)[0]}))));
"""
        result=subprocess.run(['node','-e',code,str(root/'frontend/web/js/ai-policy.js')],
            input=json.dumps(dict(model=_model_data(model),frames=frames)),capture_output=True,text=True,check=True)
        actual=json.loads(result.stdout)
        self.assertEqual(96,len(actual))
        self.assertEqual(expected,[row['chosen'] for row in actual])
        self.assertEqual(expected,[row['first'] for row in actual])

    def test_96_actual_browser_decisions_match_the_native_adaptive_planner(self):
        self._assert_96_actual_browser_decisions_match_native(4)

    def test_96_crew3_browser_decisions_match_the_native_adaptive_planner(self):
        self._assert_96_actual_browser_decisions_match_native(3)
