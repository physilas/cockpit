import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import torch

from ai.actions import ACTION_COUNT
from ai.checkpoints import load_checkpoint,save_checkpoint,weight_fingerprint
from ai.environment import CrewEnv
from ai.export_browser import export_models
from ai.nn_model import ActorCritic,RoleActorCritic
from ai.observation import OBSERVATION_SIZE
from ai.tactics import assisted_mask


class RoleEnsembleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def models(self):
        torch.manual_seed(92)
        pilot=ActorCritic(hidden_size=16)
        copilot=ActorCritic(hidden_size=24,hidden_layers=3)
        observations=torch.randn(12,OBSERVATION_SIZE)
        observations[:,:2]=0
        observations[:6,0]=1
        observations[6:,1]=1
        return pilot,copilot,RoleActorCritic(pilot,copilot),observations

    def test_heads_are_exact_and_survive_checkpoint_roundtrip(self):
        pilot,copilot,model,observations=self.models()
        logits,values=model(observations)
        self.assertTrue(torch.equal(logits[:6],pilot(observations[:6])[0]))
        self.assertTrue(torch.equal(values[6:],copilot(observations[6:])[1]))
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'best.pt'
            save_checkpoint(path,model,train_config={'assistance_version':6})
            restored,_=load_checkpoint(path)
            self.assertEqual(weight_fingerprint(model),weight_fingerprint(restored))
            self.assertTrue(torch.equal(logits,restored(observations)[0]))

    def test_gradients_do_not_cross_roles(self):
        pilot,copilot,model,observations=self.models()
        logits,values=model(observations[6:])
        (logits.sum()+values.sum()).backward()
        self.assertTrue(all(p.grad is None or not torch.count_nonzero(p.grad) for p in pilot.parameters()))
        self.assertTrue(any(p.grad is not None and torch.count_nonzero(p.grad) for p in copilot.parameters()))

    def test_assistance_dispatch_preserves_each_roles_profile(self):
        env=CrewEnv('LOG_HND_GREEN');env.reset(seed=5100004)
        for role,profile in [('pilot',4),('kopilot',3)]:
            env.game.am_zug=role
            view,mask=env.view(),env.action_mask()
            self.assertEqual(assisted_mask(view,mask,version=6),assisted_mask(view,mask,version=profile))

    @unittest.skipUnless(shutil.which('node'),'node required')
    def test_browser_logits_and_masked_choices_match_both_heads(self):
        _,_,model,observations=self.models()
        masks=torch.rand(12,ACTION_COUNT)>.3
        expected=model(observations)[0].detach()
        choices=model.act(observations,masks,deterministic=True)[0]
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            save_checkpoint(folder/'runs/role/best.pt',model,train_config={'assistance_version':6})
            catalog=export_models(folder/'runs',folder/'web')
            data=json.loads((folder/'web'/catalog['models'][0]['url']).read_text())
            self.assertEqual(data['format'],2)
            fixture={'catalog':catalog,'model':data,'observations':observations.tolist(),'masks':masks.tolist()}
            code="""
const fs=require('node:fs');global.window={};eval(fs.readFileSync(process.argv[1],'utf8'));
const f=JSON.parse(fs.readFileSync(0,'utf8')),p=window.CockpitPolicy.create(f.model,f.catalog);
process.stdout.write(JSON.stringify(f.observations.map((o,i)=>({logits:p.logits(o),choice:p.select({observation:o,action_mask:f.masks[i]})}))));
"""
            result=subprocess.run(['node','-e',code,str(root/'frontend/web/js/ai-policy.js')],
                input=json.dumps(fixture),text=True,capture_output=True,check=True)
            actual=json.loads(result.stdout)
            self.assertTrue(torch.allclose(expected,torch.tensor([r['logits'] for r in actual]),atol=1e-6))
            self.assertEqual(choices.tolist(),[r['choice'] for r in actual])
