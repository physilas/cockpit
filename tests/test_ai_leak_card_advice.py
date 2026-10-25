"""Profile-12 public adaptation macros, independent of NN quality claims."""
from copy import deepcopy
import json
import random
import unittest
from unittest.mock import patch

from backend import bridge
from ai.actions import ACTIONS, Action
from ai.browser_bridge import decision
from ai.leak_advice import leak_reference
from ai.leak_card_advice import leak_card_reference, virtual_first_mask
from ai.modules import MODULE_ACTIONS, ModuleEnv


def rescue_env(role='pilot'):
    """Legal public sequence: last own face1 stalls against public rudder4."""
    env = ModuleEnv('LOG_ATL_YELLOW', abilities=['adaptation'], clock=lambda: 0.)
    env.reset(seed='train:profile12-card-rescue')
    game = env.game
    game.landung.flugzeuge[:] = [0] * len(game.landung.flugzeuge)
    game.neuwurf_plaettchen = 0
    for owner in ('pilot', 'kopilot'):
        for die in game._wuerfel_liste(owner):
            die.augenzahl = 1
    if role == 'pilot':
        moves = [('pilot', 1, 'triebwerk', None, 3),
                 ('kopilot', 0, 'ruder', None, 4),
                 ('pilot', 2, 'funk', None, 1),
                 ('kopilot', 1, 'triebwerk', None, 3),
                 ('pilot', 3, 'fahrwerk', 0, 1),
                 ('kopilot', 2, 'landeklappe', 0, 1)]
    else:
        moves = [('pilot', 0, 'ruder', None, 4),
                 ('kopilot', 1, 'triebwerk', None, 3),
                 ('pilot', 1, 'triebwerk', None, 3),
                 ('kopilot', 2, 'landeklappe', 0, 1),
                 ('pilot', 2, 'fahrwerk', 0, 1),
                 ('kopilot', 3, 'funk', None, 1),
                 ('pilot', 3, 'fahrwerk', 1, 3)]
    for owner, die, target, index, face in moves:
        game._wuerfel_liste(owner)[die].augenzahl = face
        result = game.platziere(owner, die, target, index)
        if not result.erfolg or result.verloren:
            raise AssertionError((owner, target, result))
    if game.am_zug != role or env.view()['own_dice'] != [1, 0, 0, 0]:
        raise AssertionError('Expected the last own die without fabricating turn order.')
    return env


def action_id(kind, *, die=0, slot=-1, delta=0):
    return MODULE_ACTIONS.index(Action(kind, die=die, slot=slot, delta=delta))


