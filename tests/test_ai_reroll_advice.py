import unittest

from ai.actions import Action
from ai.contract_planner import IDS, PlanScores
from ai.modules import MODULE_ACTIONS, ModuleEnv
from ai.reroll_advice import landing_reroll_values,reroll_selection,worthwhile_landing_reroll


class RerollAdviceTests(unittest.TestCase):
    def view(self):
        env=ModuleEnv('MUC');env.reset(seed=14000230)
        view=env.view();view.update(last_round=True,height=0,distance=0,gear=[True]*3,flaps=[True]*4)
        view['board'][0]={'value':3,'owner':'pilot'}
        view['brake_progress']=[True]*3;view['brakes']=6
        for c in view['track']:c['planes']=0
        view['own_dice']=[6,0,0,0]
        return view

    def planner(self,view,allowed,**kwargs):
        result=PlanScores({0:10000. if view['own_dice'][0]<=3 else 0.},primary_available=True)
        result.primary_value=result[0]
        return result

    def test_six_counterfactual_faces_have_their_fair_mean(self):
        view=self.view()
        scores=landing_reroll_values(view,planner=self.planner)
        self.assertEqual({0:0.,1:5000.},scores)
        self.assertEqual([6,0,0,0],view['own_dice'])
        allowed=[True]*len(MODULE_ACTIONS)
        yes,_=worthwhile_landing_reroll(view,allowed,planner=self.planner)
        self.assertTrue(yes)
        selected,_=reroll_selection({**view,'reroll':{'initiator':'pilot'}},allowed,planner=self.planner)
        self.assertEqual(IDS[Action('reroll_select',subset=1)],selected)

    def test_keep_a_good_actual_die_and_respect_the_engine_mask(self):
        view=self.view();view['own_dice'][0]=1
        allowed=[True]*len(MODULE_ACTIONS)
        self.assertFalse(worthwhile_landing_reroll(view,allowed,planner=self.planner)[0])
        self.assertEqual(IDS[Action('reroll_select',subset=0)],reroll_selection(view,allowed,planner=self.planner)[0])
        allowed[IDS[Action('reroll_select',subset=0)]]=False
        self.assertEqual(IDS[Action('reroll_select',subset=1)],reroll_selection(view,allowed,planner=self.planner)[0])

    def test_proven_impossible_tasks_do_not_consume_a_token(self):
        view=self.view();view['gear']=[False]*3
        called=[]
        def forbidden(*args,**kwargs):called.append(True);raise AssertionError('Must not plan this impossible landing.')
        self.assertEqual({},landing_reroll_values(view,planner=forbidden))
        self.assertEqual([],called)

    def test_real_final_hand_can_prefer_a_reroll_before_its_chance_is_zero(self):
        from ai.contract_planner import ContractAgent
        class Blueprint:
            def rank(self,view,mask):
                ids=[i for i,ok in enumerate(mask) if ok]
                return ids[0],ids
        env=ModuleEnv('MUC',clock=lambda:0.)
        env.reset(seed='train:prospective-reroll:actual')
        game=env.game;c=game.cockpit
        game.letzte_runde=True;game.landung.hoehe=0;game.landung.entfernung=0
        game.landung.flugzeuge=[0]*len(game.landung.flugzeuge)
        c.fahrwerk_ausgefahren=[True]*3;c.landeklappen_ausgefahren=[True]*4
        c.bremsen_aktiviert=[True]*3;c.kaffeetassen=1
        game.neuwurf_plaettchen=1
        for die in game.pilot_wuerfel:die.augenzahl=6
        agent=ContractAgent('MUC',Blueprint(),beam=12,prospective_rerolls=True)
        chosen=agent.select(env.view(),env.action_mask())
        self.assertEqual(IDS[Action('reroll_start')],chosen)
        scores=agent.last_report['reroll_values']
        self.assertGreater(scores[0],0)
        self.assertGreater(max(scores.values()),scores[0]+100.)
        for die in game.kopilot_wuerfel:die.augenzahl=7-die.augenzahl
        self.assertEqual(chosen,agent.select(env.view(),env.action_mask()))
