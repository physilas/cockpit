"""Information boundaries, differential rule checks, complete games and PPO."""
from copy import deepcopy
import importlib.util
import io
import json
import math
import random
import tempfile
from pathlib import Path
import unittest

from ai.actions import ACTIONS, ACTION_IDS, Action, SLOTS, execute_placement
from ai.agents import HeuristicAgent, RandomAgent
from ai.environment import CrewEnv
from ai.observation import OBSERVATION_SIZE, encode
from ai.public_rules import legal_placement_in_view


def action_id(kind, **kwargs):
    return ACTION_IDS[Action(kind, **kwargs)]


def place_id(die, target, role=None, index=None):
    slot = next(i for i, s in enumerate(SLOTS) if s.target == target and s.owner == role and s.index == index)
    return action_id("place", die=die, slot=slot)


class EnvironmentTests(unittest.TestCase):
    def test_hidden_partner_faces_do_not_change_view_features_or_mask(self):
        for role in ("pilot", "kopilot"):
            env = CrewEnv()
            env.reset(seed=17)
            env.game.am_zug = role
            before = (deepcopy(env.view()), env.observation(), env.action_mask())
            for die in env.game._wuerfel_liste(env.other_role(role)):
                die.augenzahl = 7 - die.augenzahl
            self.assertEqual(before, (env.view(), env.observation(), env.action_mask()))
            self.assertEqual(len(before[1]), OBSERVATION_SIZE)
            self.assertNotIn("partner_dice", before[0])

    def test_masks_match_actual_engine_results_including_losing_moves(self):
        env = CrewEnv()
        rng, agent = random.Random(8), RandomAgent(9)
        checks = 0
        for seed in range(8):
            env.reset(seed=seed)
            for _ in range(20):
                if env.done:
                    break
                if env.reroll:
                    env.step(agent.select(env.view(), env.action_mask()))
                    continue
                env.game.cockpit.kaffeetassen = rng.randrange(4)
                mask, view = env.action_mask(), env.view()
                for i, action in enumerate(ACTIONS):
                    if action.kind not in ("place", "coffee"):
                        continue
                    game = deepcopy(env.game)
                    if action.kind == "place":
                        result = execute_placement(game, env.current_role, action)
                        self.assertEqual(mask[i], legal_placement_in_view(view, action))
                    else:
                        result = game.trinke_kaffee(env.current_role, action.die, action.delta)
                        # Engine clips out-of-range coffee requests. The agent deliberately
                        # offers only non-clipping requests, as the existing UI does.
                        value = env.game._wuerfel_liste(env.current_role)[action.die].augenzahl
                        if not 1 <= value + action.delta <= 6:
                            continue
                    self.assertEqual(mask[i], result.erfolg, (seed, action))
                    checks += 1
                env.step(agent.select(env.view(), mask))
        self.assertGreater(checks, 2000)

    def test_stall_is_legal_and_terminates_with_negative_reward(self):
        env = CrewEnv()
        env.reset(seed=3)
        env.game.pilot_wuerfel[0].augenzahl = 1
        env.game.kopilot_wuerfel[0].augenzahl = 6
        env.step(place_id(0, "ruder", "pilot"))
        selected = place_id(0, "ruder", "kopilot")
        self.assertTrue(env.action_mask()[selected])
        _, reward, terminated, truncated, info = env.step(selected)
        self.assertTrue(terminated)
        self.assertFalse(truncated)
        self.assertEqual((reward, info["reason"]), (-1.0, "trudeln"))
        self.assertFalse(any(info["action_mask"]))

    def test_seed_isolation_and_invalid_actions_are_non_mutating(self):
        outer = random.getstate()
        first, second = CrewEnv(), CrewEnv()
        self.assertEqual(first.reset(seed=42), second.reset(seed=42))
        self.assertEqual(random.getstate(), outer)
        for selected in (action_id("reroll_start"), action_id("reroll_select", subset=5), action_id("reroll_select", subset=2)):
            self.assertEqual(first.step(selected), second.step(selected))
            self.assertEqual(first.game.zustand(), second.game.zustand())
        self.assertEqual(random.getstate(), outer)
        snapshot = deepcopy(first.game.zustand())
        for bad in (-1, len(ACTIONS), True, "0", action_id("reroll_select", subset=1)):
            with self.assertRaises(ValueError):
                first.step(bad)
            self.assertEqual(first.game.zustand(), snapshot)

    def test_reroll_preserves_placed_dice_turn_and_spends_once(self):
        env = CrewEnv()
        env.reset(seed=1)
        env.step(place_id(0, "ruder", "pilot"))
        placed = env.game.pilot_wuerfel[0].augenzahl
        env.step(action_id("reroll_start"))
        env.step(action_id("reroll_select", subset=1))  # copilot chooses die 0
        self.assertEqual(env.current_role, "pilot")
        self.assertFalse(env.action_mask()[action_id("reroll_select", subset=1)])
        self.assertTrue(env.action_mask()[action_id("reroll_select", subset=0)])
        before, features, mask = deepcopy(env.view()), env.observation(), env.action_mask()
        for die in env.game.kopilot_wuerfel:
            die.augenzahl = 7 - die.augenzahl
        self.assertEqual((before, features, mask), (env.view(), env.observation(), env.action_mask()))
        tokens = env.game.neuwurf_plaettchen
        env.step(action_id("reroll_select", subset=0))
        self.assertEqual(env.game.neuwurf_plaettchen, tokens - 1)
        self.assertEqual(env.game.am_zug, "kopilot")
        self.assertEqual(env.game.pilot_wuerfel[0].augenzahl, placed)
        self.assertTrue(env.game.pilot_wuerfel[0].platziert)

    def test_both_empty_reroll_cannot_create_a_free_loop(self):
        env = CrewEnv()
        env.reset(seed=2)
        env.step(action_id("reroll_start"))
        env.step(action_id("reroll_select", subset=0))
        self.assertFalse(env.action_mask()[action_id("reroll_select", subset=0)])
        self.assertTrue(env.action_mask()[action_id("reroll_select", subset=1)])

    def test_empty_first_selection_is_masked_when_partner_has_no_free_dice(self):
        env = CrewEnv("TEST")
        env.reset(seed=6)
        for role in ("pilot", "kopilot"):
            for die, value in zip(env.game._wuerfel_liste(role), (3, 3, 1, 3)):
                die.augenzahl = value
        for selected in (place_id(0, "ruder", "pilot"), place_id(0, "ruder", "kopilot"),
                         place_id(1, "triebwerk", "pilot"), place_id(1, "triebwerk", "kopilot"),
                         place_id(2, "fahrwerk", "pilot", 0), place_id(2, "landeklappe", "kopilot", 0),
                         place_id(3, "fahrwerk", "pilot", 1)):
            env.step(selected)
        env.step(action_id("reroll_start"))
        self.assertFalse(env.action_mask()[action_id("reroll_select", subset=0)])
        env.step(action_id("reroll_select", subset=8))
        self.assertTrue(env.action_mask()[action_id("reroll_select", subset=0)])
        env.step(action_id("reroll_select", subset=0))
        self.assertFalse(env.done)

    def test_truncation_is_distinct_from_a_loss(self):
        env = CrewEnv(max_steps=1)
        env.reset(seed=5)
        _, reward, terminated, truncated, info = env.step(place_id(0, "ruder", "pilot"))
        self.assertFalse(terminated)
        self.assertTrue(truncated)
        self.assertEqual((reward, info["status"], info["reason"]), (0, "truncated", "step_limit"))

    def test_unsupported_modules_fail_explicitly(self):
        with self.assertRaises(ValueError):
            CrewEnv("LOG_HND_RED").reset(seed=1)

    def test_complete_scripted_win_runs_through_adapter_and_rewards(self):
        env = CrewEnv("TEST")
        env.reset(seed=1)
        returns = 0.0
        while not env.done:
            round_ = env.game.aktuelle_runde
            gear_index = min(round_ - 1, 2)
            k0, v0, k1, v1 = (0, 1, 1, 2) if round_ != 2 else (2, 4, 3, 5)
            total = math.floor(env.game.cockpit.aerodynamik_blau) + 1
            p, k = (3, 3) if env.game.letzte_runde else (max(1, min(6, total - 1)), total - max(1, min(6, total - 1)))
            for role, values in (("pilot", [3, p, [1, 3, 5][gear_index], [2, 4, 6][gear_index]]),
                                 ("kopilot", [3, k, v0, v1])):
                for die, value in zip(env.game._wuerfel_liste(role), values):
                    die.augenzahl = value
            queues = {"pilot": [place_id(0, "ruder", "pilot"), place_id(1, "triebwerk", "pilot"),
                                 place_id(2, "fahrwerk", "pilot", gear_index), place_id(3, "bremse", "pilot", gear_index)],
                      "kopilot": [place_id(0, "ruder", "kopilot"), place_id(1, "triebwerk", "kopilot"),
                                   place_id(2, "landeklappe", "kopilot", k0), place_id(3, "landeklappe", "kopilot", k1)]}
            for _ in range(8):
                _, reward, _, _, info = env.step(queues[env.current_role].pop(0))
                returns += reward
        self.assertEqual(info["status"], "gewonnen")
        self.assertAlmostEqual(returns, 1 + 6 * env.round_reward)

    def test_public_replay_and_paired_role_evaluation(self):
        from ai.evaluate import evaluate
        replay = io.StringIO()
        result = evaluate(RandomAgent(20), games=3, partner=HeuristicAgent(), replay=replay)
        self.assertEqual(result["games"], 6)
        self.assertEqual({r["ai_role"] for r in result["episodes"]}, {"pilot", "kopilot"})
        for line in replay.getvalue().splitlines():
            public = json.loads(line)["public_state"]
            self.assertNotIn("own_dice", public)
            self.assertNotIn("partner_dice", public)


