"""Mixed public play trains only learner decisions and leaves partners frozen."""
from pathlib import Path
import unittest
import torch
from ai.public_league import PublicLeagueEnv,run_team_case
from ai.checkpoints import load_checkpoint,weight_fingerprint
from ai.agents import ModelAgent
from ai.train import collect_rollout,ppo_update

SOURCE=Path('ai/releases/crew3-current-preview-v2/best.pt')

class PublicLeagueTests(unittest.TestCase):
    def setUp(self):torch.set_num_threads(1)

    def test_both_roles_keep_public_guidance_but_only_learner_actions_are_recorded(self):
        for role in ('pilot','kopilot'):
            with self.subTest(role=role):
                learner,_=load_checkpoint(SOURCE);partner,_=load_checkpoint(SOURCE)
                before=weight_fingerprint(partner);foundation=weight_fingerprint(learner.source)
                env=PublicLeagueEnv('LOG_YUL_GREEN',assistance_version=12,max_steps=256)
                env.assisted_roles=(role,)
                self.assertEqual(env.assisted_roles,('pilot','kopilot'))
                batch,records=collect_rollout(learner,env,16,seed='technical:league:'+role,
                    episodes_done=0,gamma=.995,gae_lambda=.95,uniform_mix=.03,
                    discount_unit='placement',partner=ModelAgent(partner),ai_role=role)
                self.assertEqual(sum(r['steps'] for r in records),len(batch['actions']))
                self.assertTrue(all(r['engine_decisions']==r['steps']+r['partner_decisions'] for r in records))
                self.assertGreater(sum(r['partner_decisions'] for r in records),0)
                self.assertEqual(batch['reference_masks'].shape,batch['masks'].shape)
                self.assertFalse(bool((batch['reference_masks']&~batch['masks']).any()))
                optimizer=torch.optim.Adam((p for p in learner.parameters() if p.requires_grad),lr=5e-5)
                ppo_update(learner,optimizer,batch,epochs=1,minibatch_size=32)
                self.assertEqual(weight_fingerprint(partner),before)
                self.assertEqual(weight_fingerprint(learner.source),foundation)
                self.assertTrue(all(p.grad is None for p in partner.parameters()))

    def test_team_evaluation_is_native_and_development_only(self):
        model,_=load_checkpoint(SOURCE)
        case={'airport':'LOG_YUL_GREEN','abilities':[],'modules':[]}
        row=run_team_case(model,model,case,1,14888900,duty=.6)
        self.assertTrue(row['complete']);self.assertFalse(row['release_evidence'])
        self.assertEqual(row['games'],1);self.assertEqual(len(row['episodes']),1)
        with self.assertRaises(ValueError):run_team_case(model,model,case,1,15400000,duty=.6)
        with self.assertRaises(ValueError):run_team_case(model,model,{**case,'modules':['wind']},1,14888900,duty=.6)
