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
from contextlib import redirect_stdout
from unittest.mock import patch

from ai.actions import ACTIONS, ACTION_IDS, ACTION_MASK_VERSION, Action, SLOTS, execute_placement
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
                        required = [view["board"][j] for j, slot in enumerate(SLOTS)
                                    if slot.owner == view["role"] and slot.target in ("ruder", "triebwerk")]
                        has_spare = sum(bool(v) for v in view["own_dice"]) > required.count(None)
                        expected = result.erfolg and (has_spare or SLOTS[action.slot].target in ("ruder", "triebwerk"))
                    else:
                        result = game.trinke_kaffee(env.current_role, action.die, action.delta)
                        # Engine clips out-of-range coffee requests. The agent deliberately
                        # offers only non-clipping requests, as the existing UI does.
                        value = env.game._wuerfel_liste(env.current_role)[action.die].augenzahl
                        if not 1 <= value + action.delta <= 6:
                            continue
                        expected = result.erfolg
                    self.assertEqual(mask[i], expected, (seed, action))
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


class MandatoryFieldTests(unittest.TestCase):
    def two_optional_placements_per_role(self):
        env = CrewEnv()
        env.reset(seed=7)
        for role, values in (("pilot", (1, 3, 2, 2)), ("kopilot", (1, 1, 2, 2))):
            for die, value in zip(env.game._wuerfel_liste(role), values):
                die.augenzahl = value
        for selected in (place_id(0, "funk", "pilot"), place_id(0, "landeklappe", "kopilot", 0),
                         place_id(1, "fahrwerk", "pilot", 1), place_id(1, "funk", "kopilot")):
            env.step(selected)
        return env

    def test_two_free_dice_are_reserved_for_both_missing_fields_in_each_role(self):
        env = self.two_optional_placements_per_role()
        for role, target, index in (("pilot", "fahrwerk", 0), ("kopilot", "landeklappe", 1)):
            env.game.am_zug = role
            mask = env.action_mask()
            placements = [ACTIONS[i] for i, legal in enumerate(mask) if legal and ACTIONS[i].kind == "place"]
            self.assertEqual({SLOTS[a.slot].target for a in placements}, {"ruder", "triebwerk"})
            self.assertEqual({a.die for a in placements}, {2, 3})
            self.assertTrue(all(SLOTS[a.slot].owner == role for a in placements))
            optional = place_id(2, target, role, index)
            self.assertTrue(execute_placement(deepcopy(env.game), role, ACTIONS[optional]).erfolg)
            self.assertFalse(mask[optional])
            before = deepcopy(env.game.zustand())
            with self.assertRaises(ValueError):
                env.step(optional)
            self.assertEqual(env.game.zustand(), before)

    def test_one_open_field_reserves_only_the_last_die_regardless_of_which_field(self):
        for first, last in (("ruder", "triebwerk"), ("triebwerk", "ruder")):
            env = CrewEnv()
            env.reset(seed=7)
            for role in ("pilot", "kopilot"):
                for die, value in zip(env.game._wuerfel_liste(role), (3, 1, 1, 3)):
                    die.augenzahl = value
            for selected in (place_id(0, first, "pilot"), place_id(0, first, "kopilot"),
                             place_id(1, "funk", "pilot"), place_id(1, "funk", "kopilot")):
                env.step(selected)
            self.assertTrue(env.action_mask()[place_id(2, "fahrwerk", "pilot", 0)])
            env.step(place_id(2, "fahrwerk", "pilot", 0))
            # The partner still has two dice and can use its spare one.
            self.assertTrue(env.action_mask()[place_id(2, "landeklappe", "kopilot", 0)])
            env.step(place_id(2, "landeklappe", "kopilot", 0))
            for role in ("pilot", "kopilot"):
                env.game.am_zug = role
                allowed = [ACTIONS[i] for i, valid in enumerate(env.action_mask())
                           if valid and ACTIONS[i].kind == "place"]
                self.assertEqual(len(allowed), 1)
                self.assertEqual((allowed[0].die, SLOTS[allowed[0].slot].target), (3, last))

    def test_filled_mandatory_fields_leave_spare_dice_unrestricted(self):
        env = CrewEnv()
        env.reset(seed=7)
        for role in ("pilot", "kopilot"):
            for die in env.game._wuerfel_liste(role):
                die.augenzahl = 1
        for selected in (place_id(0, "ruder", "pilot"), place_id(0, "ruder", "kopilot"),
                         place_id(1, "triebwerk", "pilot"), place_id(1, "triebwerk", "kopilot")):
            env.step(selected)
        for role, target in (("pilot", "fahrwerk"), ("kopilot", "landeklappe")):
            env.game.am_zug = role
            self.assertTrue(env.action_mask()[place_id(2, target, role, 0)])

    def test_coffee_and_joint_reroll_preserve_the_reservation(self):
        env = self.two_optional_placements_per_role()
        env.game.cockpit.kaffeetassen = 1
        env.step(action_id("coffee", die=2, delta=1))
        env.step(action_id("reroll_start"))
        env.step(action_id("reroll_select", subset=4))
        env.step(action_id("reroll_select", subset=4))
        self.assertEqual(env.current_role, "pilot")
        for role in ("pilot", "kopilot"):
            env.game.am_zug = role
            allowed = [ACTIONS[i] for i, valid in enumerate(env.action_mask()) if valid and ACTIONS[i].kind == "place"]
            self.assertEqual({SLOTS[a.slot].target for a in allowed}, {"ruder", "triebwerk"})
            self.assertEqual(len(env.game.verfuegbare_wuerfel(role)), 2)

    def test_reserved_mask_does_not_depend_on_hidden_partner_faces(self):
        env = self.two_optional_placements_per_role()
        for role in ("pilot", "kopilot"):
            env.game.am_zug = role
            before = (env.view(), env.observation(), env.action_mask())
            for die in env.game.verfuegbare_wuerfel(env.other_role(role)):
                die.augenzahl = 7 - die.augenzahl
            self.assertEqual(before, (env.view(), env.observation(), env.action_mask()))

    def test_complete_masked_games_cannot_run_out_of_mandatory_dice(self):
        resolved = 0
        for seed in range(100):
            env = CrewEnv()
            env.reset(seed=seed)
            agent = RandomAgent(seed + 20) if seed < 80 else HeuristicAgent()
            while not env.done:
                for role, fields in (("pilot", (env.game.cockpit.ruder_pilot, env.game.cockpit.schub_pilot)),
                                     ("kopilot", (env.game.cockpit.ruder_kopilot, env.game.cockpit.schub_kopilot))):
                    self.assertGreaterEqual(len(env.game.verfuegbare_wuerfel(role)), sum(f.ist_frei() for f in fields))
                env.step(agent.select(env.view(), env.action_mask()))
            self.assertNotEqual(env.info()["reason"], "pflichtfelder_nicht_erfuellt")
            resolved += env.rounds_resolved
        self.assertGreater(resolved, 20)


