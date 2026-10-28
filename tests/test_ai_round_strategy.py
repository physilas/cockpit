import copy
import json
import random
import unittest
from pathlib import Path
import torch
from ai.briefing import validate_plan
from ai.round_strategy import FEATURES,HEADS,OFFSETS,OUTPUTS,encode,inputs,choose,logits
from ai.round_strategy_training import RoundActor,sample,update
from ai.modules import ModuleEnv
from ai.preview_matrix_eval import catalogue_cases


class RoundStrategyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1)

    def test_all_route_card_cases_have_finite_public_features_and_legal_goals(self):
        for case in catalogue_cases():
            env=ModuleEnv(case['airport'],abilities=case['abilities'],clock=lambda:0.)
            env.reset(seed='round-feature-coverage');state=env.game.zustand()
            x,mask,prior=inputs(state)
            self.assertEqual(len(FEATURES),len(x));self.assertEqual(OUTPUTS,len(mask));self.assertEqual(3,sum(prior))
            self.assertEqual(choose(state),validate_plan(choose(state),state))

    def test_hidden_dice_rng_and_identity_do_not_change_policy_inputs(self):
        env=ModuleEnv('LOG_YUL_GREEN');env.reset(seed='round-public-privacy');state=env.game.zustand()
        altered={**state,'pilot_wuerfel':[6]*4,'kopilot_wuerfel':[1]*4,'szenario_id':'different name','timer_deadline_ms':5,'server_time_ms':7,'rng':list(range(20))}
        before=random.getstate();self.assertEqual(inputs(state),inputs(altered));self.assertEqual(before,random.getstate())
        self.assertNotIn('pilot_wuerfel',FEATURES);self.assertNotIn('kopilot_wuerfel',FEATURES)

    def test_real_roll_leaves_all_public_strategy_inputs_unchanged(self):
        from backend.spielplan import Spielplan
        saved_rng=random.getstate()
        try:
            for case in catalogue_cases():
                with self.subTest(airport=case['airport'],cards=case['abilities']):
                    random.seed('round-pre-roll-parity')
                    game=Spielplan(case['airport'],faehigkeitskarten=case['abilities'],clock=lambda:0.)
                    game._sammle_neuwurf_plaettchen();game._bereite_runde_vor()
                    while game.phase=='verkehr':game.wirf_verkehrswuerfel(runde_starten=False)
                    before=game.zustand()
                    self.assertEqual('vorbereitung',before['phase'])
                    self.assertEqual([None]*4,before['pilot_wuerfel'])
                    self.assertTrue(game.wuerfeln_fuer_runde())
                    after=game.zustand()
                    self.assertEqual(inputs(before),inputs(after))
                    self.assertEqual(choose(before),choose(after))
        finally:random.setstate(saved_rng)

    def test_actual_export_matches_torch_logits_and_chosen_goals(self):
        torch.manual_seed(177);actor=RoundActor();weights=actor.portable()
        self.assertLess(len(json.dumps(weights)),150_000)
        for airport,cards in [('LOG_YUL_GREEN',[]),('LOG_KEF_BLACK',['control','synchronisation']),('LOG_OSL_RED',['adaptation','mastery'])]:
            env=ModuleEnv(airport,abilities=cards);env.reset(seed='round-portable');state=env.game.zustand()
            expected=actor(torch.tensor(encode(state))).detach().tolist()[:OUTPUTS]
            self.assertTrue(all(abs(a-b)<1e-6 for a,b in zip(expected,logits(encode(state),weights))))
            self.assertEqual(sample(actor,state,False)[0],choose(state,weights))

    def test_learning_changes_round_actor_without_changing_blueprint(self):
        torch.manual_seed(51);actor=RoundActor();optimizer=torch.optim.Adam(actor.parameters(),lr=.005)
        env=ModuleEnv('LOG_YUL_GREEN');env.reset(seed='round-gradient');state=env.game.zustand();rows=[]
        for i in range(32):
            _,row=sample(actor,state,True);row['return']=1. if row['actions'][0]==0 else -1.;rows.append(row)
        before=copy.deepcopy(actor.portable());stats=update(actor,optimizer,rows)
        self.assertNotEqual(before,actor.portable());self.assertEqual(32,stats['rounds'])
        self.assertTrue(all(torch.isfinite(p).all() for p in actor.parameters()))

class PotentialAndExplorationTests(unittest.TestCase):
    def test_potential_rewards_telescope_and_coffee_cycles_cannot_pay(self):
        from ai.round_strategy import potential
        env=ModuleEnv('LOG_YUL_GREEN');env.reset(seed='round-potential-test');start=env.game.zustand()
        richer={**start,'kaffeetassen':min(3,start['kaffeetassen']+1)}
        terminal={**richer,'status':'verloren'}
        sequence=[start,richer,start,richer,terminal]
        dense=sum(potential(b)-potential(a) for a,b in zip(sequence,sequence[1:]))
        self.assertAlmostEqual(-potential(start),dense)
        self.assertAlmostEqual(0,(potential(richer)-potential(start))+(potential(start)-potential(richer)))
        self.assertEqual(0,potential(terminal))

    def test_boosted_exploration_records_the_actual_behavior_likelihood(self):
        env=ModuleEnv('LOG_YUL_GREEN');env.reset(seed='round-exploration-test');state=env.game.zustand();actor=RoundActor()
        torch.manual_seed(111);different=0
        reference=sample(actor,state,False)[0]
        for _ in range(60):
            plan,row=sample(actor,state,True,head=1,boost=True)
            self.assertEqual(reference['movement_preference'],plan['movement_preference'])
            self.assertEqual(reference['coordination'],plan['coordination'])
            different+=plan['focus']!=reference['focus']
            self.assertIn('behavior_logp',row)
            self.assertLessEqual(row['logp']-row['behavior_logp'],1.61)
        self.assertGreater(different,35)


if __name__=='__main__':unittest.main()
