import json
from pathlib import Path
import subprocess
import sys
import unittest

from backend import bridge
from ai.coherent_advice import coherent_masks
from ai.public_contract import public_contract_inputs
from ai.modules import ModuleEnv
from ai.strategy_bridge import strategy_decision


class StrategyBridgeTests(unittest.TestCase):
    def test_native_masks_and_hidden_hand_boundary_for_both_new_policies(self):
        for airport,cards in (('MUC',[]),('LOG_KEF_YELLOW',['adaptation']),('LOG_HND_RED',['synchronisation'])):
            env=ModuleEnv(airport,abilities=cards)
            env.reset(seed='train:strategy-bridge:'+airport)
            bridge._spiel=env.game
            for policy,mask_function in (('contract',public_contract_inputs),('coherent',coherent_masks)):
                allowed,reference,_=mask_function(airport,env.view(),env.action_mask())
                actual=strategy_decision(policy=policy)
                self.assertEqual(allowed,actual['action_mask'])
                self.assertEqual(reference,actual['reference_action_mask'])
                self.assertEqual(env.observation(),actual['observation'])
                self.assertNotIn('own_dice',actual['public_state'])
                for die in bridge._spiel._wuerfel_liste(env.other_role(env.current_role)):
                    die.augenzahl=7-die.augenzahl
                self.assertEqual(actual,strategy_decision(policy=policy))

    def test_reroll_role_enforcement_and_unknown_policy(self):
        bridge.neues_spiel('MUC')
        pending={'initiator':'pilot','selections':{'pilot':[0],'kopilot':None}}
        self.assertEqual('kopilot',strategy_decision('kopilot',json.dumps(pending))['role'])
        with self.assertRaises(ValueError):strategy_decision('pilot',json.dumps(pending))
        with self.assertRaises(ValueError):strategy_decision(policy='unknown')

    def test_browser_strategy_runs_without_torch_or_numpy(self):
        code="""import builtins
original=builtins.__import__
def only_standard(name,*args,**kwargs):
    if name.split('.')[0] in ('torch','numpy'):raise ImportError(name)
    return original(name,*args,**kwargs)
builtins.__import__=only_standard
from backend import bridge
from ai.modules import ModuleEnv
from ai.strategy_bridge import strategy_decision
env=ModuleEnv('LOG_KEF_YELLOW',abilities=['adaptation'])
env.reset(seed='train:torch-free-bridge')
bridge._spiel=env.game
result=strategy_decision()
assert len(result['observation'])==489 and any(result['reference_action_mask'])
"""
        result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=15)
        self.assertEqual(0,result.returncode,result.stderr)
