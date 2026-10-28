import unittest
from copy import deepcopy
import random

from ai.actions import Action
from ai.modules import MODULE_ACTIONS, ModuleEnv
from ai.module_training_eval import _official_cases
from ai.safety_guard import safe_actions


IDS = {action: i for i, action in enumerate(MODULE_ACTIONS)}


class SafetyGuardTests(unittest.TestCase):
    def test_excludes_known_fatal_rudder_preserves_safe_control_and_helpers(self):
        env = ModuleEnv('MUC')
        env.reset(seed=14000000)
        for die, value in zip(env.game.pilot_wuerfel, (6, 3, 2, 1)):
            die.augenzahl = value
        partner = env.game.kopilot_wuerfel[0]
        partner.augenzahl, partner.platziert = 3, True
        env.game.cockpit.ruder_kopilot.wuerfel = partner
        raw = env.action_mask()
        fatal = IDS[Action('place', die=0, slot=0)]
        safe = IDS[Action('place', die=1, slot=0)]
        reroll = IDS[Action('reroll_start')]
        allowed, meta = safe_actions('MUC', env.view(), raw)
        self.assertTrue(raw[fatal])
        self.assertFalse(allowed[fatal])
        self.assertEqual('trudeln', meta['rejected'][str(fatal)])
        self.assertTrue(allowed[safe])
        self.assertEqual(raw[reroll], allowed[reroll])
        self.assertEqual('laeuft', env.game.status)

    def test_known_leak_cost_is_checked_at_second_thrust(self):
        airport, cards = next((a, c) for (a, c), m in _official_cases().items()
                              if 'leak' in m and not set(m) & {'wind', 'intern'})
        env = ModuleEnv(airport, abilities=cards)
        env.reset(seed=14000000)
        for die, value in zip(env.game.pilot_wuerfel, (6, 1, 2, 3)):
            die.augenzahl = value
        partner = env.game.kopilot_wuerfel[0]
        partner.augenzahl, partner.platziert = 1, True
        env.game.cockpit.schub_kopilot.wuerfel = partner
        env.game.cockpit.kerosin = 4
        fatal = IDS[Action('place', die=0, slot=2)]
        safe = IDS[Action('place', die=1, slot=2)]
        allowed, meta = safe_actions(airport, env.view(), env.action_mask())
        self.assertFalse(allowed[fatal])
        self.assertTrue(allowed[safe])
        self.assertEqual('kerosin_leer', meta['rejected'][str(fatal)])

    def test_partner_hidden_faces_cannot_change_rejections(self):
        env = ModuleEnv('MUC')
        env.reset(seed=14000000)
        raw = env.action_mask()
        first = safe_actions('MUC', env.view(), raw)
        for die in env.game.kopilot_wuerfel:
            die.augenzahl = 7 - die.augenzahl
        env.rng.seed(920)
        self.assertEqual(first, safe_actions('MUC', env.view(), raw))

    def test_fast_checks_match_real_engine_at_module_intermediate_states(self):
        rng = random.Random(92)
        for airport, cards in list(_official_cases())[::17]:
            env = ModuleEnv(airport, abilities=cards, clock=lambda: 0.)
            env.reset(seed=14000050)
            for step in range(16):
                if env.done:
                    break
                raw = env.action_mask()
                _, meta = safe_actions(airport, env.view(), raw)
                actual_fatal = set()
                for index, ok in enumerate(raw):
                    if ok and MODULE_ACTIONS[index].kind in ('place', 'bonus_place'):
                        branch = deepcopy(env)
                        branch.step(index)
                        if branch.game.status == 'verloren':
                            actual_fatal.add(str(index))
                self.assertEqual(actual_fatal, set(meta['rejected']), (airport, step))
                env.step(rng.choice([i for i, ok in enumerate(raw) if ok]))
