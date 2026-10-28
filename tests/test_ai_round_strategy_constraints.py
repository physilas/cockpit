import unittest
from unittest.mock import patch
import torch
from ai.modules import ModuleEnv
from ai.briefing import proposals
from ai.round_strategy import HEADS,OFFSETS,OUTPUTS,choose,inputs
from ai.round_strategy_training import RoundActor,load_actor_weights,collect_pair


class RoundGoalConstraintsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1)

    def state(self):
        env=ModuleEnv('LOG_YUL_GREEN');env.reset(seed='public-necessary-goals')
        return env.game.zustand()

    def choices(self,state,key):
        h=next(i for i,head in enumerate(HEADS) if head[0]==key);mask=inputs(state)[1]
        return {v for i,v in enumerate(HEADS[h][1]) if mask[OFFSETS[h]+i]}

    def test_explicit_goal_cannot_leave_an_unreachable_remaining_distance(self):
        weights=RoundActor().portable();weights['actor_bias'][1]=100.;weights['actor_bias'][2]=2.
        for distance,height in [(2,1000),(4,2000),(6,3000)]:
            state={**self.state(),'entfernung':distance,'hoehe':height,'letzte_runde':False,'warteschleife':False}
            self.assertEqual(2,choose(state,weights)['movement_preference'])
            self.assertEqual({2,None},self.choices(state,'movement_preference'))
        state={**self.state(),'entfernung':3,'hoehe':1000,'letzte_runde':False,'warteschleife':False}
        self.assertEqual(2,choose(state,weights)['movement_preference'])

    def test_irreversible_threshold_reduces_the_maximum_future_speed(self):
        state={**self.state(),'entfernung':2,'hoehe':2000,'aerodynamik_orange':12.5}
        self.assertEqual({1,None},self.choices(state,'movement_preference'))
        state['module']=['wind'];self.assertIn(2,self.choices(state,'movement_preference'))

    def test_finished_tasks_and_empty_airspace_are_not_explicit_goals(self):
        state={**self.state(),'faehigkeitskarten':['synchronisation'],
               'fahrwerk_ausgefahren':[True]*3,'landeklappen_ausgefahren':[True]*4,
               'bremsen_aktiviert':[True]*3,'flugzeuge':[0]*self.state()['laenge']}
        self.assertEqual({'coffee',None},self.choices(state,'focus'))
        self.assertEqual({'level',None},self.choices(state,'coordination'))
        state['landeklappen_ausgefahren']=[True]*3+[False]
        self.assertIn('tasks',self.choices(state,'focus'));self.assertNotIn('synchronisation',self.choices(state,'coordination'))

    def test_final_round_wind_goal_and_finished_ice_are_not_suggested(self):
        state={**self.state(),'module':['wind','ice'],'letzte_runde':True,'eis_fortschritt':4}
        self.assertEqual({'level',None},self.choices(state,'coordination'))
        expected={'version':1,'round':state['runde'],**{g['key']:g['selected'] for g in proposals(state)['goals']}}
        self.assertEqual(expected,choose(state))

    def test_warm_start_preserves_new_actor_but_resets_the_critic(self):
        source=RoundActor().portable();actor=RoundActor();load_actor_weights(actor,source)
        self.assertEqual(source,actor.portable());self.assertTrue(torch.equal(actor.output.weight[-1],torch.zeros(48)))
        self.assertEqual(0.,float(actor.output.bias[-1].detach()))

    def test_exploration_targets_a_reached_round_and_a_head_with_alternatives(self):
        actor=RoundActor();state={k:v.detach().tolist() for k,v in actor.state_dict().items()}
        mask=[False]*OUTPUTS
        for i in (0,OFFSETS[1],OFFSETS[1]+1,OFFSETS[2]):mask[i]=True
        calls=[]
        def fake_play(model,case,seed,**kwargs):
            calls.append(kwargs)
            return [{'round':1,'mask':mask,'td_advantage':0.,'policy_weight':float(kwargs['stochastic'])}],{'won':False}
        with patch('ai.round_strategy_training.play',side_effect=fake_play):
            _,rows,record=collect_pair((0,{},'unit-reachable-head',state))
        self.assertFalse(calls[0]['stochastic']);self.assertEqual((1,1),calls[1]['exploration_choice'])
        self.assertEqual('focus',record['explored_head']);self.assertEqual(0.,rows[0]['advantage'])


if __name__=='__main__':unittest.main()
