import unittest

from ai.actions import Action
from ai.belief_simulator import BeliefSimulator,simulation_step
from ai.modules import MODULE_ACTIONS,ModuleEnv
from ai.safety_guard import safe_actions


class RealtimeGuardTests(unittest.TestCase):
    def test_rounded_remaining_second_is_not_a_proof_that_a_winning_move_times_out(self):
        env=ModuleEnv('LOG_PBH_RED',abilities=['adaptation','control'],clock=lambda:0.)
        env.reset(seed='train:realtime-guard:rounding')
        view=env.view('pilot')
        view.update(regular_turn='pilot',round_starter='pilot',round=7,height=0,distance=0,last_round=True,
            holding=False,attitude=0,coffee=0,partner_remaining=0,own_dice=[0,0,0,2],
            gear=[True]*3,flaps=[True]*4,brake_progress=[True]*3,brakes=6,aero_blue=7.5,aero_orange=12.5)
        for cell in view['track']:cell['planes']=0
        for index,role in enumerate(('pilot','kopilot','pilot','kopilot')):
            view['board'][index]={'value':1,'owner':role}
        view['fuel'].update(remaining=20,occupied=True)
        view['modules_state'].update(time_remaining=1,pending=None,swap=None)
        closing=MODULE_ACTIONS.index(Action('place',die=3,slot=17))
        reroll=MODULE_ACTIONS.index(Action('reroll_start'))
        raw=[i in (closing,reroll) for i in range(len(MODULE_ACTIONS))]
        branch=BeliefSimulator('LOG_PBH_RED',view).sample(0)
        branch.game.zusatz.deadline=None
        simulation_step(branch,closing)
        self.assertEqual('gewonnen',branch.game.status)
        allowed,meta=safe_actions('LOG_PBH_RED',view,raw)
        self.assertTrue(allowed[closing])
        self.assertNotIn(str(closing),meta['rejected'])
