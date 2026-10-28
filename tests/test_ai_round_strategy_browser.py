import json
import unittest
from unittest.mock import patch
from backend import bridge
from play_options import neues_spiel
from ai.briefing import suggest as original
from ai.round_strategy_browser import suggest
from ai.round_strategy_training import RoundActor
from ai.round_strategy import inputs,OUTPUTS,OFFSETS,HEADS


class RoundStrategyBrowserTests(unittest.TestCase):
    def test_old_crews_and_missing_qualified_weights_keep_exact_proposals(self):
        neues_spiel('LOG_YUL_GREEN',briefing=True)
        with patch('ai.round_strategy_browser.released_weights',return_value=None):
            for profile in (0,12,13,14,15):self.assertEqual(original(),suggest(profile))

    def test_learned_defaults_are_valid_goals_and_cannot_access_rolled_dice(self):
        state=neues_spiel('LOG_YUL_GREEN',briefing=True);weights=RoundActor().portable()
        weights['actor_weight']=[[0.]*48 for _ in range(OUTPUTS)];weights['actor_bias']=[0.]*OUTPUTS
        weights['actor_bias'][0]=5.;weights['actor_bias'][OFFSETS[1]+2]=5.
        weights['release']={'qualification_granted':True}
        with patch('ai.round_strategy_browser.released_weights',return_value=(weights,'test-sha')):
            proposal=suggest(15);self.assertEqual(0,proposal['goals'][0]['selected']);self.assertEqual('coffee',proposal['goals'][1]['selected'])
            self.assertEqual(original(),suggest(13));self.assertEqual('test-sha',proposal['strategy_selection']['weights_sha256'])
            bridge.wuerfeln_fuer_runde()
            with self.assertRaises(ValueError):suggest(15)

    def test_recorded_strategy_context_contains_public_inputs_and_preserves_rng(self):
        import random
        from ai.round_strategy import FEATURES
        state=neues_spiel('LOG_YUL_GREEN',briefing=True);weights=RoundActor().portable()
        weights['release']={'qualification_granted':True}
        before=random.getstate()
        with patch('ai.round_strategy_browser.released_weights',return_value=(weights,'public-context-test')):
            proposal=suggest(15)
        context=proposal['strategy_selection']['training_context']
        self.assertEqual(list(FEATURES),context['feature_names'])
        self.assertEqual(inputs(state),tuple(context[key] for key in ('public_features','goal_mask','default_prior')))
        self.assertEqual(before,random.getstate())
        self.assertNotIn('pilot_wuerfel',json.dumps(proposal));self.assertNotIn('kopilot_wuerfel',json.dumps(proposal))

    def test_ranked_alternatives_are_legal_and_obey_the_public_goal_mask(self):
        from ai.round_strategy import HEADS,OFFSETS
        state=neues_spiel('LOG_YUL_GREEN',briefing=True);weights=RoundActor().portable()
        weights['release']={'qualification_granted':True}
        with patch('ai.round_strategy_browser.released_weights',return_value=(weights,'ranked-context-test')):
            proposal=suggest(15)
        mask=inputs(state)[1]
        for h,goal in enumerate(proposal['goals']):
            expected={v for i,v in enumerate(HEADS[h][1]) if mask[OFFSETS[h]+i]}
            self.assertEqual(expected,set(goal['ai_suggestions']))
            self.assertEqual(goal['selected'],goal['ai_suggestions'][0])
            self.assertTrue(all(any(o['value']==v for o in goal['options']) for v in goal['ai_suggestions']))

    def test_real_decisions_keep_old_crews_and_skipped_plans_exact(self):
        from ai.briefing_browser import decision as old_decision
        from ai.briefing_browser_v2 import decision as v2_decision
        from ai.round_strategy_browser import decision as actual
        from ai.briefing import proposals
        state=neues_spiel('LOG_KUL_YELLOW',json.dumps(['synchronisation']))
        while state['phase']=='verkehr':state=bridge.wirf_verkehrswuerfel()['zustand']
        if state['phase']=='vorbereitung':state=bridge.wuerfeln_fuer_runde()
        plan=json.dumps({'version':1,'round':state['runde'],**{g['key']:g['selected'] for g in proposals(state)['goals']}})
        with patch('ai.round_strategy_browser.released_weights',side_effect=AssertionError('Legacy paths must not require the new goal network.')):
            self.assertEqual(old_decision(assistance_version=15,schema_version=3),actual(assistance_version=15,schema_version=3))
            self.assertEqual(old_decision(assistance_version=13,schema_version=3,plan_json=plan),actual(assistance_version=13,schema_version=3,plan_json=plan))
        with patch('ai.round_strategy_browser.released_weights',return_value=({'release':{}},'presence-only')):
            result=actual(assistance_version=15,schema_version=3,plan_json=plan)
            self.assertEqual(v2_decision(assistance_version=15,schema_version=3,plan_json=plan),result)
            self.assertEqual('briefing-v2',result['communication_policy'])

    def test_browser_adapter_import_is_torch_free(self):
        import subprocess,sys
        subprocess.run([sys.executable,'-c',"import sys;import ai.round_strategy_browser;assert 'torch' not in sys.modules"],check=True,timeout=10)
