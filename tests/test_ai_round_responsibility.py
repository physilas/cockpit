from copy import deepcopy
import unittest

from ai.modules import ModuleEnv
from ai.round_responsibility import public_responsibilities


class ResponsibilityTests(unittest.TestCase):
    def test_both_roles_and_all_private_faces_receive_the_same_prescription(self):
        env=ModuleEnv('LOG_OSL_GREEN');env.reset(seed=14000220)
        a=public_responsibilities(env.view('pilot'),1)
        b=public_responsibilities(env.view('kopilot'),1)
        self.assertEqual(a,b)
        view=env.view();view['own_dice']=[1,1,1,1]
        self.assertEqual(a,public_responsibilities(view,1))

    def test_three_current_planes_consume_the_three_distinct_radio_slots(self):
        env=ModuleEnv('MUC');env.reset(seed=14000221)
        view=env.view()
        for cell in view['track']:cell['planes']=3 if cell['distance']==view['distance'] else 0
        tasks=public_responsibilities(view,1)
        self.assertEqual([1],tasks['radios']['pilot'])
        self.assertEqual([1,1],tasks['radios']['kopilot'])
        view['partner_remaining']=2
        tasks=public_responsibilities(view,1)
        self.assertEqual(1,sum(map(len,tasks['radios'].values())))

    def test_training_schedule_counts_an_already_issued_token_once(self):
        env=ModuleEnv('LOG_ATL_GREEN');env.reset(seed=14000222)
        root=env.view()
        self.assertEqual(1,len(public_responsibilities(root,1)['training_roles']))
        trained=deepcopy(root)
        trained['modules_state']['intern'].pop(0)
        trained['modules_state']['extra_fields'][0]={'value':2,'owner':'pilot'}
        self.assertEqual([],public_responsibilities(trained,1)['training_roles'])

    def test_fuel_payment_budget_accounts_for_all_remaining_rounds(self):
        env=ModuleEnv('LOG_OSL_GREEN');env.reset(seed=14000223)
        view=env.view();view['fuel']['remaining']=20;view['height']=6000
        tasks=public_responsibilities(view,1)
        self.assertEqual(2,tasks['payment_target'])
        view['fuel']['occupied']=True
        self.assertIsNone(public_responsibilities(view,1)['fuel_role'])
