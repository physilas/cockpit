from copy import deepcopy
import unittest

from ai.fuel_capacity import necessary_fuel_fields
from ai.modules import ModuleEnv


class FuelCapacityTests(unittest.TestCase):
    def test_bound_matches_exhaustive_best_case_payment_counts(self):
        env=ModuleEnv('LOG_OSL_GREEN');env.reset(seed='train:fuel-count-bound')
        for rounds in range(1,8):
            for remaining in range(1,51):
                view=deepcopy(env.view());view['height']=(rounds-1)*1000
                view['fuel'].update(remaining=remaining,occupied=False)
                view['last_round']=rounds==1
                result=necessary_fuel_fields(view)
                possible=[p for p in range(rounds+1) if remaining-(6*(rounds-p)+p)>0]
                self.assertEqual(bool(possible),result['possible'],(rounds,remaining))
                if possible:self.assertEqual(min(possible),result['minimum_payments'])

    def test_current_payment_is_charged_and_counted_once(self):
        env=ModuleEnv('LOG_OSL_GREEN');env.reset(seed='train:fuel-count-payment')
        view=env.view();view['height']=6000;view['fuel']['remaining']=20
        self.assertEqual(5,necessary_fuel_fields(view)['minimum_payments'])
        view['fuel'].update(remaining=19,occupied=True)
        self.assertEqual(4,necessary_fuel_fields(view)['minimum_payments'])
        view['fuel']['remaining']=14
        self.assertEqual(5,necessary_fuel_fields(view)['minimum_payments'])

    def test_leak_is_control_cost_and_does_not_invent_a_fuel_field(self):
        env=ModuleEnv('LOG_ATL_YELLOW',abilities=['adaptation']);env.reset(seed='train:fuel-count-leak')
        self.assertFalse(necessary_fuel_fields(env.view())['applicable'])
