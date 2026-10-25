"""Small engine/public fixtures for isolated donation advice, not win evidence."""
from copy import deepcopy
import random
import unittest
from unittest.mock import patch

from ai.actions import Action
from ai.leak_card_advice import leak_card_reference
from ai.leak_donation_advice import donation_candidates, leak_donation_reference
from ai.modules import MODULE_ACTIONS, ModuleEnv


def action_id(kind, *, die=-1, slot=-1):
    return MODULE_ACTIONS.index(Action(kind, die=die, slot=slot))


def donation_env():
    """Five actual legal placements; donor C has [1,3], recipient P one die1."""
    env = ModuleEnv('LOG_ATL_YELLOW', abilities=['working-together'], clock=lambda: 0.)
    env.reset(seed='train:isolated-public-leak-donation:251060')
    game = env.game
    for owner, hand in (('pilot', (1, 3, 2, 1)), ('kopilot', (4, 3, 1, 3))):
        for die, face in zip(game._wuerfel_liste(owner), hand):
            die.augenzahl = face
    for owner, index, target, field in (
            ('pilot', 0, 'funk', None), ('kopilot', 0, 'ruder', None),
            ('pilot', 1, 'triebwerk', None), ('kopilot', 1, 'triebwerk', None),
            ('pilot', 2, 'bremse', 0)):
        placed = game.platziere(owner, index, target, field)
        if not placed.erfolg or placed.verloren:
            raise AssertionError((owner, target, placed))
    if game.am_zug != 'kopilot' or env.view()['own_dice'] != [0, 0, 1, 3]:
        raise AssertionError('The fixture must reach the real donor turn.')
    return env


