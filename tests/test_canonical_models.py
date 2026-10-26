"""Actual published tensor/browser parity; technical states, not win evidence."""
import json
from pathlib import Path
import subprocess
import unittest
import torch
from ai.checkpoints import load_checkpoint
from ai.modules import ModuleEnv

ROOT=Path(__file__).resolve().parents[1]

class CanonicalModelTests(unittest.TestCase):
    def test_actual_four_exports_match_pytorch_and_case_contract(self):
        torch.set_num_threads(1)
        catalog=json.loads((ROOT/'frontend/web/js/ai-models.js').read_text().split(' = ',1)[1].strip().rstrip(';'))
        models=[m for m in catalog['models'] if not m.get('ui_hidden') and (m.get('preview',{} ) or {}).get('enabled')]
        self.assertEqual([m['name'] for m in models],['Crew 1','Crew 2','Crew 3','Crew 4'])
        total=0
        for entry in models:
            with self.subTest(crew=entry['name']):
                self.assertEqual(len(entry['supported_airports']),21)
                self.assertEqual(len(entry['preview']['supported_cases']),186)
                model,payload=load_checkpoint(ROOT/'ai/releases'/entry['id'])
                observations=[];masks=[];references=[]
                for airport,cards in [('LOG_YUL_GREEN',[]),('LOG_ATL_GREEN',[]),
                    ('LOG_ATL_YELLOW',['working-together']),('LOG_KEF_YELLOW',['adaptation']),
                    ('LOG_GIG_YELLOW',['control']),('LOG_PBH_BLACK',['control','mastery'])]:
                    env=ModuleEnv(airport,abilities=cards,assistance_version=12,max_steps=256)
                    _,info=env.reset(seed='technical:canonical-browser:'+entry['name']+airport)
                    for _ in range(4):
                        observations.append(env.observation());masks.append(info['action_mask']);references.append(info['reference_action_mask'])
                        with torch.no_grad():action=model.act(torch.tensor(observations[-1]),masks[-1],deterministic=True,reference_mask=references[-1])[0].item()
                        _,_,_,_,info=env.step(action)
                        if env.done:break
                obs=torch.tensor(observations);ref=torch.tensor(references,dtype=torch.bool)
                with torch.no_grad():expected=model.policy_output(obs,ref)[0]
                fixture={'data':json.loads((ROOT/'frontend/web'/entry['url']).read_text()),
                    'observations':observations,'masks':masks,'references':references}
                code="""
const fs=require('node:fs');global.window={};eval(fs.readFileSync(process.argv[1],'utf8'));
const f=JSON.parse(fs.readFileSync(0,'utf8')),p=window.CockpitPolicy.create(f.data,{schema:f.data.schema});
process.stdout.write(JSON.stringify(f.observations.map((o,i)=>({logits:p.logits(o,f.references[i]),choice:p.select({observation:o,action_mask:f.masks[i],reference_action_mask:f.references[i]})}))));
"""
                output=subprocess.run(['node','-e',code,str(ROOT/'frontend/web/js/ai-policy.js')],input=json.dumps(fixture),capture_output=True,text=True,check=True)
                actual=json.loads(output.stdout);tensor=torch.tensor([r['logits'] for r in actual])
                self.assertTrue(torch.allclose(expected,tensor,atol=2e-5,rtol=1e-5))
                choices=expected.masked_fill(~torch.tensor(masks,dtype=torch.bool),-float('inf')).argmax(-1).tolist()
                self.assertEqual(choices,[r['choice'] for r in actual]);total+=len(observations)
        print(f'Browser/PyTorch canonical parity: {total} technical decisions')