@unittest.skipUnless(importlib.util.find_spec("torch"), "Optionale KI-Pakete fehlen: pip install -r ai/requirements.txt")
class LearningTests(unittest.TestCase):
    def setUp(self):
        import torch
        torch.set_num_threads(1)
        torch.manual_seed(4)

    def test_masked_sampling_single_action_and_gradients(self):
        import torch
        from ai.nn_model import ActorCritic
        model = ActorCritic(hidden_size=32)
        x = torch.zeros((4, OBSERVATION_SIZE))
        mask = torch.zeros((4, len(ACTIONS)), dtype=torch.bool)
        mask[:, 7] = True
        distribution, _ = model.distribution(x, mask)
        self.assertTrue(torch.equal(distribution.probs[:, 7], torch.ones(4)))
        self.assertEqual(float(distribution.probs[:, 6].sum().detach()), 0.0)
        action, logp, value = model.act(x, mask)
        self.assertTrue(torch.equal(action, torch.full((4,), 7)))
        (value.square().mean() - logp.mean()).backward()
        self.assertTrue(all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None))
        with self.assertRaises(ValueError):
            model.distribution(x, torch.zeros_like(mask))

    def test_cooperative_gae_terminal_and_truncation_bootstrap(self):
        from ai.train import compute_gae
        self.assertEqual(compute_gae([0, 1], [0, 0], gamma=1, gae_lambda=1), ([1, 1], [1, 1]))
        advantages, returns = compute_gae([0], [0.2], bootstrap=2, gamma=0.5)
        self.assertAlmostEqual(advantages[0], 0.8)
        self.assertAlmostEqual(returns[0], 1.0)

    def test_real_rollout_update_and_checkpoint_roundtrip(self):
        import torch
        from ai.checkpoints import load_checkpoint, save_checkpoint
        from ai.nn_model import ActorCritic
        from ai.train import collect_rollout, ppo_update
        model = ActorCritic(hidden_size=32)
        before = {k: p.clone() for k, p in model.state_dict().items()}
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
        batch, records = collect_rollout(model, CrewEnv(), 64, seed=5, episodes_done=0, gamma=0.995, gae_lambda=0.95)
        stats = ppo_update(model, optimizer, batch, epochs=2, minibatch_size=32)
        self.assertTrue(records)
        self.assertTrue(all(math.isfinite(v) for v in stats.values()))
        for name in ("actor.weight", "critic.weight"):
            self.assertFalse(torch.equal(before[name], model.state_dict()[name]))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.pt"
            save_checkpoint(path, model, total_steps=len(batch["actions"]))
            loaded, payload = load_checkpoint(path)
            self.assertEqual(payload["total_steps"], len(batch["actions"]))
            x = batch["observations"][:2]
            self.assertTrue(torch.equal(model(x)[0], loaded(x)[0]))
            payload["schema"]["version"] += 1
            torch.save(payload, path)
            with self.assertRaises(ValueError):
                load_checkpoint(path)


if __name__ == "__main__":
    unittest.main()