class LeakDonationAdviceTests(unittest.TestCase):
    def test_engine_rescue_starts_and_gives_the_safe_known_face(self):
        env = donation_env()
        raw, view = env.action_mask(), env.view()
        gifts = donation_candidates(view)
        self.assertEqual(set(gifts), {3})
        self.assertEqual(gifts[3]['face'], 3)
        self.assertEqual(gifts[3]['attitude'], 1)
        # Ordinary play without the exchange really stalls the pilot.
        ordinary = deepcopy(env.game)
        self.assertTrue(ordinary.platziere('kopilot', 2, 'landeklappe', 0).erfolg)
        bad = ordinary.platziere('pilot', 3, 'ruder')
        self.assertTrue(bad.verloren)
        self.assertEqual(bad.grund, 'trudeln')

        start = action_id('swap_start')
        self.assertTrue(raw[start])
        reference = leak_donation_reference(view, raw)
        self.assertEqual([index for index, flag in enumerate(reference) if flag], [start])
        env.step(start)
        self.assertEqual(env.current_role, 'kopilot')
        allowed = env.action_mask()
        good, poor = action_id('swap_choose', die=3), action_id('swap_choose', die=2)
        self.assertTrue(allowed[good] and allowed[poor])
        advised = leak_donation_reference(env.view(), allowed)
        self.assertTrue(advised[good])
        self.assertFalse(advised[poor])
        env.step(good)
        self.assertEqual(env.current_role, 'pilot')
        receiver = action_id('swap_choose', die=3)
        receiver_ref = leak_donation_reference(env.view(), env.action_mask())
        self.assertEqual([i for i, flag in enumerate(receiver_ref) if flag], [receiver])
        env.step(receiver)
        self.assertIsNone(env.game.zusatz.kooperation)
        self.assertEqual(env.current_role, 'kopilot')
        self.assertEqual(env.game.pilot_wuerfel[3].augenzahl, 3)
        self.assertEqual(env.game.kopilot_wuerfel[3].augenzahl, 1)
        self.assertTrue(env.game.zusatz.kooperation_genutzt)
        # No extra die is created, no control pair is paid again.
        self.assertEqual(sum(bool(face) for face in env.view()['own_dice']), 2)
        self.assertEqual(env.view()['partner_remaining'], 1)
        fuel = env.game.cockpit.kerosin
        env.step(action_id('place', die=2, slot=10))
        env.step(action_id('place', die=3, slot=0))
        self.assertEqual(env.game.status, 'laeuft')
        self.assertEqual(env.game.cockpit.fluglage, 1)
        self.assertEqual(env.game.cockpit.kerosin, fuel)

    def test_any_unknown_return_face_is_usable_without_reading_it_for_advice(self):
        baseline = None
        for hidden in range(1, 7):
            env = donation_env()
            env.game.pilot_wuerfel[3].augenzahl = hidden
            view, allowed = env.view(), env.action_mask()
            advised = leak_donation_reference(view, allowed)
            if baseline is None:
                baseline = deepcopy((view, allowed, advised))
            self.assertEqual((view, allowed, advised), baseline)
            env.step(action_id('swap_start'))
            env.step(action_id('swap_choose', die=3))
            env.step(action_id('swap_choose', die=3))
            env.step(action_id('place', die=2, slot=10))
            env.step(action_id('place', die=3, slot=0))
            concentration = action_id('place', die=3, slot=17)
            self.assertTrue(env.action_mask()[concentration])
            result = env.game.platziere('kopilot', 3, 'konzentration', 0)
            self.assertTrue(result.erfolg)
            self.assertFalse(result.verloren)
            self.assertEqual(env.game.cockpit.fluglage, 1)

    def test_own_required_face_and_unknown_return_capacity_are_protected(self):
        env = donation_env()
        view = env.view()
        # Face1 is the only current first-flap face: donate3, never1.
        self.assertEqual(set(donation_candidates(view)), {3})
        blocked = deepcopy(view)
        blocked['flaps'][0] = True
        # The first flap was deployed earlier; face3 is now the sole known
        # current face for flap2 and must not be promised to the partner.
        self.assertEqual(donation_candidates(blocked), {})
        late = deepcopy(view)
        late.update(last_round=True, height=0, attitude=-1)
        self.assertEqual(donation_candidates(late), {})

    def test_public_curves_and_landing_level_are_checked_for_the_gift(self):
        env = donation_env()
        view = env.view()
        current = next(cell for cell in view['track'] if cell['distance'] == view['distance'])
        current['min'], current['max'] = 2, 2
        self.assertEqual(donation_candidates(view), {})
        view['own_dice'][3] = 2
        self.assertEqual(donation_candidates(view)[3]['attitude'], 2)
        landing = deepcopy(view)
        landing.update(last_round=True, height=0, attitude=-2, brakes=6)
        landing['flaps'] = [True] * 4
        self.assertEqual(donation_candidates(landing)[3]['attitude'], 0)

    def test_public_inputs_rng_and_pending_partner_faces_do_not_change(self):
        env = donation_env()
        for pending in (False, True):
            if pending:
                env.step(action_id('swap_start'))
            allowed, view = env.action_mask(), env.view()
            before = deepcopy((allowed, view))
            global_rng, local_rng = random.getstate(), env.rng.getstate()
            first = leak_donation_reference(view, allowed, cpu_duty_cycle=.7)
            self.assertEqual((allowed, view), before)
            self.assertEqual(random.getstate(), global_rng)
            self.assertEqual(env.rng.getstate(), local_rng)
            self.assertTrue(any(first))
            self.assertFalse(any(advised and not legal for advised, legal in zip(first, allowed)))
            for die in env.game.pilot_wuerfel:
                if die.ist_verfuegbar():
                    die.augenzahl = 7 - die.augenzahl
            self.assertEqual(env.view(), view)
            self.assertEqual(leak_donation_reference(env.view(), allowed, cpu_duty_cycle=.7), first)

    def test_deterministic_pacing_never_changes_which_candidate_is_evaluated(self):
        env = donation_env()
        env.step(action_id('swap_start'))
        view, allowed = env.view(), env.action_mask()
        expected = leak_donation_reference(view, allowed)
        for duty in (1., .7, .25):
            with patch('ai.leak_donation_advice.CpuBudget.pause', autospec=True) as paused:
                actual = leak_donation_reference(view, allowed, cpu_duty_cycle=duty)
            self.assertGreater(paused.call_count, 0)
            self.assertEqual(actual, expected)

    def test_outside_the_narrow_case_uses_exact_profile12_reference(self):
        env = donation_env()
        original, allowed = env.view(), env.action_mask()
        for reason in ('recipient_two_dice', 'no_concentration', 'donor_control_missing',
                       'recipient_thrust_missing', 'used_card', 'absent_card',
                       'wind', 'ice', 'intern', 'pending', 'reroll', 'masked_start'):
            with self.subTest(reason=reason):
                view, mask = deepcopy(original), list(allowed)
                if reason == 'recipient_two_dice': view['partner_remaining'] = 2
                elif reason == 'no_concentration':
                    for index in range(17, 20): view['board'][index] = {'owner': 'pilot', 'value': 1}
                elif reason == 'donor_control_missing': view['board'][1] = None
                elif reason == 'recipient_thrust_missing': view['board'][2] = None
                elif reason == 'used_card': view['modules_state']['swap_available'] = False
                elif reason == 'absent_card': view['modules_state']['cards'] = ['control']
                elif reason in ('wind', 'ice', 'intern'): view['modules_state']['modules'].append(reason)
                elif reason == 'pending': view['modules_state']['pending'] = {'role': 'pilot', 'source': 'synchronisation', 'value': 3}
                elif reason == 'reroll': view['reroll'] = {'initiator': 'kopilot', 'selections': {'pilot': None, 'kopilot': None}}
                elif reason == 'masked_start': mask[action_id('swap_start')] = False
                self.assertEqual(leak_donation_reference(view, mask, beam=8),
                                 leak_card_reference(view, mask, beam=8))

    def test_malformed_masks_and_unbounded_options_fail_closed(self):
        env = donation_env()
        view, allowed = env.view(), env.action_mask()
        blank = [False] * len(MODULE_ACTIONS)
        self.assertEqual(leak_donation_reference(view, blank), blank)
        for mask in ([True], [1] * len(MODULE_ACTIONS)):
            with self.assertRaises(ValueError): leak_donation_reference(view, mask)
        for beam in (0, 25, True):
            with self.assertRaises(ValueError): leak_donation_reference(view, allowed, beam=beam)
        for duty in (0, 1.1, float('nan')):
            with self.assertRaises(ValueError): leak_donation_reference(view, allowed, cpu_duty_cycle=duty)


if __name__ == '__main__':
    unittest.main()
