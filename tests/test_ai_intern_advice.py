"""Intern advice is public, legal, paced, and uses actual replacement tokens."""
from copy import deepcopy
import random
import unittest

from ai.actions import Action
from ai.intern_advice import intern_reference, intern_schedule, _token_targets
from ai.modules import ModuleEnv, MODULE_ACTIONS


def index(kind, **fields):
    return MODULE_ACTIONS.index(Action(kind, **fields))


def fresh(airport='LOG_ATL_GREEN', role='pilot'):
    cards = ['adaptation'] if airport == 'LOG_HND_RED' else []
    env = ModuleEnv(airport, abilities=cards, clock=lambda: 0.)
    env.reset(seed='train:intern-advice:251052')
    env.game.am_zug = role
    env.game.zusatz.praktikant = [1, 2, 3, 4, 5, 6]
    for r in ('pilot', 'kopilot'):
        for die, face in zip(env.game._wuerfel_liste(r), (3, 1, 2, 4)):
            die.augenzahl = face
    return env


def play(env, die, slot):
    return env.step(index('place', die=die, slot=slot))


class InternAdviceTests(unittest.TestCase):
    def test_one_training_per_round_is_softly_recommended_then_marked_done(self):
        env = fresh()
        self.assertEqual(intern_schedule(env.view())['recommended_now'], 1)
        raw = env.action_mask()
        advice = intern_reference(env.view(), raw)
        self.assertTrue(any(advice))
        self.assertTrue(all(not flag or raw[i] for i, flag in enumerate(advice)))
        self.assertTrue(all(action.kind == 'place' and action.slot == 21
                            for flag, action in zip(advice, MODULE_ACTIONS) if flag))
        env.step(next(i for i, flag in enumerate(advice) if flag))
        self.assertEqual(env.view()['modules_state']['pending']['value'], 1)
        self.assertEqual(len(env.game.zusatz.praktikant), 5)
        schedule = intern_schedule(env.view())
        self.assertEqual(schedule['trained_this_round'], 1)
        self.assertEqual(schedule['recommended_now'], 0)
        self.assertEqual(sum(bool(value) for value in env.view()['own_dice']), 3)
        pending = intern_reference(env.view(), env.action_mask())
        self.assertTrue(all(action.kind == 'bonus_place'
                            for flag, action in zip(pending, MODULE_ACTIONS) if flag))
        env.step(next(i for i, flag in enumerate(pending) if flag))
        self.assertIsNone(env.view()['modules_state']['pending'])

    def test_late_quota_counts_remaining_public_slots_and_reports_impossibility(self):
        env = fresh()
        view = env.view()
        view['height'] = 1000
        view['modules_state']['intern'] = [1, 2, 3, 4]
        schedule = intern_schedule(view)
        self.assertEqual(schedule['minimum_now'], 2)
        self.assertEqual(schedule['recommended_now'], 2)
        view['modules_state']['extra_fields'][0] = {'owner': 'pilot', 'value': 4}
        view['modules_state']['intern'] = [2, 3, 4]
        self.assertEqual(intern_schedule(view)['recommended_now'], 1)
        view['last_round'] = True
        self.assertTrue(intern_schedule(view)['public_capacity_insufficient'])

    def test_public_token_destinations_match_engine_for_both_roles_and_all_faces(self):
        for airport in ('LOG_ATL_GREEN', 'LOG_HND_RED'):
            for role in ('pilot', 'kopilot'):
                for face in range(1, 7):
                    with self.subTest(airport=airport, role=role, face=face):
                        env = fresh(airport, role)
                        others = [n for n in range(1, 7) if n != face]
                        env.game.zusatz.praktikant = [face] + others if role == 'pilot' else others + [face]
                        env.game._wuerfel_liste(role)[0].augenzahl = 1 if face != 1 else 2
                        play(env, 0, 21 if role == 'pilot' else 22)
                        raw = env.action_mask()
                        expected = {action.slot for flag, action in zip(raw, MODULE_ACTIONS)
                                    if flag and action.kind == 'bonus_place'}
                        self.assertEqual(set(_token_targets(env.view(), face)), expected)
                        advice = intern_reference(env.view(), raw, beam=8)
                        self.assertTrue(any(advice))
                        self.assertTrue(all(not flag or raw[i] for i, flag in enumerate(advice)))

    def test_last_regular_die_is_replaced_by_real_token_and_fills_thrust(self):
        env = fresh()
        for die, slot in ((0, 0), (0, 1), (1, 7), (1, 10), (2, 17), (2, 3)):
            play(env, die, slot)
        train = index('place', die=3, slot=21)
        self.assertTrue(intern_reference(env.view(), env.action_mask())[train])
        env.step(train)
        self.assertEqual(sum(bool(value) for value in env.view()['own_dice']), 0)
        thrust = index('bonus_place', slot=2)
        reference = intern_reference(env.view(), env.action_mask())
        self.assertEqual([i for i, flag in enumerate(reference) if flag], [thrust])
        env.step(thrust)
        self.assertTrue(env.game.cockpit.pflichtfelder_erfuellt())

    def test_pending_token_clears_actual_front_traffic(self):
        env = fresh()
        for die, slot in ((0, 0), (0, 1), (2, 2), (2, 3), (1, 7), (1, 10)):
            play(env, die, slot)
        landing = env.game.landung
        landing.flugzeuge[:] = [0] * len(landing.flugzeuge)
        front = landing.get_entfernungswerte().index(landing.entfernung)
        landing.flugzeuge[front] = 1
        play(env, 3, 21)
        radio = index('bonus_place', slot=4)
        reference = intern_reference(env.view(), env.action_mask())
        self.assertTrue(reference[radio])
        env.step(radio)
        self.assertEqual(landing.flugzeuge[front], 0)

    def test_pending_token_pays_actual_kerosene_once(self):
        env = fresh('LOG_HND_RED')
        for die, slot in ((0, 0), (0, 1), (2, 2), (2, 3), (1, 7), (1, 10)):
            play(env, die, slot)
        env.game.cockpit.kerosin = 8
        play(env, 3, 21)
        fuel = index('bonus_place', slot=20)
        reference = intern_reference(env.view(), env.action_mask())
        self.assertTrue(reference[fuel])
        env.step(fuel)
        self.assertEqual(env.game.cockpit.kerosin, 7)
        self.assertFalse(env.game.cockpit.kerosin_feld.ist_frei())

    def test_private_faces_real_rng_and_inputs_are_untouched(self):
        env = fresh()
        view, mask = env.view(), env.action_mask()
        before = deepcopy(view), list(mask), env.rng.getstate(), random.getstate()
        advice = intern_reference(view, mask)
        self.assertEqual((view, mask, env.rng.getstate(), random.getstate()), before)
        for die in env.game.kopilot_wuerfel:
            die.augenzahl = 7 - die.augenzahl
        self.assertEqual(intern_reference(env.view(), env.action_mask()), advice)
        view['modules_state']['modules'].append('wind')
        self.assertEqual(intern_reference(view, mask), mask)


if __name__ == '__main__':
    unittest.main()
