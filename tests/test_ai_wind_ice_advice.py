"""New public micro-plans versus actual engine outcomes, without win claims."""
from copy import deepcopy
import random
import unittest
from unittest.mock import patch

from ai.actions import Action
from ai.modules import MODULE_ACTIONS, MODULE_SLOTS, ModuleEnv
from ai.wind_ice_advice import (_after_placement, _completion_options, _legal,
    wind_ice_plans, wind_ice_reference)
from ai.wind_ice_environment import WindIceEnv
from tests.test_ai_wind_ice_counterexamples import (
    _action, _place, ice_final_pair_fixture, wind_public_thrust_fixture)


def paired(source):
    source.assistance_version = 12
    research = WindIceEnv(source.airport, abilities=list(source.abilities))
    # Scripted technical fixture copy only. The planner gets only view/mask.
    research.__dict__.update(deepcopy(source.__dict__))
    research._source_reference_mask = None
    return source, research


class WindIceAdviceTests(unittest.TestCase):
    def test_final_ice_pair_is_uniquely_advised_and_actually_wins(self):
        source, research = paired(ice_final_pair_fixture())
        native, study = source.info(), research.info()
        good = _action(3, 'eisbremse', index=7)
        self.assertEqual([i for i, yes in enumerate(study['reference_action_mask']) if yes], [good])
        self.assertEqual(study['action_mask'], native['action_mask'])
        self.assertEqual(study['source_reference_action_mask'], native['reference_action_mask'])
        _place(research.game, 'kopilot', 3, 'eisbremse', 7)
        self.assertTrue(research.game.rundenende().gewonnen)

    def test_public_tailwind_ranks_safe_thrust_above_overshoot(self):
        source, research = paired(wind_public_thrust_fixture())
        info = research.info()
        safe, overshoot = _action(2, 'triebwerk', owner='pilot'), _action(1, 'triebwerk', owner='pilot')
        plans = wind_ice_plans(research.view(), info['action_mask'])
        self.assertGreater(plans[safe], plans[overshoot] + 1000)
        self.assertFalse(info['reference_action_mask'][overshoot])
        self.assertTrue(any(info['reference_action_mask']))
        self.assertEqual(source.info()['action_mask'], info['action_mask'])

    def test_adaptation_is_a_real_first_step_not_an_extra_die_or_stale_face(self):
        source, research = paired(ice_final_pair_fixture())
        for env in (source, research):
            env.game.kopilot_wuerfel[3].augenzahl = 2
            env.game.cockpit.kaffeetassen = 0
        flip = MODULE_ACTIONS.index(Action('adaptation', die=3))
        info = research.info()
        self.assertEqual([i for i, yes in enumerate(info['reference_action_mask']) if yes], [flip])
        result = research.game.zusatz.aktion('kopilot', 'adaptation', {'wuerfel_index': 3})
        self.assertTrue(result.erfolg)
        self.assertEqual(research.view()['own_dice'], [0, 0, 0, 5])
        good = _action(3, 'eisbremse', index=7)
        self.assertTrue(research.info()['reference_action_mask'][good])
        _place(research.game, 'kopilot', 3, 'eisbremse', 7)
        self.assertTrue(research.game.rundenende().gewonnen)

    def test_virtual_new_face_rules_match_engine_for_all_fields_and_faces(self):
        checked = 0
        for fixture in (wind_public_thrust_fixture, ice_final_pair_fixture):
            for face in range(1, 7):
                env = fixture()
                index = next(i for i, value in enumerate(env.view()['own_dice']) if value)
                env.game._wuerfel_liste(env.current_role)[index].augenzahl = face
                view, mask = env.view(), env.action_mask()
                missing = sum(view['board'][i] is None for i in ((0, 2) if view['role'] == 'pilot' else (1, 3)))
                for slot_index, slot in enumerate(MODULE_SLOTS):
                    actual = mask[MODULE_ACTIONS.index(Action('place', die=index, slot=slot_index))]
                    # The planning reservation is intentionally conservative;
                    # the ordinary engine may still permit a doomed optional.
                    reserved = sum(bool(value) for value in view['own_dice']) <= missing and slot.target not in ('ruder', 'triebwerk')
                    self.assertEqual(_legal(view, index, slot_index, face), actual and not reserved)
                    checked += 1
        self.assertEqual(checked, 372)

    def test_public_upgrade_ice_and_coffee_effects_match_actual_placements(self):
        for fixture, die, target, slot_index, index in (
                (ice_final_pair_fixture, 3, 'eisbremse', 30, 7),
                (wind_public_thrust_fixture, 1, 'fahrwerk', 9, 2),
                (wind_public_thrust_fixture, 2, 'konzentration', 17, 0)):
            env = fixture()
            # Concentration0 is occupied in this wind fixture; choose a free
            # concentration field without changing the scripted hand.
            if target == 'konzentration': slot_index, index = 18, 1
            view = env.view()
            after, _ = _after_placement(view, die, slot_index, view['own_dice'][die], view['coffee'])
            _place(env.game, view['role'], die, target, index)
            actual = env.view(view['role'])
            for key in ('own_dice', 'gear', 'flaps', 'brake_progress', 'aero_blue', 'aero_orange', 'brakes', 'coffee', 'track'):
                self.assertEqual(after[key], actual[key], (fixture.__name__, target, key))
            for key in ('ice_progress', 'extra_fields'):
                self.assertEqual(after['modules_state'][key], actual['modules_state'][key])

    def test_joint_own_assignment_never_reuses_a_die_or_shared_coffee(self):
        self.assertEqual(_completion_options((2,), ('ruder', 'triebwerk'), 3), ())
        options = dict(_completion_options((2, 2), ('ruder', 'triebwerk'), 1))
        self.assertNotIn((1, 1), options)
        self.assertEqual(options[(1, 2)], 1)
        self.assertEqual(options[(2, 2)], 0)
        self.assertNotIn((4, 2), options)

    def test_unused_partner_faces_rng_inputs_and_pacing_preserve_advice(self):
        _, env = paired(wind_public_thrust_fixture())
        view, info, rng = env.view(), env.info(), random.getstate()
        snapshot = deepcopy(view)
        reference = info['reference_action_mask']
        env.game.kopilot_wuerfel[2].augenzahl = 6
        env.game.kopilot_wuerfel[3].augenzahl = 5
        self.assertEqual(env.view(), view)
        self.assertEqual(env.info()['reference_action_mask'], reference)
        with patch('ai.wind_ice_advice.CpuBudget.pause') as pause:
            self.assertEqual(wind_ice_reference(view, info['action_mask'], info['source_reference_action_mask'], cpu_duty_cycle=.7), reference)
            self.assertTrue(pause.called)
        self.assertEqual(view, snapshot)
        self.assertEqual(random.getstate(), rng)

    def test_native_mask_schema_clock_rng_and_other_modules_are_unchanged(self):
        for airport, cards in (('LOG_ATL_YELLOW', ['adaptation']), ('LOG_ATL_GREEN', []), ('MUC', [])):
            source = ModuleEnv(airport, abilities=cards, assistance_version=12)
            research = WindIceEnv(airport, abilities=cards)
            seed = 'train:wind-ice-fallback:' + airport
            source.reset(seed=seed); research.reset(seed=seed)
            self.assertIsNone(source.clock)
            self.assertIsNone(research.clock)
            self.assertEqual(research.view(), source.view())
            self.assertEqual(research.observation(), source.observation())
            self.assertEqual(research.info()['action_mask'], source.info()['action_mask'])
            self.assertEqual(research.info()['reference_action_mask'], source.info()['reference_action_mask'])
            self.assertEqual(research.rng.getstate(), source.rng.getstate())
        for profile in (0, 10, 11, 13, True):
            with self.assertRaises(ValueError): WindIceEnv(assistance_version=profile)


if __name__ == '__main__':
    unittest.main()