def scripted_round(env, engine_value=1):
    """Resolve a real base-game round without traffic or upgrades."""
    for role in ("pilot", "kopilot"):
        for die, value in zip(env.game._wuerfel_liste(role), (1, engine_value, 1, 1)):
            die.augenzahl = value
    queues = {
        "pilot": [place_id(0, "ruder", "pilot"), place_id(1, "triebwerk", "pilot"),
                  place_id(2, "funk", "pilot"), place_id(3, "konzentration", index=0)],
        "kopilot": [place_id(0, "ruder", "kopilot"), place_id(1, "triebwerk", "kopilot"),
                    place_id(2, "konzentration", index=1), place_id(3, "konzentration", index=2)]}
    return [env.step(queues[env.current_role].pop(0)) for _ in range(8)]


class SynchronizationTests(unittest.TestCase):
    def test_backlog_penalty_once_at_round_end_with_separate_components(self):
        env = CrewEnv("TEST", round_reward=0.02, sync_weight=0.05)
        env.reset(seed=1)
        env.game.landung.hoehe = 1000
        results = scripted_round(env)
        for _, reward, _, _, info in results[:-1]:
            self.assertEqual(reward, 0)
            self.assertEqual(info["reward_components"]["sync"], 0)
        _, reward, terminated, truncated, info = results[-1]
        self.assertTrue(terminated)
        self.assertFalse(truncated)
        self.assertEqual(info["reason"], "notlandung")
        self.assertEqual(info["reward_components"], {"outcome": -1, "round": 0.02, "sync": -0.05, "tasks": 0})
        self.assertAlmostEqual(reward, -1.03)
        record = env.episode_record(1, "both", sum(r[1] for r in results))
        self.assertEqual((record["round"], record["landing_round_started"], record["distance_remaining"]), (2, 0, 2))
        self.assertAlmostEqual(record["return"], record["outcome_return"] + record["round_return"] + record["sync_return"])

    def test_one_field_tolerance_and_progress_vs_stalling(self):
        stalled = CrewEnv("TEST", round_reward=0, sync_weight=0.05, sync_tolerance=0)
        moving = CrewEnv("TEST", round_reward=0, sync_weight=0.05, sync_tolerance=0)
        for env in (stalled, moving):
            env.reset(seed=1)
            env.game.landung.hoehe = 2000
        stall_reward = scripted_round(stalled)[-1][1]
        move_reward = scripted_round(moving, engine_value=3)[-1][1]
        self.assertAlmostEqual(stall_reward, -0.05)
        self.assertEqual(move_reward, 0)
        self.assertEqual((stalled.game.landung.entfernung, moving.game.landung.entfernung), (2, 1))
        stalled.sync_tolerance = 1
        self.assertEqual(stalled.sync_error(), 0)

    def test_early_arrival_and_holding_do_not_receive_penalty(self):
        env = CrewEnv("TEST", round_reward=0, sync_weight=0.5, sync_tolerance=0)
        env.reset(seed=2)
        env.game.landung.entfernung = 0
        env.game.landung.hoehe = 3000
        env.game.warteschleife = True
        result = scripted_round(env)[-1]
        self.assertEqual(result[1], 0)
        self.assertEqual(result[-1]["reward_totals"]["sync"], 0)
        self.assertEqual(env.game.landung.hoehe, 2000)
        self.assertFalse(env.done)

    def test_coffee_and_rerolls_do_not_charge_backlog_again(self):
        env = CrewEnv(sync_weight=0.05, sync_tolerance=0)
        env.reset(seed=42)
        env.game.landung.hoehe = 1000
        env.game.cockpit.kaffeetassen = 1
        delta = -1 if env.game.pilot_wuerfel[0].augenzahl > 1 else 1
        choices = [action_id("coffee", die=0, delta=delta), action_id("reroll_start"),
                   action_id("reroll_select", subset=1), action_id("reroll_select", subset=0)]
        for selected in choices:
            _, reward, _, _, info = env.step(selected)
            self.assertEqual(reward, 0)
            self.assertEqual(info["reward_totals"]["sync"], 0)
        self.assertEqual(env.sync_error(), 5)

    def test_zero_weight_disables_shaping_and_invalid_parameters_fail(self):
        env = CrewEnv("TEST", round_reward=0, sync_weight=0, sync_tolerance=0)
        env.reset(seed=1)
        env.game.landung.hoehe = 1000
        result = scripted_round(env)[-1]
        self.assertEqual(result[1], -1)
        self.assertEqual(result[-1]["reward_components"]["sync"], 0)
        for bad in (-0.1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                CrewEnv(sync_weight=bad)
            with self.assertRaises(ValueError):
                CrewEnv(sync_tolerance=bad)


class TaskPenaltyTests(unittest.TestCase):
    def test_task_count_tracks_required_preparation_not_optional_brake_upgrades(self):
        env = CrewEnv(task_weight=0.02)
        env.reset(seed=1)
        self.assertEqual(env.unfinished_tasks(), {"gear": 3, "flaps": 4, "braking": 1, "traffic": 9})
        c = env.game.cockpit
        c.fahrwerk_ausgefahren[0] = True
        c.landeklappen_ausgefahren[:2] = [True, True]
        c.bremsen_aktiviert[0] = True
        env.game.landung.flugzeuge[0] -= 1
        self.assertEqual(env.unfinished_tasks(), {"gear": 2, "flaps": 2, "braking": 0, "traffic": 8})
        before = env.unfinished_tasks()
        c.bremsen_aktiviert[:] = [True, True, True]
        self.assertEqual(env.unfinished_tasks(), before)

    def test_round_penalty_grows_quadratically_and_scales_with_undone_tasks(self):
        env = CrewEnv("TEST", round_reward=0, task_weight=0.02)
        env.reset(seed=1)
        charges = []
        for round_ in range(1, 6):
            results = scripted_round(env)
            self.assertTrue(all(r[-1]["reward_components"]["tasks"] == 0 for r in results[:-1]))
            charge = results[-1][-1]["reward_components"]["tasks"]
            self.assertAlmostEqual(charge, -0.02 * 8 * (round_ ** 2 - (round_ - 1) ** 2) / 49)
            charges.append(charge)
        self.assertTrue(all(abs(a) < abs(b) for a, b in zip(charges, charges[1:])))
        fewer = CrewEnv("TEST", round_reward=0, task_weight=0.02)
        fewer.reset(seed=1)
        fewer.game.cockpit.fahrwerk_ausgefahren[0] = True
        fewer.game.cockpit.aerodynamik_blau += 1
        charge = scripted_round(fewer)[-1][-1]["reward_components"]["tasks"]
        self.assertAlmostEqual(charge, charges[0] * 7 / 8)

    def test_early_failure_settles_same_remaining_budget_as_late_failure(self):
        early = CrewEnv("TEST", round_reward=0, task_weight=0.02)
        early.reset(seed=1)
        early.game.pilot_wuerfel[0].augenzahl = 1
        early.game.kopilot_wuerfel[0].augenzahl = 6
        early.step(place_id(0, "ruder", "pilot"))
        result = early.step(place_id(0, "ruder", "kopilot"))
        self.assertTrue(result[2])
        self.assertAlmostEqual(result[-1]["reward_totals"]["tasks"], -0.16)
        late = CrewEnv("TEST", round_reward=0, task_weight=0.02)
        late.reset(seed=1)
        while not late.done:
            scripted_round(late)
        self.assertEqual(late.info()["reason"], "notlandung")
        self.assertAlmostEqual(late.reward_totals["tasks"], early.reward_totals["tasks"])
        self.assertEqual(late.task_urgency, 1)

    def test_coffee_rerolls_and_truncation_do_not_repeat_or_settle_task_cost(self):
        env = CrewEnv("TEST", round_reward=0, task_weight=0.02)
        env.reset(seed=1)
        scripted_round(env)
        cost = env.reward_totals["tasks"]
        die = env.game._wuerfel_liste(env.current_role)[0]
        delta = -1 if die.augenzahl > 1 else 1
        for choice in [action_id("coffee", die=0, delta=delta), action_id("reroll_start"),
                       action_id("reroll_select", subset=1), action_id("reroll_select", subset=0)]:
            result = env.step(choice)
            self.assertEqual(result[-1]["reward_components"]["tasks"], 0)
            self.assertEqual(env.reward_totals["tasks"], cost)
        truncated = CrewEnv("TEST", max_steps=1, task_weight=0.02)
        truncated.reset(seed=1)
        _, reward, terminated, limited, info = truncated.step(place_id(0, "ruder", "pilot"))
        self.assertFalse(terminated)
        self.assertTrue(limited)
        self.assertEqual((reward, info["reward_totals"]["tasks"], truncated.task_urgency), (0, 0, 0))

    def test_completed_preparation_has_zero_task_penalty_and_allows_a_win(self):
        env = CrewEnv("TEST", round_reward=0, task_weight=0.02)
        env.reset(seed=1)
        env.game.landung.entfernung = env.game.landung.hoehe = 0
        env.game.letzte_runde = True
        c = env.game.cockpit
        c.fahrwerk_ausgefahren[:] = [True] * 3
        c.landeklappen_ausgefahren[:] = [True] * 4
        c.bremsen_aktiviert[0] = True
        c.aerodynamik_blau += 3
        c.aerodynamik_orange += 4
        result = scripted_round(env)[-1]
        self.assertEqual(result[-1]["status"], "gewonnen")
        self.assertEqual(result[1], 1)
        record = env.episode_record(1, "both", 1)
        self.assertEqual((record["tasks_undone"], record["tasks_return"]), (0, 0))

    def test_task_weight_zero_and_invalid_values(self):
        env = CrewEnv("TEST", round_reward=0, task_weight=0)
        env.reset(seed=1)
        while not env.done:
            scripted_round(env)
        self.assertEqual(env.reward_totals["tasks"], 0)
        for bad in (-1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                CrewEnv(task_weight=bad)


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

    def test_uniform_mixture_has_legal_floor_and_consistent_log_probabilities(self):
        import torch
        from ai.nn_model import ActorCritic
        model = ActorCritic(observation_size=3, action_count=5, hidden_size=8)
        with torch.no_grad():
            model.actor.bias.copy_(torch.tensor([12., -12., 3., 0., 100.]))
        x = torch.zeros((3, 3))
        mask = torch.tensor([[True, True, False, False, False],
                             [False, True, True, True, False],
                             [False, True, False, False, False]])
        base, _ = model.distribution(x, mask)
        mixed, _ = model.distribution(x, mask, uniform_mix=0.03)
        uniform = mask.float() / mask.sum(-1, keepdim=True)
        torch.testing.assert_close(mixed.probs, 0.97 * base.probs + 0.03 * uniform)
        self.assertTrue(torch.equal(mixed.probs[~mask], torch.zeros_like(mixed.probs[~mask])))
        self.assertTrue(bool((mixed.probs[mask] >= (0.03 * uniform)[mask] - 1e-7).all()))
        pure_uniform, _ = model.distribution(x, mask, uniform_mix=1)
        torch.testing.assert_close(pure_uniform.probs, uniform)
        unchanged, _ = model.distribution(x, mask, uniform_mix=0)
        self.assertTrue(torch.equal(unchanged.probs, base.probs))
        actions, sampled_logp, _ = model.act(x, mask, uniform_mix=0.03)
        logp, entropy, value = model.evaluate_actions(x, mask, actions, uniform_mix=0.03)
        torch.testing.assert_close(logp, sampled_logp)
        self.assertTrue(bool(mask.gather(1, actions[:, None]).all()))
        (value.square().mean() - logp.mean() - 0.01 * entropy.mean()).backward()
        self.assertTrue(all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None))
        self.assertEqual(model.actor.bias.grad[-1].item(), 0)
        for bad in (-0.01, 1.01, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                model.distribution(x, mask, uniform_mix=bad)

    def test_uniform_exploration_resume_defaults_and_explicit_zero(self):
        from ai.train import resolve_uniform_mix
        self.assertEqual(resolve_uniform_mix(None), 0.03)
        self.assertEqual(resolve_uniform_mix(None, {}), 0)
        self.assertEqual(resolve_uniform_mix(None, {"uniform_mix": 0.1}), 0.1)
        self.assertEqual(resolve_uniform_mix(0, {"uniform_mix": 0.1}), 0)
        self.assertEqual(resolve_uniform_mix(0.03, {}), 0.03)

    def test_model_agent_greedy_evaluation_omits_uniform_exploration(self):
        import torch
        from ai.agents import ModelAgent
        from ai.nn_model import ActorCritic
        env = CrewEnv()
        _, info = env.reset(seed=5)
        mask = info["action_mask"]
        best = max(i for i, legal in enumerate(mask) if legal)
        model = ActorCritic(hidden_size=32)
        with torch.no_grad():
            model.actor.weight.zero_()
            model.actor.bias.zero_()
            model.actor.bias[best] = 10
        self.assertEqual(ModelAgent(model, uniform_mix=1).select(env.view(), mask), best)
        stochastic = ModelAgent(model, deterministic=False, uniform_mix=1)
        draws = [stochastic.select(env.view(), mask) for _ in range(32)]
        self.assertTrue(all(mask[action] for action in draws))
        self.assertGreater(len(set(draws)), 1)

    def test_real_rollout_update_and_checkpoint_roundtrip(self):
        import torch
        from ai.checkpoints import load_checkpoint, save_checkpoint
        from ai.nn_model import ActorCritic
        from ai.train import collect_rollout, ppo_update
        model = ActorCritic(hidden_size=32)
        before = {k: p.clone() for k, p in model.state_dict().items()}
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
        batch, records = collect_rollout(model, CrewEnv(task_weight=0.02), 64, seed=5, episodes_done=0,
                                         gamma=0.995, gae_lambda=0.95, uniform_mix=0.03)
        with torch.no_grad():
            recomputed, _, _ = model.evaluate_actions(batch["observations"], batch["masks"], batch["actions"], uniform_mix=0.03)
        torch.testing.assert_close(recomputed, batch["log_probs"])
        stats = ppo_update(model, optimizer, batch, epochs=2, minibatch_size=32, uniform_mix=0.03)
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

    def test_resume_reward_overrides_preserve_unspecified_legacy_values(self):
        from ai.train import parser, reward_config
        old = {"round_reward": 0.02}
        self.assertEqual(reward_config(parser().parse_args([]), old),
                         {"round_reward": 0.02, "sync_weight": 0, "sync_tolerance": 1, "task_weight": 0})
        args = parser().parse_args(["--round-reward", "0", "--sync-weight", "0.05"])
        self.assertEqual(reward_config(args, old), {"round_reward": 0, "sync_weight": 0.05, "sync_tolerance": 1, "task_weight": 0})
        self.assertEqual(reward_config(parser().parse_args([])),
                         {"round_reward": 0, "sync_weight": 0.05, "sync_tolerance": 1, "task_weight": 0.02})
        options = parser().parse_args(["--task-weight", "0.03"])
        saved = reward_config(options, old)
        self.assertEqual(saved["task_weight"], 0.03)
        self.assertEqual(reward_config(parser().parse_args([]), saved), saved)
        self.assertEqual(reward_config(parser().parse_args(["--task-weight", "0"]), saved)["task_weight"], 0)

    def test_csv_upgrade_preserves_old_data_and_leaves_new_values_unknown(self):
        import csv
        from ai.train import append_rows
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metrics.csv"
            append_rows(path, ["update", "total_steps"], [{"update": 1, "total_steps": 12}])
            append_rows(path, ["update", "total_steps", "train_mean_sync_return"],
                        [{"update": 2, "total_steps": 24, "train_mean_sync_return": -0.1}])
            with path.open() as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0], {"update": "1", "total_steps": "12", "train_mean_sync_return": ""})
            self.assertEqual(rows[1]["train_mean_sync_return"], "-0.1")

    def test_checkpoint_selection_prefers_actual_progress_over_round_counter(self):
        from ai.train import validation_score
        stalled = {"win_rate": 0, "landing_round_rate": 0, "airport_reached_rate": 0,
                   "mean_distance_remaining": 6, "mean_round": 7}
        progressing = {**stalled, "mean_distance_remaining": 1, "mean_round": 5}
        self.assertGreater(validation_score(progressing), validation_score(stalled))
        landed = {**stalled, "landing_round_rate": 1, "airport_reached_rate": 1, "mean_distance_remaining": 0}
        self.assertGreater(validation_score(landed), validation_score(progressing))

    def test_legacy_checkpoint_can_continue_with_changed_rewards_and_disable_them(self):
        import csv
        import torch
        from ai.checkpoints import save_checkpoint, load_checkpoint
        from ai.nn_model import ActorCritic
        from ai.train import main
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original, shaped, disabled = root / "old", root / "sync", root / "off"
            path = original / "latest.pt"
            model = ActorCritic(hidden_size=32)
            optimizer = torch.optim.Adam(model.parameters(), lr=3e-4)
            config = {"airport": "TEST", "round_reward": 0.02, "max_steps": 256,
                      "gamma": 0.995, "gae_lambda": 0.95, "seed": 42, "hidden_size": 32}
            save_checkpoint(path, model, optimizer_state=optimizer.state_dict(), train_config=config,
                            total_steps=0, episodes=0, update=0, best_score=[-1, -1], torch_rng_state=torch.get_rng_state())
            original_bytes = path.read_bytes()
            common = ["ai.train", "--rollout-steps", "64", "--epochs", "1", "--minibatch-size", "32", "--eval-games", "2"]
            # An unchanged legacy reward/exploration setup still needs a fresh
            # log directory when the mandatory-field mask is introduced.
            with patch("sys.argv", common + ["--resume", str(path), "--steps", "64", "--run-dir", str(original)]), \
                    redirect_stdout(io.StringIO()), patch("sys.stderr", io.StringIO()) as errors:
                with self.assertRaises(SystemExit):
                    main()
                self.assertIn("Aktionsmasken", errors.getvalue())
            self.assertEqual(path.read_bytes(), original_bytes)
            mask_only = root / "mandatory"
            with patch("sys.argv", common + ["--resume", str(path), "--steps", "64", "--run-dir", str(mask_only)]), redirect_stdout(io.StringIO()):
                main()
            _, reserved = load_checkpoint(mask_only / "latest.pt")
            self.assertEqual(reserved["train_config"]["action_mask_version"], ACTION_MASK_VERSION)
            self.assertTrue(reserved["train_config"]["mask_changed_on_resume"])
            self.assertFalse(reserved["train_config"]["reward_changed_on_resume"])
            self.assertFalse(reserved["train_config"]["exploration_changed_on_resume"])
            self.assertEqual(reserved["model_config"], model.config)
            with patch("sys.argv", common + ["--resume", str(path), "--steps", "64", "--run-dir", str(shaped),
                                              "--round-reward", "0", "--sync-weight", "0.05", "--task-weight", "0.02",
                                              "--uniform-mix", "0.03"]), redirect_stdout(io.StringIO()):
                main()
            _, saved = load_checkpoint(shaped / "latest.pt")
            self.assertEqual(saved["train_config"]["round_reward"], 0)
            self.assertEqual(saved["train_config"]["sync_weight"], 0.05)
            self.assertEqual(saved["train_config"]["task_weight"], 0.02)
            self.assertEqual(saved["train_config"]["uniform_mix"], 0.03)
            self.assertEqual(saved["model_config"], model.config)
            self.assertTrue(saved["train_config"]["reward_changed_on_resume"])
            self.assertTrue(saved["train_config"]["exploration_changed_on_resume"])
            self.assertTrue(saved["train_config"]["mask_changed_on_resume"])
            self.assertEqual(path.read_bytes(), original_bytes)
            with (shaped / "metrics.csv").open() as handle:
                metrics = list(csv.DictReader(handle))
            self.assertNotEqual(metrics[-1]["eval_mean_sync_return"], "")
            self.assertNotEqual(metrics[-1]["eval_mean_tasks_return"], "")
            self.assertEqual(float(metrics[-1]["uniform_mix"]), 0.03)
            with patch("sys.argv", common + ["--resume", str(path), "--steps", "64", "--run-dir", str(original),
                                              "--round-reward", "0"]), redirect_stdout(io.StringIO()), patch("sys.stderr", io.StringIO()):
                with self.assertRaises(SystemExit):
                    main()
            self.assertEqual(path.read_bytes(), original_bytes)
            with patch("sys.argv", common + ["--resume", str(path), "--steps", "64", "--run-dir", str(original),
                                              "--uniform-mix", "0.03"]), redirect_stdout(io.StringIO()), patch("sys.stderr", io.StringIO()):
                with self.assertRaises(SystemExit):
                    main()
            self.assertEqual(path.read_bytes(), original_bytes)
            with patch("sys.argv", common + ["--resume", str(shaped / "latest.pt"), "--steps", str(saved["total_steps"] + 32),
                                              "--run-dir", str(disabled), "--sync-weight", "0", "--task-weight", "0",
                                              "--uniform-mix", "0"]), redirect_stdout(io.StringIO()):
                main()
            _, off = load_checkpoint(disabled / "latest.pt")
            self.assertEqual(off["train_config"]["sync_weight"], 0)
            self.assertEqual(off["train_config"]["round_reward"], 0)
            self.assertEqual(off["train_config"]["task_weight"], 0)
            self.assertEqual(off["train_config"]["uniform_mix"], 0)
            self.assertFalse(off["train_config"]["mask_changed_on_resume"])


if __name__ == "__main__":
    unittest.main()
