"""Engine-checked capacity boundaries; no changes to current player profiles."""
from copy import deepcopy
import unittest

from ai.actions import Action
from ai.module_capacity import control_budget, reserve_controls
from ai.modules import ModuleEnv, MODULE_ACTIONS


def selected(kind, **fields):
    return MODULE_ACTIONS.index(Action(kind, **fields))


def execute(env, kind, **fields):
    action = selected(kind, **fields)
    assert env.action_mask()[action]
    return env.step(action)


def ordinary_bottleneck(airport='LOG_PRG_GREEN', abilities=('adaptation', 'working-together')):
    env = ModuleEnv(airport, abilities=abilities, clock=lambda: 0.)
    env.reset(seed='train:module-capacity:251048')
    for role in ('pilot', 'kopilot'):
        for die, face in zip(env.game._wuerfel_liste(role), (3, 1, 2, 4)):
            die.augenzahl = face
    if 'intern' in env.game.cockpit.module:
        env.game.zusatz.praktikant = [1, 2, 3, 4, 5, 6]
    for die, slot in ((0, 0), (0, 1), (1, 7), (1, 10), (2, 17), (2, 3)):
        execute(env, 'place', die=die, slot=slot)
    return env


def future_sync_bottleneck():
    env = ModuleEnv('LOG_PRG_GREEN', abilities=['adaptation', 'synchronisation'], clock=lambda: 0.)
    env.reset(seed='train:module-capacity:251049')
    for die, face in zip(env.game.pilot_wuerfel, (1, 2, 3, 4)):
        die.augenzahl = face
    for die, face in zip(env.game.kopilot_wuerfel, (3, 2, 1, 4)):
        die.augenzahl = face
    for die, slot in ((0, 7), (0, 1), (1, 17), (1, 18)):
        execute(env, 'place', die=die, slot=slot)
    return env


