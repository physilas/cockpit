"""Donation research changes soft advice, preserving native profile12 behavior."""
from copy import deepcopy
import json
from pathlib import Path
import random
import unittest

import torch

from ai.actions import Action
from ai.agents import ModelAgent
from ai.checkpoints import load_checkpoint, weight_fingerprint
from ai.intern_strength_compare import tensor_fingerprint, with_margin
from ai.leak_donation_environment import DonationEnv
from ai.modules import CARDS, MODULE_ACTIONS, MODULE_SLOTS, ModuleEnv, module_schema
from tests.test_ai_leak_donation_advice import donation_env


def _action(kind, *, die=-1, slot=-1):
    return MODULE_ACTIONS.index(Action(kind, die=die, slot=slot))


def paired_donation_fixture():
    source = donation_env()
    source.assistance_version = 12
    research = DonationEnv(source.airport, abilities=list(source.abilities))
    # Copy fixture state, not a live game's hidden hand into a planner. The
    # helper/model below still receives only the permitted public own-role view.
    research.__dict__.update(deepcopy(source.__dict__))
    research._source_reference_mask = None
    return source, research


class LeakDonationEnvironmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def assert_source_contract(self, source, research, *, same_reference=False):
        native, study = source.info(), research.info()
        self.assertEqual(study['action_mask'], native['action_mask'])
        self.assertEqual(study['source_reference_action_mask'], native['reference_action_mask'])
        self.assertTrue(study['research_leak_donation'])
        self.assertTrue(all(not advice or study['action_mask'][index]
                            for index, advice in enumerate(study['reference_action_mask'])))
        self.assertEqual(research.view(), source.view())
        self.assertEqual(research.observation(), source.observation())
        self.assertEqual(research.rng.getstate(), source.rng.getstate())
        ordinary = {key: value for key, value in study.items()
                    if key not in ('research_leak_donation', 'source_reference_action_mask',
                                   'reference_action_mask')}
        expected = {key: value for key, value in native.items() if key != 'reference_action_mask'}
        self.assertEqual(ordinary, expected)
        if same_reference:
            self.assertEqual(study['reference_action_mask'], native['reference_action_mask'])
        return native, study

    def test_schema_allowed_actions_and_saved_source_reference_are_native_profile12(self):
        source, research = paired_donation_fixture()
        schema_before = deepcopy(module_schema())
        self.assertIs(research.actions, MODULE_ACTIONS)
        self.assertIs(research.slots, MODULE_SLOTS)
        # This copied technical fixture deliberately uses a fixed clock; the
        # research wrapper must preserve it. Native None clocks are covered
        # separately on the untouched reset paths below.
        self.assertIs(research.clock, source.clock)
        self.assertEqual(research.assistance_version, 12)
        native, study = self.assert_source_contract(source, research)
        start = _action('swap_start')
        self.assertTrue(native['action_mask'][start])
        self.assertEqual([index for index, flag in enumerate(study['reference_action_mask']) if flag], [start])
        self.assertNotEqual(study['reference_action_mask'], native['reference_action_mask'])
        self.assertEqual(module_schema(), schema_before)
        # Returned metadata masks are detached from both cached references.
        detached = list(study['source_reference_action_mask'])
        study['source_reference_action_mask'][start] = not detached[start]
        self.assertEqual(research.info()['source_reference_action_mask'], detached)

    def test_pending_swap_roles_keep_native_source_masks_and_reach_actual_safe_rudder(self):
        source, research = paired_donation_fixture()
        sequence = [
            _action('swap_start'), _action('swap_choose', die=3),
            _action('swap_choose', die=3),
            _action('place', die=2, slot=10), _action('place', die=3, slot=0),
        ]
        for index, action in enumerate(sequence):
            native, study = self.assert_source_contract(source, research)
            self.assertTrue(native['action_mask'][action])
            if index < 3:
                self.assertEqual([i for i, flag in enumerate(study['reference_action_mask']) if flag], [action])
            native_result, study_result = source.step(action), research.step(action)
            self.assertEqual(native_result[:4], study_result[:4])
        self.assert_source_contract(source, research, same_reference=True)
        self.assertIsNone(research.game.zusatz.kooperation)
        self.assertEqual(research.game.status, 'laeuft')
        self.assertEqual(research.game.cockpit.fluglage, 1)
        self.assertEqual(research.game.cockpit.kerosin, source.game.cockpit.kerosin)
        self.assertEqual(research.game.am_zug, source.game.am_zug)
        self.assertEqual(sum(bool(face) for face in research.view()['own_dice']), 1)

    def test_all_five_other_cards_and_native_wind_intern_paths_are_exact_fallbacks(self):
        cases = [('LOG_ATL_YELLOW', [card]) for card in sorted(set(CARDS) - {'working-together'})]
        cases += [('LOG_GIG_YELLOW', ['working-together']), ('LOG_ATL_GREEN', [])]
        # Identical explicitly scripted placements, including a native round
        # resolution when legal; the engine's seeded next rolls stay identical.
        sequence = [_action('place', die=0, slot=0), _action('place', die=0, slot=1),
                    _action('place', die=1, slot=2), _action('place', die=1, slot=3),
                    _action('place', die=2, slot=17), _action('place', die=2, slot=18),
                    _action('place', die=3, slot=19), _action('place', die=3, slot=5)]
        for airport, cards in cases:
            with self.subTest(airport=airport, cards=cards):
                options = dict(abilities=cards, assistance_version=12)
                source, research = ModuleEnv(airport, **options), DonationEnv(airport, **options)
                seed = 'train:donation-wrapper-fallback:251061:' + airport + ':' + ','.join(cards)
                source.reset(seed=seed); research.reset(seed=seed)
                for env in (source, research):
                    for role in ('pilot', 'kopilot'):
                        for die in env.game._wuerfel_liste(role):
                            die.augenzahl = 3
                self.assertIsNone(source.clock)
                self.assertIsNone(research.clock)
                for action in sequence:
                    native, _ = self.assert_source_contract(source, research, same_reference=True)
                    self.assertTrue(native['action_mask'][action])
                    native_result, study_result = source.step(action), research.step(action)
                    self.assertEqual(native_result[:4], study_result[:4])
                    if source.done:
                        break
                self.assert_source_contract(source, research, same_reference=True)

    def test_unassisted_and_terminal_roles_never_leak_stale_reference_masks(self):
        source, research = paired_donation_fixture()
        source.assisted_roles = research.assisted_roles = ('pilot',)
        native, study = self.assert_source_contract(source, research, same_reference=True)
        self.assertEqual(study['reference_action_mask'], native['action_mask'])
        self.assertEqual(study['source_reference_action_mask'], native['action_mask'])
        source.game.status = research.game.status = 'verloren'
        source.game.verlust_grund = research.game.verlust_grund = 'trudeln'
        native, study = self.assert_source_contract(source, research, same_reference=True)
        self.assertFalse(any(study['source_reference_action_mask']))
        self.assertEqual(study['source_reference_action_mask'], native['action_mask'])

    def test_advice_does_not_mutate_public_input_rng_or_depend_on_partner_faces(self):
        _, research = paired_donation_fixture()
        view = deepcopy(research.view())
        global_rng, engine_rng = random.getstate(), research.rng.getstate()
        baseline = research.info()
        for hidden in (6, 2):
            research.game.pilot_wuerfel[3].augenzahl = hidden
            self.assertEqual(research.view(), view)
            current = research.info()
            self.assertEqual(current['action_mask'], baseline['action_mask'])
            self.assertEqual(current['source_reference_action_mask'], baseline['source_reference_action_mask'])
            self.assertEqual(current['reference_action_mask'], baseline['reference_action_mask'])
            self.assertNotIn('partner_dice', research.view())
        self.assertEqual(random.getstate(), global_rng)
        self.assertEqual(research.rng.getstate(), engine_rng)

    def test_original_crew2_margin12_choices_are_measured_without_changing_weights(self):
        checkpoint = Path(__file__).resolve().parents[1] / 'ai/releases/crew2-v1/best.pt'
        if not checkpoint.exists():
            self.skipTest('The original Crew-2 release is not available in this checkout.')
        original_bytes = checkpoint.read_bytes()
        original, _ = load_checkpoint(checkpoint)
        original_sha = weight_fingerprint(original)
        model = with_margin(original, 12.)
        model_sha, tensor_sha = weight_fingerprint(model), tensor_fingerprint(model)
        self.assertEqual(tensor_sha, tensor_fingerprint(original))
        source, research = paired_donation_fixture()
        native, study = self.assert_source_contract(source, research)
        rng_before, torch_before = random.getstate(), torch.get_rng_state().clone()
        agent = ModelAgent(model)
        native_action = agent.select(source.view(), native['action_mask'], reference_mask=native['reference_action_mask'])
        donation_action = agent.select(research.view(), study['action_mask'], reference_mask=study['reference_action_mask'])
        self.assertTrue(native['action_mask'][native_action])
        self.assertTrue(study['action_mask'][donation_action])
        # This measurement intentionally makes no assertion that a finite
        # soft prior overrides the inherited detail logits on this fixture.
        print(json.dumps({'technical_fixture': 'public_leak_donation', 'guide_margin': 12,
            'native_action': MODULE_ACTIONS[native_action].to_dict(),
            'donation_action': MODULE_ACTIONS[donation_action].to_dict(),
            'donation_choice_inside_reference': study['reference_action_mask'][donation_action],
            'tensor_values_changed': False}), flush=True)
        self.assertEqual(weight_fingerprint(original), original_sha)
        self.assertEqual(weight_fingerprint(model), model_sha)
        self.assertEqual(tensor_fingerprint(model), tensor_sha)
        self.assertEqual(checkpoint.read_bytes(), original_bytes)
        self.assertEqual(random.getstate(), rng_before)
        self.assertTrue(torch.equal(torch.get_rng_state(), torch_before))

    def test_other_profiles_require_a_separate_explicit_research_phase(self):
        for profile in (0, 10, 11, 13, True):
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                DonationEnv(assistance_version=profile)


if __name__ == '__main__':
    unittest.main()
