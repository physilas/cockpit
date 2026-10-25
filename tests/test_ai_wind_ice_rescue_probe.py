"""Fatal-rudder classification uses known own/public faces only."""
from copy import deepcopy
import random
import unittest

from ai.actions import Action
from ai.wind_ice_rescue_probe import fatal_rudder
from tests.test_ai_wind_ice_counterexamples import ice_final_pair_fixture


class WindIceRescueProbeTests(unittest.TestCase):
    def test_regular_and_explicit_bonus_faces_use_the_public_other_rudder(self):
        view = ice_final_pair_fixture().view()
        view['board'][1] = None
        view['board'][0] = {'value': 2, 'owner': 'pilot'}
        view['own_dice'][3] = 6
        view['attitude'] = -1
        before, rng = deepcopy(view), random.getstate()
        self.assertTrue(fatal_rudder(view, Action('place', die=3, slot=1)))
        self.assertEqual(view, before)
        self.assertEqual(random.getstate(), rng)
        view['modules_state']['pending'] = {'role': 'kopilot', 'source': 'synchronisation', 'value': 6}
        self.assertTrue(fatal_rudder(view, Action('bonus_place', slot=1)))
        view['modules_state']['pending']['value'] = None
        self.assertFalse(fatal_rudder(view, Action('bonus_place', slot=1)))

    def test_unpublished_partner_control_causes_abstention(self):
        view = ice_final_pair_fixture().view()
        view['board'][0] = view['board'][1] = None
        self.assertFalse(fatal_rudder(view, Action('place', die=3, slot=1)))
        self.assertFalse(fatal_rudder(view, Action('coffee', die=3, delta=1)))


if __name__ == '__main__':
    unittest.main()
