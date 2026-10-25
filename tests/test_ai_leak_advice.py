"""Public profile-11 leak scoring: exact fuel costs, soft masks and privacy."""
from copy import deepcopy
import math
import random
import unittest

from backend import bridge
from ai.actions import ACTIONS, Action
from ai.browser_bridge import decision
from ai.leak_advice import leak_reference, make_leak_adjustment
from ai.module_physics import fuel_budget
from ai.modules import CARDS, MODULE_ACTIONS, ModuleEnv
from ai.tactics import plan_actions


def fresh(card='control', role='pilot', *, profile=0):
    env = ModuleEnv('LOG_ATL_YELLOW', abilities=[card], assistance_version=profile, clock=lambda: 0.)
    env.reset(seed='train:leak-advice:251054')
    env.game.am_zug = role
    env.game.landung.flugzeuge[:] = [0]*len(env.game.landung.flugzeuge)
    for owner in ('pilot', 'kopilot'):
        for die, face in zip(env.game._wuerfel_liste(owner), (3, 1, 4, 6)):
            die.augenzahl = face
    return env


def public_partner_thrust(env, face):
    role = env.current_role
    partner = env.other_role(role)
    env.game.am_zug = partner
    env.game._wuerfel_liste(partner)[0].augenzahl = face
    result = env.game.platziere(partner, 0, 'triebwerk')
    if not result.erfolg: raise AssertionError(result)
    if env.game.am_zug != role: raise AssertionError('Expected regular turn to return.')


