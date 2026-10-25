import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import torch
from ai.checkpoints import load_checkpoint,save_checkpoint,schema
from ai.export_browser import export_models
from ai.modules import MODULE_FEATURES,MODULE_ACTIONS
from ai.nn_model import ActorCritic,ResidualActorCritic


class ResidualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1)

    def test_zero_output_branch_preserves_source_and_receives_gradients(self):
        source=ActorCritic(hidden_size=16)
        model=ResidualActorCritic(source,len(MODULE_FEATURES),len(MODULE_ACTIONS),hidden_size=32)
        observation=torch.randn(12,len(MODULE_FEATURES));mask=torch.ones(12,len(MODULE_ACTIONS),dtype=torch.bool)
        original,value=source(observation[:,:349]);actual,new_value=model(observation)
        self.assertTrue(torch.equal(original,actual[:,:121]));self.assertTrue(torch.equal(value,new_value))
        saved={k:v.clone() for k,v in source.state_dict().items()}
        actions,_,_=model.act(observation,mask)
        logp,entropy,pred=model.evaluate_actions(observation,mask,actions)
        optimizer=torch.optim.Adam(model.parameters(),lr=.001)
        (-logp.mean()+.5*pred.square().mean()-.01*entropy.mean()).backward();optimizer.step()
        self.assertTrue(any(bool(p.abs().sum()) for p in model.residual.actor.parameters()))
        for k,v in source.state_dict().items():self.assertTrue(torch.equal(v,saved[k]))
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'best.pt';save_checkpoint(path,model)
            loaded,payload=load_checkpoint(path)
            self.assertEqual(payload['schema'],schema(3))
            torch.testing.assert_close(model(observation)[0],loaded(observation)[0])

    def test_rule_pretraining_keeps_policy_and_value_unchanged(self):
        source=ActorCritic(hidden_size=16)
        model=ResidualActorCritic(source,len(MODULE_FEATURES),len(MODULE_ACTIONS),hidden_size=24)
        head=torch.nn.Linear(24,len(MODULE_ACTIONS))
        inputs=torch.randn(8,len(MODULE_FEATURES));targets=torch.randint(2,(8,len(MODULE_ACTIONS))).float()
        before=[v.detach().clone() for v in model(inputs)]
        encoder_before=model.residual.encoder[0].weight.detach().clone()
        optimizer=torch.optim.Adam([*model.residual.encoder.parameters(),*head.parameters()],lr=.01)
        loss=torch.nn.functional.binary_cross_entropy_with_logits(head(model.residual.encoder(inputs)),targets)
        loss.backward();optimizer.step()
        self.assertFalse(torch.equal(encoder_before,model.residual.encoder[0].weight))
        for a,b in zip(before,model(inputs)):self.assertTrue(torch.equal(a,b))

    @unittest.skipUnless(shutil.which('node'),'node required')
    def test_browser_residual_composition_matches_torch(self):
        model=ResidualActorCritic(ActorCritic(hidden_size=16),len(MODULE_FEATURES),len(MODULE_ACTIONS),hidden_size=24)
        torch.nn.init.normal_(model.residual.actor.weight,std=.05)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);save_checkpoint(root/'runs/detail/best.pt',model)
            catalog=export_models(root/'runs',root/'web');entry=catalog['models'][0]
            data=json.loads((root/'web'/entry['url']).read_text())
            obs=torch.randn(10,len(MODULE_FEATURES));masks=torch.rand(10,len(MODULE_ACTIONS))>.3
            fixture={'model':data,'catalog':{'schema':entry['schema']},'observations':obs.tolist(),'masks':masks.tolist()}
            code="""const fs=require('node:fs');global.window={};eval(fs.readFileSync(process.argv[1],'utf8'));
const f=JSON.parse(fs.readFileSync(0,'utf8')),p=window.CockpitPolicy.create(f.model,f.catalog);
process.stdout.write(JSON.stringify(f.observations.map((o,i)=>({logits:p.logits(o),choice:p.select({observation:o,action_mask:f.masks[i]})}))));"""
            result=subprocess.run(['node','-e',code,str(Path(__file__).resolve().parents[1]/'frontend/web/js/ai-policy.js')],input=json.dumps(fixture),text=True,capture_output=True,check=True)
            actual=json.loads(result.stdout)
            torch.testing.assert_close(model(obs)[0],torch.tensor([r['logits'] for r in actual]),atol=2e-6,rtol=1e-6)
            self.assertEqual(model.act(obs,masks,deterministic=True)[0].tolist(),[r['choice'] for r in actual])


if __name__=='__main__':unittest.main()
