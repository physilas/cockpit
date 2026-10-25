from copy import deepcopy
import unittest

import torch

from ai.actions import Action
from ai.agents import ModelAgent
from ai.modules import ModuleEnv, MODULE_ACTIONS
from ai.nn_model import ActorCritic, GuidedResidualActorCritic
from ai.search_environment import OpenRiskEnv
from ai.search_teacher import SearchTeacher


class OpenRiskSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_source_masks_are_exact_and_proposals_remain_engine_legal_and_private(self):
        for airport in ('LOG_HND_GREEN', 'LOG_OSL_GREEN'):
            env = OpenRiskEnv(airport, assistance_version=9)
            source = ModuleEnv(airport, assistance_version=9)
            legal = ModuleEnv(airport)
            _, info = env.reset(seed=251037)
            _, original = source.reset(seed=251037)
            _, raw = legal.reset(seed=251037)
            self.assertEqual(info['source_action_mask'], original['action_mask'])
            self.assertEqual(info['reference_action_mask'], original['reference_action_mask'])
            self.assertTrue(all(not v or raw['action_mask'][i] for i, v in enumerate(info['action_mask'])))
            self.assertTrue(all(not v or info['action_mask'][i] for i, v in enumerate(original['action_mask'])))
            before, rng = deepcopy(env.view()), env.rng.getstate()
            for die in env.game._wuerfel_liste(env.other_role(env.current_role)):
                die.augenzahl = 7 - die.augenzahl
            self.assertEqual(env.view(), before)
            self.assertEqual(env.info()['action_mask'], info['action_mask'])
            self.assertEqual(env.rng.getstate(), rng)
            env.game.landung.hoehe = 0
            landing = env.info()
            self.assertEqual(landing['action_mask'], landing['source_action_mask'])

    def test_open_proposal_preserves_shared_coffee_and_executes_the_real_curve(self):
        # Engine-checked analogue of the recorded forced-coffee bottleneck:
        # pilot rudder 5 is public, copilot thrust 6 is public. The pilot's
        # last die is 4; the unseen copilot die in this fixture is 5.
        env = OpenRiskEnv('LOG_HND_GREEN', assistance_version=9, round_reward=0.)
        env.reset(seed=251037)
        g, c = env.game, env.game.cockpit
        g.am_zug = 'pilot';g.aktuelle_runde = 3;g.neuwurf_plaettchen = 0
        g.landung.hoehe = 4000;g.landung.entfernung = 3
        g.landung.flugzeuge = [0] * len(g.landung.flugzeuge)
        c.kaffeetassen = 2;c.aerodynamik_blau = 4.5;c.aerodynamik_orange = 8.5
        c.landeklappen_ausgefahren[:] = [True, True, True, False]
        c.bremsen_aktiviert[:] = [True, True, False]
        for role in ('pilot', 'kopilot'):
            for die in g._wuerfel_liste(role):die.platziert = True
        g.pilot_wuerfel[0].augenzahl = 5;c.ruder_pilot.wuerfel = g.pilot_wuerfel[0]
        g.kopilot_wuerfel[0].augenzahl = 6;c.schub_kopilot.wuerfel = g.kopilot_wuerfel[0]
        g.pilot_wuerfel[3].augenzahl = 4;g.pilot_wuerfel[3].platziert = False
        g.kopilot_wuerfel[3].augenzahl = 5;g.kopilot_wuerfel[3].platziert = False
        info = env.info();view = env.view()
        coffee = MODULE_ACTIONS.index(Action('coffee', die=3, delta=-2))
        place = MODULE_ACTIONS.index(Action('place', die=3, slot=2))
        self.assertEqual([i for i, v in enumerate(info['source_action_mask']) if v], [coffee])
        self.assertTrue(info['action_mask'][place])
        model = GuidedResidualActorCritic(ActorCritic(489, 217, 8, 1), 489, 217, 8, 1)
        self.assertEqual(ModelAgent(model).select(view, info['source_action_mask'], reference_mask=info['reference_action_mask']), coffee)
        action = SearchTeacher(model, mode='round-open').select(view, info['action_mask'],
                    source_mask=info['source_action_mask'], reference_mask=info['reference_action_mask'])
        self.assertEqual(action, place)
        env.step(action)
        self.assertEqual(c.kaffeetassen, 2)
        env.step(MODULE_ACTIONS.index(Action('coffee', die=3, delta=-1)))
        env.step(MODULE_ACTIONS.index(Action('place', die=3, slot=1)))
        self.assertEqual(g.status, 'laeuft')
        self.assertEqual((g.landung.entfernung, c.fluglage, c.kaffeetassen), (1, -1, 1))

    def test_open_teacher_requires_an_original_source_mask(self):
        model = ActorCritic(489, 217, 8, 1)
        env = OpenRiskEnv('LOG_HND_GREEN', assistance_version=9);_, info = env.reset(seed=251037)
        with self.assertRaises(ValueError):
            SearchTeacher(model, mode='round-open').select(env.view(), info['action_mask'])


if __name__ == '__main__':
    unittest.main()
