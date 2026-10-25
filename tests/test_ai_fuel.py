"""Kerosene action/schema compatibility, privacy, engine parity and PPO transfer."""
from copy import deepcopy
import json
from pathlib import Path
import random
import shutil
import subprocess
import tempfile
import unittest

import torch

from backend import bridge
from ai.actions import ACTIONS, SLOTS, execute_placement
from ai.agents import ModelAgent
from ai.browser_bridge import decision
from ai.checkpoints import load_checkpoint, save_checkpoint, schema
from ai.export_browser import export_models
from ai.fuel import FUEL_ACTIONS, FUEL_SLOTS, FUEL_FEATURES, FuelEnv, fuel_capacity_mask
from ai.nn_model import ActorCritic
from ai.train_fuel import expand_base_model,freeze_legacy_policy


class FuelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_schema_prefix_and_zero_column_weight_transfer(self):
        base = ActorCritic(hidden_size=16)
        new = expand_base_model(base)
        self.assertEqual(FUEL_ACTIONS[:121], ACTIONS)
        self.assertEqual(FUEL_SLOTS[:20], SLOTS)
        self.assertEqual(FUEL_FEATURES[:349], schema()['features'])
        inputs = torch.randn(6,349)
        logits, values = base(inputs)
        extended, new_values = new(torch.cat([inputs,torch.randn(6,3)],dim=1))
        torch.testing.assert_close(logits, extended[:,:121],atol=1e-6,rtol=1e-6)
        torch.testing.assert_close(values,new_values,atol=1e-6,rtol=1e-6)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'best.pt'
            save_checkpoint(path,new,total_steps=0)
            loaded,payload=load_checkpoint(path)
            self.assertEqual(payload['schema'],schema(2))
            self.assertEqual(loaded.config,new.config)

    def test_fuel_field_paid_once_and_matches_engine(self):
        for role in ('pilot','kopilot'):
            env=FuelEnv('LOG_OSL_GREEN')
            env.reset(seed=46)
            env.game.am_zug=role
            mask=env.action_mask()
            for i in range(121,125):
                cloned=deepcopy(env.game)
                before=cloned.cockpit.kerosin
                result=execute_placement(cloned,role,FUEL_ACTIONS[i],FUEL_SLOTS)
                self.assertEqual(mask[i],result.erfolg)
                self.assertEqual(cloned.cockpit.kerosin,before-env.view()['own_dice'][i-121])
            env.step(121)
            self.assertFalse(any(env.action_mask()[121:]))
        base=FuelEnv('MUC',assistance_version=3)
        base.reset(seed=45)
        self.assertFalse(any(base.action_mask()[121:]))

    def test_last_shared_spare_and_future_fuel_are_reserved_once(self):
        env=FuelEnv('LOG_OSL_GREEN')
        env.reset(seed=46)
        view=env.view()
        view['own_dice']=[1,0,0,0]
        view['partner_remaining']=0
        view['fuel']['remaining']=8
        for i,s in enumerate(SLOTS):
            if s.target in ('ruder','triebwerk'):
                view['board'][i]={'owner':s.owner,'value':3}
        mask=[False]*125
        mask[17]=mask[121]=True
        actual=fuel_capacity_mask(view,mask)
        self.assertFalse(actual[17])
        self.assertTrue(actual[121])
        # A partner with a public spare can perform the one shared job.
        view['partner_remaining']=1
        self.assertTrue(fuel_capacity_mask(view,mask)[17])
        view['own_dice'][0]=2
        self.assertFalse(fuel_capacity_mask(view,mask)[121])

    def test_module_privacy_and_browser_parity(self):
        env=FuelEnv('LOG_OSL_GREEN',assistance_version=3)
        env.reset(seed=46)
        bridge._spiel=env.game
        actual=decision(assistance_version=3,schema_version=2)
        self.assertEqual(actual['observation'],env.observation())
        self.assertEqual(actual['action_mask'],env.action_mask())
        self.assertNotIn('own_dice',actual['public_state'])
        for die in env.game._wuerfel_liste(env.other_role(env.current_role)):
            die.augenzahl=7-die.augenzahl
        self.assertEqual(actual,decision(assistance_version=3,schema_version=2))
        with self.assertRaises(ValueError):
            decision()
        bridge.neues_spiel('LOG_HND_RED','["control"]')
        with self.assertRaises(ValueError):
            decision(schema_version=2)

    def test_new_features_receive_real_ppo_updates(self):
        from ai.train import collect_rollout,ppo_update
        env=FuelEnv('LOG_OSL_GREEN',assistance_version=3)
        model=expand_base_model(ActorCritic(hidden_size=16))
        freeze_legacy_policy(model)
        base_inputs=torch.cat([torch.randn(6,349),torch.zeros(6,3)],dim=1)
        old_logits=model(base_inputs)[0][:,:121].detach().clone()
        initial=model.encoder[0].weight[:,349:].detach().clone()
        batch,records=collect_rollout(model,env,64,seed='fuel-unit',episodes_done=0,gamma=.995,gae_lambda=.95)
        self.assertEqual(batch['observations'].shape[1],352)
        optimizer=torch.optim.Adam(model.parameters(),lr=1e-3)
        ppo_update(model,optimizer,batch,epochs=1,minibatch_size=64,clip=.2,value_coef=.5,entropy_coef=.01)
        self.assertFalse(torch.equal(initial,model.encoder[0].weight[:,349:]))
        torch.testing.assert_close(old_logits,model(base_inputs)[0][:,:121],atol=1e-6,rtol=1e-6)
        self.assertTrue(records)

    @unittest.skipUnless(shutil.which('node'),'node needed')
    def test_schema_two_js_logits_and_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            model=expand_base_model(ActorCritic(hidden_size=16))
            save_checkpoint(root/'runs/fuel/best.pt',model,train_config={'airport':'LOG_OSL_GREEN'})
            catalog=export_models(root/'runs',root/'web')
            entry=catalog['models'][0]
            data=json.loads((root/'web'/entry['url']).read_text())
            obs=torch.randn(5,352)
            masks=torch.rand(5,125)>.5
            fixture={'model':data,'catalog':{'schema':entry['schema']},'observations':obs.tolist(),'masks':masks.tolist()}
            js="""const fs=require('node:fs');global.window={};eval(fs.readFileSync(process.argv[1],'utf8'));
const f=JSON.parse(fs.readFileSync(0,'utf8')),p=window.CockpitPolicy.create(f.model,f.catalog);
process.stdout.write(JSON.stringify(f.observations.map((o,i)=>({logits:p.logits(o),choice:p.select({observation:o,action_mask:f.masks[i]})}))));"""
            answer=subprocess.run(['node','-e',js,str(Path(__file__).resolve().parents[1]/'frontend/web/js/ai-policy.js')],input=json.dumps(fixture),text=True,capture_output=True,check=True)
            rows=json.loads(answer.stdout)
            self.assertTrue(torch.allclose(model(obs)[0],torch.tensor([r['logits'] for r in rows]),atol=1e-6))
            self.assertEqual(model.act(obs,masks,deterministic=True)[0].tolist(),[r['choice'] for r in rows])


if __name__=='__main__':
    unittest.main()
