import copy
import json
import unittest
from unittest.mock import patch
from backend import bridge
from play_options import neues_spiel
from ai.modules import ModuleEnv
from ai.round_strategy_options import proposals,validate_plan,is_expert_plan
from ai.briefing_browser_v2 import decision
from ai.ability_browser import decision as expert
from ai.round_strategy_browser import start_round


class FlexibleRoundOptionsTests(unittest.TestCase):
    def test_expert_is_a_valid_public_goal_but_malformed_plans_do_not_roll(self):
        state=neues_spiel('LOG_YUL_GREEN',briefing=True)
        proposal=proposals(state)
        plan={'version':2,'round':1,**{g['key']:g['selected'] for g in proposal['goals']}}
        self.assertTrue(is_expert_plan(plan));self.assertEqual(plan,validate_plan(plan,state))
        for invalid in ({**plan,'round':2},{**plan,'movement_preference':True},{**plan,'version':True},{**plan,'extra':3},[]):
            with self.assertRaises(ValueError):start_round(json.dumps(invalid))
            self.assertEqual([None]*4,bridge.zustand()['pilot_wuerfel'])
        self.assertEqual('platzieren',start_round(json.dumps(plan))['phase'])

    def test_expert_option_preserves_actual_old_decision_inputs_and_arbitration(self):
        for airport,cards in [('LOG_YUL_GREEN',[]),('LOG_KUL_YELLOW',['synchronisation']),('LOG_GIG_YELLOW',['control'])]:
            with self.subTest(airport=airport):
                env=ModuleEnv(airport,abilities=cards,clock=lambda:0.);env.reset(seed='exact-expert-option')
                plan={'version':2,'round':1,'movement_preference':None,'focus':None,'coordination':None}
                with patch.object(bridge,'_spiel',env.game):
                    original=expert(assistance_version=15,schema_version=3)
                    result=decision(assistance_version=15,schema_version=3,plan_json=json.dumps(plan))
                for key,value in original.items():self.assertEqual(value,result[key],key)
                self.assertEqual(plan,result['round_plan'])
