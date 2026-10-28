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
                allowed,reference,plan=public_contract_inputs(airport,view,raw,beam=12)
                baseline=next(i for i,ok in enumerate(plan['baseline_mask']) if ok)
                self.assertEqual(expected,arbitrate_contract(baseline,allowed,plan))
                self.assertTrue(all(not r or a for a,r in zip(plan['baseline_mask'],reference)))
                env.step(expected)
                if env.done:break

    def test_invalid_or_non_engine_legal_arbitration_fails(self):
        with self.assertRaises(ValueError):arbitrate_contract(1,[True,False],{})
        plan=dict(best_action=1,scores={'1':5.},forced_action=None,tolerance=1.)
        with self.assertRaises(ValueError):arbitrate_contract(0,[True,False],plan)