class LeakCardAdviceTests(unittest.TestCase):
    def test_both_roles_recommend_the_public_rescue_without_changing_profile11(self):
        for role in ('pilot', 'kopilot'):
            with self.subTest(role=role):
                env = rescue_env(role)
                rudder = action_id('place', slot=0 if role == 'pilot' else 1)
                adaptation = action_id('adaptation')
                env.assistance_version = 11
                historical = deepcopy(env.info())
                self.assertTrue(historical['action_mask'][adaptation])
                self.assertTrue(historical['reference_action_mask'][rudder])
                self.assertEqual(sum(historical['reference_action_mask']), 1)
                bad_game = deepcopy(env.game)
                bad = bad_game.platziere(role, 0, 'ruder')
                self.assertTrue(bad.verloren)
                self.assertEqual(bad.grund, 'trudeln')

                env.assistance_version = 12
                improved = env.info()
                self.assertEqual(improved['action_mask'], historical['action_mask'])
                self.assertTrue(improved['reference_action_mask'][adaptation])
                self.assertFalse(improved['reference_action_mask'][rudder])
                env.step(adaptation)
                self.assertEqual(env.game._wuerfel_liste(role)[0].augenzahl, 6)
                self.assertTrue(env.info()['reference_action_mask'][rudder])
                # Test the immediate physical consequence without auto-resolving
                # another round or claiming eventual victory.
                good = env.game.platziere(role, 0, 'ruder')
                self.assertTrue(good.erfolg)
                self.assertFalse(good.verloren)
                self.assertEqual(env.game.cockpit.fluglage, -2 if role == 'pilot' else 2)

                unchanged = rescue_env(role)
                unchanged.assistance_version = 11
                self.assertEqual(unchanged.info(), historical)

    def test_adaptation_is_once_per_player_per_flight_across_real_round_end(self):
        env = rescue_env()
        game = env.game
        self.assertTrue(game.zusatz.aktion('pilot', 'adaptation', {'wuerfel_index': 0}).erfolg)
        self.assertTrue(game.platziere('pilot', 0, 'ruder').erfolg)
        self.assertTrue(game.platziere('kopilot', 3, 'funk').erfolg)
        old_round = game.aktuelle_runde
        # The environment owns an isolated engine RNG even for real transition
        # rolls; no test mutates the global RNG or reads future game faces.
        with env._engine_randomness():
            ended = game.rundenende()
            env._advance()
        self.assertTrue(ended.erfolg)
        self.assertFalse(ended.verloren)
        self.assertEqual(game.aktuelle_runde, old_round + 1)
        self.assertTrue(game.zusatz.anpassung['pilot'])
        self.assertFalse(game.zusatz.anpassung['kopilot'])
        failed = game.zusatz.aktion('pilot', 'adaptation', {'wuerfel_index': 0})
        self.assertFalse(failed.erfolg)
        self.assertEqual(failed.grund, 'karte_nicht_verfuegbar')
        # Off-turn adaptation remains a real engine card effect; the partner
        # has its independent once-per-flight allowance.
        self.assertTrue(game.zusatz.aktion('kopilot', 'adaptation', {'wuerfel_index': 0}).erfolg)

    def test_virtual_first_mask_rechecks_new_face_against_engine(self):
        env = ModuleEnv('LOG_ATL_YELLOW', abilities=['adaptation'], clock=lambda: 0.)
        env.reset(seed='train:profile12-virtual-face')
        game = env.game
        # All own controls already occupied: a single optional die can use a
        # new gear destination after flipping, rather than the stale old one.
        game.landung.flugzeuge[:] = [0] * len(game.landung.flugzeuge)
        for owner, die, target, index, face in (
                ('pilot', 1, 'triebwerk', None, 3), ('kopilot', 0, 'ruder', None, 4),
                ('pilot', 2, 'ruder', None, 4), ('kopilot', 1, 'triebwerk', None, 3),
                ('pilot', 3, 'funk', None, 1), ('kopilot', 2, 'landeklappe', 0, 1)):
            game._wuerfel_liste(owner)[die].augenzahl = face
            result = game.platziere(owner, die, target, index)
            self.assertTrue(result.erfolg)
            self.assertFalse(result.verloren)
        game.pilot_wuerfel[0].augenzahl = 1
        game.cockpit.kaffeetassen = 1
        before = env.view()
        self.assertTrue(virtual_first_mask(before)[ACTIONS.index(Action('place', die=0, slot=7))])
        self.assertFalse(virtual_first_mask(before)[ACTIONS.index(Action('place', die=0, slot=9))])
        virtual = deepcopy(before)
        virtual['own_dice'][0] = 6
        virtual['modules_state']['adaptation']['pilot'] = False
        snapshot = deepcopy(virtual)
        mask = virtual_first_mask(virtual)
        self.assertEqual(virtual, snapshot)
        self.assertEqual(len(mask), len(ACTIONS))
        self.assertTrue(all(type(flag) is bool for flag in mask))
        self.assertFalse(mask[ACTIONS.index(Action('place', die=0, slot=7))])
        self.assertTrue(mask[ACTIONS.index(Action('place', die=0, slot=9))])
        self.assertTrue(mask[ACTIONS.index(Action('coffee', die=0, delta=-1))])
        self.assertFalse(mask[ACTIONS.index(Action('coffee', die=0, delta=1))])
        self.assertFalse(any(selected and action.die > 0 for action, selected in zip(ACTIONS, mask)))
        self.assertFalse(mask[ACTIONS.index(Action('reroll_start'))])
        self.assertTrue(game.zusatz.aktion('pilot', 'adaptation', {'wuerfel_index': 0}).erfolg)
        expected = env.action_mask()[:len(ACTIONS)]
        expected[ACTIONS.index(Action('reroll_start'))] = False
        self.assertEqual(mask, expected)

    def test_public_inputs_masks_and_both_rngs_are_unchanged_and_partner_private_faces_irrelevant(self):
        env = rescue_env()
        env.assistance_version = 11
        allowed = env.info()['action_mask']
        view = env.view()
        snapshot = deepcopy((view, allowed))
        global_rng, private_rng = random.getstate(), env.rng.getstate()
        first = leak_card_reference(view, allowed, beam=8)
        self.assertEqual((view, allowed), snapshot)
        self.assertEqual(random.getstate(), global_rng)
        self.assertEqual(env.rng.getstate(), private_rng)
        self.assertTrue(any(first))
        self.assertFalse(any(advised and not legal for advised, legal in zip(first, allowed)))
        for die in env.game.kopilot_wuerfel:
            if die.ist_verfuegbar():
                die.augenzahl = 7 - die.augenzahl
        self.assertEqual(env.view(), view)
        self.assertEqual(leak_card_reference(env.view(), allowed, beam=8), first)

    def test_repeated_reference_is_invariant_to_cpu_pacing_and_simulated_work_clock(self):
        env = rescue_env()
        env.assistance_version = 11
        allowed, view = env.info()['action_mask'], env.view()
        expected = leak_card_reference(view, allowed, beam=8)
        for duty in (1., .7, .25):
            with self.subTest(duty=duty):
                # Force the cooperative-pause branch to execute on every
                # meaningful interval. Time must affect pacing, never which
                # candidate is evaluated or shortlisted.
                ticks = iter(index * .03 for index in range(10000))
                with patch('ai.leak_card_advice.time.perf_counter', side_effect=lambda: next(ticks)), \
                        patch('ai.leak_card_advice.CpuBudget.pause', autospec=True) as paused:
                    first = leak_card_reference(view, allowed, beam=8, cpu_duty_cycle=duty)
                    second = leak_card_reference(view, allowed, beam=8, cpu_duty_cycle=duty)
                self.assertGreater(paused.call_count, 0)
                self.assertEqual(first, expected)
                self.assertEqual(second, expected)

    def test_masked_out_or_consumed_adaptation_falls_back_exactly_to_profile11(self):
        for reason in ('masked', 'consumed', 'absent'):
            with self.subTest(reason=reason):
                env = rescue_env()
                if reason == 'consumed':
                    env.game.zusatz.anpassung['pilot'] = True
                elif reason == 'absent':
                    env.game.zusatz.karten[:] = ['control']
                env.assistance_version = 11
                allowed = env.info()['action_mask']
                if reason == 'masked':
                    allowed[action_id('adaptation')] = False
                view = env.view()
                expected = leak_reference(view, allowed, beam=8)
                self.assertEqual(leak_card_reference(view, allowed, beam=8), expected)
                if reason != 'masked':
                    historical = env.info()
                    env.assistance_version = 12
                    self.assertEqual(env.info(), historical)

    def test_existing_nonleak_module_paths_remain_exact_profile11_fallbacks(self):
        for airport, cards in (('MUC', []), ('LOG_OSL_GREEN', []),
                               ('LOG_ATL_GREEN', []), ('LOG_GIG_YELLOW', ['control']),
                               ('LOG_KEF_YELLOW', ['control']),
                               ('LOG_GIG_RED', ['adaptation', 'control'])):
            with self.subTest(airport=airport):
                env = ModuleEnv(airport, abilities=cards, clock=lambda: 0.)
                env.reset(seed='train:profile12-legacy-fallback')
                env.assistance_version = 11
                historical = env.info()
                env.assistance_version = 12
                self.assertEqual(env.info(), historical)

    def test_terminal_masks_and_explicit_work_bounds_fail_closed(self):
        env = rescue_env()
        view, allowed = env.view(), env.action_mask()
        blank = [False] * len(MODULE_ACTIONS)
        self.assertEqual(leak_card_reference(view, blank), blank)
        for mask in ([True], [1] * len(MODULE_ACTIONS)):
            with self.assertRaises(ValueError):
                leak_card_reference(view, mask)
        for beam in (0, 25, True):
            with self.assertRaises(ValueError):
                leak_card_reference(view, allowed, beam=beam)
        for cost in (0, -1, float('nan')):
            with self.assertRaises(ValueError):
                leak_card_reference(view, allowed, card_cost=cost)

    def test_native_browser_bridge_profile12_parity_before_and_after_rescue(self):
        previous = bridge._spiel
        try:
            for role in ('pilot', 'kopilot'):
                env = rescue_env(role)
                env.assistance_version = 12
                for _ in range(2):
                    bridge._spiel = env.game
                    global_rng, own_rng = random.getstate(), env.rng.getstate()
                    actual = decision(role, json.dumps(env.reroll), env.steps, env.max_steps, 12, 3)
                    info = env.info()
                    self.assertEqual(actual['observation'], env.observation())
                    self.assertEqual(actual['action_mask'], info['action_mask'])
                    self.assertEqual(actual['reference_action_mask'], info['reference_action_mask'])
                    self.assertEqual(actual['role'], role)
                    for hidden in ('own_dice', 'pilot_wuerfel', 'kopilot_wuerfel'):
                        self.assertNotIn(hidden, actual['public_state'])
                    self.assertEqual(random.getstate(), global_rng)
                    self.assertEqual(env.rng.getstate(), own_rng)
                    if not env.game.zusatz.anpassung[role]:
                        env.step(action_id('adaptation'))
        finally:
            bridge._spiel = previous


if __name__ == '__main__':
    unittest.main()
