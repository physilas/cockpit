import unittest

from ai.coherent_advice import profile12_masks
from ai.contract_planner import ContractAgent
from ai.modules import ModuleEnv
from ai.public_contract import arbitrate_contract,public_contract_inputs


class PublicContractTests(unittest.TestCase):
    def test_public_arbitration_matches_original_agent_across_transitions(self):
        class Blueprint:
            def rank(self,view,raw):
                allowed,_=profile12_masks(view,raw)
                ids=[i for i,ok in enumerate(allowed) if ok]
                return ids[0],ids
        for airport,cards in (('MUC',[]),('LOG_KEF_YELLOW',['adaptation']),('LOG_HND_RED',['synchronisation'])):
            env=ModuleEnv(airport,abilities=cards,clock=lambda:0.)
            env.reset(seed='train:public-contract:'+airport)
            agent=ContractAgent(airport,Blueprint(),beam=12)
            for _ in range(16):
                view,raw=env.view(),env.action_mask()
                expected=agent.select(view,raw)
                allowed,reference,plan=public_contract_inputs(airport,view,raw,beam=12,respond_to_partner=False)
                baseline=next(i for i,ok in enumerate(plan['baseline_mask']) if ok)
                self.assertEqual(expected,arbitrate_contract(baseline,allowed,plan))
                self.assertTrue(all(not r or a for a,r in zip(plan['baseline_mask'],reference)))
                env.step(expected)
                if env.done:break

    def test_invalid_or_non_engine_legal_arbitration_fails(self):
        with self.assertRaises(ValueError):arbitrate_contract(1,[True,False],{})
        plan=dict(best_action=1,scores={'1':5.},forced_action=None,tolerance=1.)
        with self.assertRaises(ValueError):arbitrate_contract(0,[True,False],plan)

    def test_familiar_first_control_is_kept_on_plain_routes(self):
        env=ModuleEnv('MUC');env.reset(seed='train:adaptive-contract-cue')
        allowed,reference,plan=public_contract_inputs('MUC',env.view(),env.action_mask(),beam=12)
        self.assertEqual('await_public_partner_control',plan['planning_mode'])
        self.assertIsNone(plan['forced_action']);self.assertIsNone(plan['best_action'])
        baseline=next(i for i,ok in enumerate(plan['baseline_mask']) if ok)
        self.assertEqual(baseline,arbitrate_contract(baseline,allowed,plan))

    def test_coupled_modules_keep_the_complete_plan_from_the_first_move(self):
        for airport in ('LOG_GIG_YELLOW','LOG_KEF_YELLOW','LOG_HND_RED'):
            env=ModuleEnv(airport,abilities=['adaptation']);env.reset(seed='train:adaptive-coupling:'+airport)
            args=(airport,env.view(),env.action_mask())
            default=public_contract_inputs(*args,beam=12)
            direct=public_contract_inputs(*args,beam=12,respond_to_partner=False)
            self.assertEqual(default,direct)
            self.assertNotEqual('await_public_partner_control',default[2]['planning_mode'])
