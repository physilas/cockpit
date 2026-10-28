import unittest

from ai.actions import Action
from ai.coherent_advice import profile12_masks
from ai.coherent_safety import coherent_safe_actions
from ai.contract_planner import IDS
from ai.module_capacity import reserve_controls
from ai.modules import ModuleEnv
from ai.response_contract import ResponseContractAgent,partner_control_published
from ai.safety_guard import safe_actions


class ResponseContractTests(unittest.TestCase):
    def test_public_cue_does_not_depend_on_faces_or_private_rng(self):
        env=ModuleEnv('MUC');env.reset(seed='train:response-public-cue')
        self.assertFalse(partner_control_published(env.view()))
        for die in env.game.kopilot_wuerfel:die.augenzahl=7-die.augenzahl
        env.rng.seed(39)
        self.assertFalse(partner_control_published(env.view()))
        env.step(IDS[Action('place',die=0,slot=0)])
        self.assertTrue(partner_control_published(env.view()))

    def test_before_public_cue_uses_exact_safe_blueprint_without_new_convention(self):
        class FirstLegal:
            def select(self,view,mask,*,reference_mask):
                self.mask,self.reference=list(mask),list(reference_mask)
                return next(i for i,ok in enumerate(mask) if ok)
        for airport,cards in (('MUC',[]),('LOG_KEF_YELLOW',['adaptation'])):
            env=ModuleEnv(airport,abilities=cards);env.reset(seed='train:response-blueprint:'+airport)
            view,raw=env.view(),env.action_mask()
            agent=ResponseContractAgent.__new__(ResponseContractAgent)
            agent.airport,agent.agent,agent.beam=airport,FirstLegal(),24
            chosen=agent.select(view,raw)
            allowed,_=coherent_safe_actions(airport,view,raw)
            safe,_=safe_actions(airport,view,reserve_controls(view,allowed))
            expected,reference=profile12_masks(view,safe)
            self.assertEqual(expected,agent.agent.mask)
            self.assertEqual(reference,agent.agent.reference)
            self.assertEqual('await_public_partner_control',agent.last_report['planning_mode'])
            self.assertTrue(raw[chosen])