class LeakAdviceTests(unittest.TestCase):
    def test_public_leak_pair_cost_matches_engine_and_paid_pair_is_not_charged_twice(self):
        for role in ('pilot', 'kopilot'):
            env = fresh(role=role)
            env.game.cockpit.kerosin = 3
            env.game.landung.hoehe = 1000
            public_partner_thrust(env, 3)
            view = env.view()
            adjust = make_leak_adjustment(view)
            self.assertGreater(adjust(3, 3), adjust(1, 3))
            for own in (1, 3):
                game = deepcopy(env.game)
                game._wuerfel_liste(role)[0].augenzahl = own
                actual = game.platziere(role, 0, 'triebwerk')
                pilot, kopilot = (own, 3) if role == 'pilot' else (3, own)
                projected = fuel_budget(view, pilot, kopilot)
                self.assertEqual(game.cockpit.kerosin, projected['after_current'])
                self.assertEqual(actual.grund, projected['reason'])
            self.assertTrue(env.game.platziere(role, 0, 'triebwerk').erfolg)
            self.assertEqual(env.game.cockpit.kerosin, 2)
            self.assertEqual(make_leak_adjustment(env.view())(3, 3), 0.)
            # Mutation outside the helper cannot corrupt its cached snapshot.
            view['fuel']['remaining'] = 20
            self.assertLess(adjust(1, 3), -1000)

    def test_zero_fuel_is_fatal_even_on_last_round(self):
        for remaining in (1, 2):
            env = fresh()
            env.game.cockpit.kerosin = remaining
            env.game.letzte_runde = True
            env.game.landung.hoehe = 0
            public_partner_thrust(env, 3)
            view = env.view()
            adjusted = make_leak_adjustment(view)(3, 3)
            result = env.game.platziere('pilot', 0, 'triebwerk')
            self.assertEqual(result.verloren, remaining == 1)
            self.assertEqual(result.grund, 'kerosin_leer' if remaining == 1 else '')
            self.assertEqual(adjusted < -1000, remaining == 1)

    def test_optional_hook_scores_landing_holding_and_early_overshoot(self):
        env = fresh(); public_partner_thrust(env, 3)
        original = env.view()
        original['own_dice'] = [0, 0, 0, 3]
        original['board'][0] = {'value': 3, 'owner': 'pilot'}
        mask = [False]*len(ACTIONS)
        mask[ACTIONS.index(Action('place', die=3, slot=2))] = True
        for case in ('landing', 'holding', 'overshoot'):
            view = deepcopy(original)
            view['last_round'] = case == 'landing'
            view['holding'] = case == 'holding'
            view['brakes'] = 2
            if case == 'overshoot':
                view['distance'], view['aero_blue'], view['aero_orange'] = 1, 2, 4
            seen = []
            def callback(own, other):
                seen.append((own, other))
                return -7.
            plain, _ = plan_actions(view, mask, beam=8, version=4)
            changed, _ = plan_actions(view, mask, beam=8, version=4, thrust_score_adjustment=callback)
            self.assertTrue(seen, case)
            self.assertTrue(all(pair == (3, 3) for pair in seen))
            self.assertEqual(set(plain), set(changed))
            self.assertTrue(all(math.isclose(changed[key], value-7.) for key, value in plain.items()))

    def test_zero_adjustment_preserves_existing_rankings_and_invalid_hooks_fail(self):
        for airport in ('MUC', 'LOG_OSL_GREEN'):
            env = ModuleEnv(airport, clock=lambda: 0.)
            env.reset(seed='train:leak-hook-zero')
            view, raw = env.view(), env.action_mask()
            prefix = raw[:125 if view['fuel']['present'] else len(ACTIONS)]
            before = deepcopy(view)
            rng = random.getstate()
            for version in (3, 4):
                plain = plan_actions(view, prefix, beam=12, version=version)
                explicit = plan_actions(view, prefix, beam=12, version=version, thrust_score_adjustment=None)
                zero = plan_actions(view, prefix, beam=12, version=version, thrust_score_adjustment=lambda *_: 0.)
                self.assertEqual(plain, explicit)
                self.assertEqual(plain, zero)
            self.assertEqual(view, before)
            self.assertEqual(random.getstate(), rng)
            with self.assertRaises(ValueError): plan_actions(view, prefix, thrust_score_adjustment=3)
            with self.assertRaises(ValueError):
                plan_actions(view, prefix, beam=8, thrust_score_adjustment=lambda *_: float('nan'))

    def test_all_six_cards_remain_legal_public_soft_and_have_no_kerosene_field(self):
        for card in CARDS:
            for role in ('pilot', 'kopilot'):
                env = fresh(card, role)
                view, raw = env.view(), env.action_mask()
                self.assertFalse(view['fuel']['present'])
                before, rng = deepcopy(view), random.getstate()
                env.assistance_version = 11
                info = env.info()
                self.assertTrue(any(info['action_mask']))
                self.assertTrue(any(info['reference_action_mask']))
                self.assertFalse(any(advice and not allowed for advice, allowed in
                    zip(info['reference_action_mask'], info['action_mask'])))
                self.assertFalse(any(allowed and not legal for allowed, legal in zip(info['action_mask'], raw)))
                self.assertFalse(any(allowed and action.kind == 'place' and action.slot == 20
                    for allowed, action in zip(info['action_mask'], MODULE_ACTIONS)))
                self.assertTrue(any(allowed and not advice for allowed, advice in
                    zip(info['action_mask'], info['reference_action_mask'])))
                self.assertEqual(view, before)
                self.assertEqual(random.getstate(), rng)
                for die in env.game._wuerfel_liste(env.other_role(role)):
                    if die.ist_verfuegbar(): die.augenzahl = 7-die.augenzahl
                self.assertEqual(env.view(), before)
                self.assertEqual(env.info()['action_mask'], info['action_mask'])
                self.assertEqual(env.info()['reference_action_mask'], info['reference_action_mask'])

    def test_new_profile_keeps_all_old_module_fallbacks_exact(self):
        for airport, cards in (('MUC', []), ('LOG_OSL_GREEN', []), ('LOG_ATL_GREEN', []),
                ('LOG_GIG_YELLOW', ['control']), ('LOG_KEF_YELLOW', ['control']),
                ('LOG_GIG_RED', ['adaptation', 'control']), ('LOG_OSL_RED', ['adaptation', 'control'])):
            env = ModuleEnv(airport, abilities=cards, assistance_version=10, clock=lambda: 0.)
            env.reset(seed='train:leak-fallback')
            old = env.info()
            env.assistance_version = 11
            self.assertEqual(env.info()['action_mask'], old['action_mask'])
            self.assertEqual(env.info()['reference_action_mask'], old['reference_action_mask'])

    def test_pending_black_die_and_swap_abstain_and_browser_sees_same_profile_11(self):
        env = fresh('synchronisation', profile=11)
        env.game.pilot_wuerfel[0].augenzahl = 1
        env.step(MODULE_ACTIONS.index(Action('place', die=0, slot=7)))
        env.game.kopilot_wuerfel[0].augenzahl = 1
        env.step(MODULE_ACTIONS.index(Action('place', die=0, slot=10)))
        self.assertEqual(env.view()['modules_state']['pending']['source'], 'synchronisation')
        allowed = env.info()['action_mask']
        self.assertEqual(leak_reference(env.view(), allowed), allowed)
        self.assertEqual(env.info()['reference_action_mask'], allowed)
        old = bridge._spiel
        try:
            bridge._spiel = env.game
            browser = decision(env.current_role, 'null', env.steps, env.max_steps, 11, 3)
            self.assertEqual(browser['reference_action_mask'], env.info()['reference_action_mask'])
            self.assertEqual(browser['action_mask'], allowed)
            self.assertEqual(browser['observation'], env.observation())
        finally:
            bridge._spiel = old
        env = fresh('working-together', profile=11)
        env.step(MODULE_ACTIONS.index(Action('swap_start')))
        info = env.info()
        self.assertEqual(leak_reference(env.view(), info['action_mask']), info['action_mask'])
        self.assertFalse(info['action_mask'][MODULE_ACTIONS.index(Action('swap_cancel'))])


if __name__ == '__main__': unittest.main()
