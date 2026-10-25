"""Capacity advice stays synchronized with the actual module engine state."""
import unittest

from ai.actions import Action
from ai.all_modules_environment import AllModulesEnv
from ai.capacity_modules_environment import CapacityModulesEnv
from ai.module_capacity import control_budget
from ai.modules import ModuleEnv, MODULE_ACTIONS


def action(kind, **fields):
    return MODULE_ACTIONS.index(Action(kind, **fields))


def place(env, die, slot):
    return env.step(action('place', die=die, slot=slot))


def controlled(env_class=CapacityModulesEnv, airport='LOG_PRG_GREEN',
               cards=('adaptation', 'working-together')):
    env = env_class(airport, abilities=cards)
    env.reset(seed='train:capacity-env:251050')
    for role in ('pilot', 'kopilot'):
        for die, face in zip(env.game._wuerfel_liste(role), (3, 1, 2, 4)):
            die.augenzahl = face
    if 'intern' in env.game.cockpit.module:
        env.game.zusatz.praktikant = [1, 2, 3, 4, 5, 6]
    for die, slot in ((0, 0), (0, 1), (1, 7), (1, 10), (2, 17), (2, 3)):
        place(env, die, slot)
    return env


class CapacityModulesEnvironmentTests(unittest.TestCase):
    def test_raw_optional_last_die_is_removed_and_actual_mandatory_fields_finish(self):
        old = controlled(AllModulesEnv)
        env = controlled()
        optional = action('place', die=3, slot=18)
        thrust = action('place', die=3, slot=2)
        self.assertTrue(old.action_mask()[optional])
        info = env.info()
        self.assertTrue(info['raw_action_mask'][optional])
        self.assertFalse(info['action_mask'][optional])
        self.assertEqual(info['reference_action_mask'], info['action_mask'])
        self.assertTrue(info['action_mask'][thrust])
        self.assertTrue(info['action_mask'][action('swap_start')])
        env.step(thrust)
        self.assertTrue(env.game.cockpit.pflichtfelder_erfuellt())
        # In the original research environment the optional placement leaves
        # thrust empty with no remaining pilot die, exactly the audited failure.
        old.step(optional)
        self.assertFalse(old.game.cockpit.pflichtfelder_erfuellt())
        self.assertEqual(len(old.game.verfuegbare_wuerfel('pilot')), 0)

    def test_plain_base_fuel_masks_and_reference_are_exactly_unchanged(self):
        for airport in ('MUC', 'LOG_HND_GREEN', 'LOG_OSL_GREEN'):
            with self.subTest(airport=airport):
                env = CapacityModulesEnv(airport)
                old = ModuleEnv(airport, assistance_version=9)
                env.reset(seed=251050);old.reset(seed=251050)
                for _ in range(5):
                    self.assertEqual(env.action_mask(), old.action_mask())
                    self.assertEqual(env.info()['reference_action_mask'], old.info()['reference_action_mask'])
                    if env.done:
                        break
                    selected = next(i for i, valid in enumerate(env.action_mask()) if valid)
                    env.step(selected);old.step(selected)

    def test_intern_replacement_updates_masks_before_and_after_pending_token(self):
        env = controlled(airport='LOG_ATL_GREEN', cards=())
        train = action('place', die=3, slot=21)
        self.assertTrue(env.action_mask()[train])
        env.step(train)
        self.assertEqual(env.current_role, 'pilot')
        info = env.info()
        thrust, radio = action('bonus_place', slot=2), action('bonus_place', slot=4)
        self.assertTrue(info['raw_action_mask'][radio])
        self.assertFalse(info['action_mask'][radio])
        self.assertTrue(info['action_mask'][thrust])
        self.assertEqual(info['reference_action_mask'], info['action_mask'])
        env.step(thrust)
        self.assertIsNone(env.view()['modules_state']['pending'])
        self.assertEqual(env.current_role, 'kopilot')
        self.assertTrue(env.game.cockpit.pflichtfelder_erfuellt())
        self.assertEqual(env.info()['reference_action_mask'], env.action_mask())

    def test_future_then_issued_black_die_changes_current_reference_without_double_count(self):
        env = CapacityModulesEnv('LOG_PRG_GREEN', abilities=['adaptation', 'synchronisation'])
        env.reset(seed='train:capacity-env:sync:251050')
        for die, face in zip(env.game.pilot_wuerfel, (1, 2, 3, 4)):
            die.augenzahl = face
        for die, face in zip(env.game.kopilot_wuerfel, (3, 2, 1, 4)):
            die.augenzahl = face
        for die, slot in ((0, 7), (0, 1), (1, 17), (1, 18)):
            place(env, die, slot)
        self.assertTrue(control_budget(env.view())['future_sync_uncertain'])
        self.assertEqual(control_budget(env.view())['shared_bonus'], 0)
        self.assertEqual(env.info()['action_mask'], env.info()['raw_action_mask'])
        place(env, 2, 4);place(env, 2, 10)
        self.assertEqual(control_budget(env.view())['shared_bonus'], 1)
        self.assertEqual(control_budget(env.view())['total_available'], 3)
        roll = action('bonus_roll')
        self.assertTrue(env.info()['reference_action_mask'][roll])
        env.step(roll)
        info = env.info()
        own_rudder, partner_thrust = action('bonus_place', slot=0), action('bonus_place', slot=3)
        self.assertTrue(info['raw_action_mask'][partner_thrust])
        self.assertFalse(info['action_mask'][partner_thrust])
        self.assertTrue(info['reference_action_mask'][own_rudder])
        self.assertEqual(info['reference_action_mask'], info['action_mask'])
        env.step(own_rudder)
        self.assertEqual(control_budget(env.view())['shared_bonus'], 0)
        self.assertTrue(env.info()['reference_action_mask'][action('place', die=3, slot=2)])
        self.assertFalse(env.info()['action_mask'][action('place', die=3, slot=19)])


if __name__ == '__main__':
    unittest.main()
