from copy import deepcopy
import random
import unittest

from ai.belief_simulator import BeliefSimulator, fork_simulation, simulation_step
from ai.module_training_eval import _official_cases
from ai.modules import ModuleEnv, MODULE_ACTIONS
from ai.rollout_search import RolloutSearchAgent, SearchConfig, candidates


class FirstLegal:
    def select(self, view, mask):
        return next(i for i, ok in enumerate(mask) if ok)

    def rank(self, view, mask):
        legal = [i for i, ok in enumerate(mask) if ok]
        return legal[0], legal


class BeliefSearchTests(unittest.TestCase):
    def test_public_reconstruction_all_186_official_cases(self):
        for (airport, cards) in _official_cases():
            with self.subTest(airport=airport, cards=cards):
                env = ModuleEnv(airport, abilities=cards, assistance_version=0)
                env.reset(seed=14000100)
                view = env.view()
                sim = BeliefSimulator(airport, view).sample(1)
                expected = deepcopy(view)
                if 'realtime' in view['modules_state']['modules']:
                    expected['modules_state']['time_remaining'] -= 1
                self.assertEqual(expected, sim.view())
                self.assertEqual(env.action_mask(), sim.action_mask())

    def test_reconstruction_during_real_actions_and_bonus_phases(self):
        rng = random.Random(88)
        for airport, cards in list(_official_cases())[::13]:
            env = ModuleEnv(airport, abilities=cards, assistance_version=0)
            env.reset(seed=14000100)
            for step in range(40):
                if env.done:
                    break
                view = env.view()
                sim = BeliefSimulator(airport, view).sample(step)
                expected = deepcopy(view)
                if 'realtime' in view['modules_state']['modules']:
                    expected['modules_state']['time_remaining'] = max(0, expected['modules_state']['time_remaining'] - 1)
                self.assertEqual(expected, sim.view(), (airport, step))
                self.assertEqual(env.action_mask(), sim.action_mask(), (airport, step))
                legal = [i for i, ok in enumerate(env.action_mask()) if ok]
                env.step(rng.choice(legal))

    def test_hidden_hand_and_engine_rng_cannot_affect_samples(self):
        env = ModuleEnv('MUC', assistance_version=0)
        env.reset(seed=14000101)
        before = env.view()
        a = BeliefSimulator('MUC', before).sample(99)
        for die in env.game.kopilot_wuerfel:
            die.augenzahl = 6
        env.rng.seed(551)
        self.assertEqual(before, env.view())
        b = BeliefSimulator('MUC', env.view()).sample(99)
        self.assertEqual(a.view('kopilot'), b.view('kopilot'))

    def test_forks_preserve_aliases_and_do_not_mutate_root_or_global_rng(self):
        env = ModuleEnv('MUC')
        env.reset(seed=14000101)
        view = env.view()
        root = BeliefSimulator('MUC', view).sample(4)
        branch = fork_simulation(root)
        state = random.getstate()
        action = FirstLegal().select(branch.view(), branch.action_mask())
        simulation_step(branch, action)
        self.assertEqual(state, random.getstate())
        self.assertEqual(view, root.view())
        self.assertIs(branch.game.cockpit.landung, branch.game.landung)
        self.assertIs(branch.game.zusatz.spiel, branch.game)
        self.assertIs(branch.clock, branch.game.zusatz.clock)

    def test_search_falls_back_when_no_complete_paired_batch(self):
        env = ModuleEnv('MUC')
        env.reset(seed=14000102)
        agent = RolloutSearchAgent('MUC', FirstLegal(), config=SearchConfig(
            samples=1, candidates=2, minimum_samples=1, max_seconds=.000001))
        expected, _ = FirstLegal().rank(env.view(), env.action_mask())
        self.assertEqual(expected, agent.select(env.view(), env.action_mask()))
        self.assertEqual(0, agent.last_report['samples'])

    def test_candidates_preserve_baseline_and_merge_equivalent_dice(self):
        env = ModuleEnv('MUC')
        env.reset(seed=14000102)
        view = env.view()
        view['own_dice'] = [2, 2, 2, 2]
        ranked = [i for i, action in enumerate(MODULE_ACTIONS) if action.kind == 'place' and action.slot == 0]
        self.assertEqual([ranked[0]], candidates(view, ranked, ranked[0], 6))

    def test_geometry_mismatch_fails(self):
        env = ModuleEnv('MUC')
        env.reset(seed=14000102)
        view = env.view()
        view['track'][0]['traffic'] += 1
        with self.assertRaises(ValueError):
            BeliefSimulator('MUC', view).sample(1)