class ModuleCapacityTests(unittest.TestCase):
    def test_last_regular_die_is_reserved_and_helpers_remain_available(self):
        env = ordinary_bottleneck()
        view, raw = env.view(), env.action_mask()
        budget = control_budget(view)
        self.assertEqual(budget['regular']['pilot'], 1)
        self.assertEqual(budget['missing_by_role']['pilot'], 1)
        result = reserve_controls(view, raw)
        thrust = selected('place', die=3, slot=2)
        coffee_preparation = selected('place', die=3, slot=18)
        self.assertTrue(raw[coffee_preparation])
        self.assertFalse(result[coffee_preparation])
        self.assertTrue(result[thrust])
        for index, action in enumerate(MODULE_ACTIONS):
            if raw[index] and action.kind != 'place':
                self.assertTrue(result[index], action)
        self.assertTrue(result[selected('adaptation', die=3)])
        self.assertTrue(result[selected('swap_start')])
        self.assertTrue(result[selected('reroll_start')])
        self.assertTrue(any(flag and action.kind == 'coffee'
                            for flag, action in zip(result, MODULE_ACTIONS)))
        self.assertTrue(all(not flag or raw[index] for index, flag in enumerate(result)))
        execute(env, 'place', die=3, slot=2)
        self.assertTrue(env.game.cockpit.pflichtfelder_erfuellt())

    def test_intern_training_replaces_reserved_die_and_issued_token_fills_control(self):
        env = ordinary_bottleneck('LOG_ATL_GREEN', ())
        raw = env.action_mask()
        training = selected('place', die=3, slot=21)
        self.assertTrue(raw[training])
        self.assertTrue(reserve_controls(env.view(), raw)[training])
        execute(env, 'place', die=3, slot=21)
        budget = control_budget(env.view())
        self.assertEqual(budget['regular']['pilot'], 0)
        self.assertEqual(budget['issued_intern']['pilot'], 1)
        self.assertEqual(budget['shared_bonus'], 0)
        self.assertEqual(budget['available_by_role']['pilot'], 1)
        raw = env.action_mask()
        forced = reserve_controls(env.view(), raw)
        thrust = selected('bonus_place', slot=2)
        radio = selected('bonus_place', slot=4)
        self.assertTrue(raw[radio])
        self.assertFalse(forced[radio])
        self.assertTrue(forced[thrust])
        execute(env, 'bonus_place', slot=2)
        self.assertTrue(env.game.cockpit.pflichtfelder_erfuellt())

    def test_future_sync_abstains_without_inventing_a_die_then_counts_issued_one_once(self):
        env = future_sync_bottleneck()
        view, raw = env.view(), env.action_mask()
        budget = control_budget(view)
        self.assertEqual(budget['regular']['pilot'], 2)
        self.assertEqual(budget['missing_by_role']['pilot'], 2)
        self.assertTrue(budget['future_sync_uncertain'])
        self.assertEqual(budget['shared_bonus'], 0)
        self.assertEqual(budget['total_available'], 4)
        self.assertEqual(reserve_controls(view, raw), raw)
        # A real legal radio+flap sequence creates the black die after the
        # apparent own-hand shortage. Hard reservation before this is unsound.
        execute(env, 'place', die=2, slot=4)
        execute(env, 'place', die=2, slot=10)
        budget = control_budget(env.view())
        self.assertFalse(budget['future_sync_uncertain'])
        self.assertEqual(budget['shared_bonus'], 1)
        self.assertEqual(budget['total_available'], 3)
        self.assertEqual(budget['deficit_by_role'], {'pilot': 1, 'kopilot': 0})
        self.assertTrue(reserve_controls(env.view(), env.action_mask())[selected('bonus_roll')])
        execute(env, 'bonus_roll')
        raw = env.action_mask()
        result = reserve_controls(env.view(), raw)
        self.assertTrue(result[selected('bonus_place', slot=0)])
        self.assertTrue(result[selected('bonus_place', slot=2)])
        # The copilot has its own regular die for thrust; spending the single
        # shared die there cannot also fill the pilot's two remaining controls.
        self.assertTrue(raw[selected('bonus_place', slot=3)])
        self.assertFalse(result[selected('bonus_place', slot=3)])
        execute(env, 'bonus_place', slot=0)
        self.assertEqual(control_budget(env.view())['shared_bonus'], 0)
        self.assertTrue(reserve_controls(env.view(), env.action_mask())[selected('place', die=3, slot=2)])

    def test_two_deficits_cannot_both_spend_the_one_shared_die(self):
        env = future_sync_bottleneck()
        execute(env, 'place', die=2, slot=4)
        execute(env, 'place', die=2, slot=10)
        execute(env, 'bonus_roll')
        view, raw = env.view(), env.action_mask()
        # An explicitly hypothetical public count makes two deficits. The
        # budget reports infeasibility and leaves rescue decisions to search.
        view['partner_remaining'] = 0
        budget = control_budget(view)
        self.assertEqual(sum(budget['deficit_by_role'].values()), 2)
        self.assertEqual(budget['shared_bonus'], 1)
        self.assertEqual(reserve_controls(view, raw), raw)

    def test_spare_intern_or_shared_die_does_not_force_an_optional_control(self):
        env = ModuleEnv('LOG_ATL_GREEN', clock=lambda: 0.)
        env.reset(seed='train:module-capacity:spare-intern')
        token = env.game.zusatz.praktikant[0]
        env.game.pilot_wuerfel[0].augenzahl = 1 if token != 1 else 2
        execute(env, 'place', die=0, slot=21)
        budget = control_budget(env.view())
        self.assertGreaterEqual(budget['regular']['pilot'], budget['missing_by_role']['pilot'])
        self.assertEqual(reserve_controls(env.view(), env.action_mask()), env.action_mask())

    def test_unknown_state_or_empty_result_abstains_and_inputs_are_detached(self):
        env = ordinary_bottleneck()
        view, raw = env.view(), env.action_mask()
        saved_view, saved_raw = deepcopy(view), list(raw)
        reserve_controls(view, raw)
        self.assertEqual(view, saved_view)
        self.assertEqual(raw, saved_raw)
        optional_only = [False] * len(raw)
        optional_only[selected('place', die=3, slot=18)] = True
        self.assertEqual(reserve_controls(view, optional_only), optional_only)
        view['modules_state']['pending'] = {'source': 'future-unknown-token', 'role': 'pilot'}
        self.assertEqual(reserve_controls(view, raw), raw)
        with self.assertRaises(ValueError):
            reserve_controls(saved_view, [True])

    def test_private_partner_faces_and_rng_cannot_enter_the_public_api(self):
        env = ordinary_bottleneck()
        before_view = deepcopy(env.view())
        before_budget = control_budget(before_view)
        before_mask = reserve_controls(before_view, env.action_mask())
        for die in env.game.kopilot_wuerfel:
            if die.ist_verfuegbar():
                die.augenzahl = 7 - die.augenzahl
        env.rng.seed('unrelated-engine-rng')
        self.assertEqual(env.view(), before_view)
        self.assertEqual(control_budget(env.view()), before_budget)
        self.assertEqual(reserve_controls(env.view(), env.action_mask()), before_mask)


if __name__ == '__main__':
    unittest.main()
