"""Experimental simulator-backed policy improvement for every module/card.

Paired full-game rollouts, common random numbers, terminal win objective and
conservative fallback. This is not full POMCP/SPARTA: the root belief is an IID
prior and the rollout continuation is a fixed, observation-limited blueprint.
No simulated player may select from its partner's private hand.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import time

from .agents import ModelAgent
from .belief_simulator import BeliefSimulator, fork_simulation, simulation_step
from .modules import MODULE_ACTIONS, MODULE_SLOTS, module_encode


class GuidedBlueprint:
    def __init__(self, model, profile=12):
        if profile not in (10, 11, 12):
            raise ValueError('Expected public profile 10, 11 or 12.')
        self.agent = ModelAgent(model)
        self.model, self.profile = model, profile

    def masks(self, view, raw):
        from .module_guidance import module_guidance
        allowed, reference = module_guidance(view, raw)
        modules = set(view['modules_state']['modules'])
        if self.profile in (11, 12) and 'leak' in modules and not modules & {'wind', 'ice', 'intern'}:
            if self.profile == 12:
                from .leak_card_advice import leak_card_reference
                reference = leak_card_reference(view, allowed)
            else:
                from .leak_advice import leak_reference
                reference = leak_reference(view, allowed)
        # Historical planners were written for the full engine mask. A new
        # shield can remove their entire preferred continuation. Keep the
        # shield's legal alternatives instead of creating an empty NN prior.
        if not any(allowed):
            allowed = list(raw)
        reference = [bool(a and r) for a, r in zip(allowed, reference)]
        if not any(reference):
            reference = list(allowed)
        return allowed, reference

    def select(self, view, raw):
        allowed, reference = self.masks(view, raw)
        return self.agent.select(view, allowed, reference_mask=reference)

    def rank(self, view, raw):
        import torch
        allowed, reference = self.masks(view, raw)
        device = next(self.model.parameters()).device
        with torch.no_grad():
            observation = torch.tensor(module_encode(view), dtype=torch.float32, device=device)
            logits, _ = self.model.policy_output(observation, reference_mask=reference)
            values = logits.detach().cpu().tolist()
        baseline = max((i for i, ok in enumerate(allowed) if ok), key=lambda i: (values[i], -i))
        return baseline, sorted((i for i, ok in enumerate(raw) if ok), key=lambda i: (-values[i], i))


def semantic_action(view, index):
    action = MODULE_ACTIONS[index]
    if action.kind in ('place', 'coffee', 'adaptation', 'anticipation', 'swap_choose'):
        face = view['own_dice'][action.die]
        return action.kind, action.slot, action.delta, face
    return action.kind, action.slot, action.delta, action.subset


def candidates(view, ranked, baseline, width):
    """Deduplicate equal dice and retain action/target diversity in a small beam."""
    representatives, seen = [], set()
    for index in [baseline, *ranked]:
        key = semantic_action(view, index)
        if key not in seen:
            representatives.append(index)
            seen.add(key)
    diverse, groups = [baseline], set()
    for index in representatives:
        action = MODULE_ACTIONS[index]
        group = (action.kind, MODULE_SLOTS[action.slot].target if action.slot >= 0 else None)
        if group not in groups:
            if index != baseline:
                diverse.append(index)
            groups.add(group)
    return list(dict.fromkeys([*diverse, *representatives]))[:width]


@dataclass(frozen=True)
class SearchConfig:
    samples: int = 8
    candidates: int = 6
    max_seconds: float = 2.
    minimum_samples: int = 4
    minimum_gain: float = .1
    horizon: str = 'game'
    shield: bool = True

    def __post_init__(self):
        if (type(self.samples) is not int or self.samples < 1 or type(self.candidates) is not int
                or self.candidates < 1 or type(self.minimum_samples) is not int
                or not 1 <= self.minimum_samples <= self.samples
                or not math.isfinite(self.max_seconds) or self.max_seconds <= 0
                or not math.isfinite(self.minimum_gain) or not 0 <= self.minimum_gain <= 1
                or self.horizon not in ('game', 'round') or type(self.shield) is not bool):
            raise ValueError('Invalid bounded rollout search configuration.')


class RolloutSearchAgent:
    def __init__(self, airport, blueprint, *, config=None):
        self.airport = airport
        self.config = config or SearchConfig()
        if self.config.shield:
            from .safety_guard import ShieldedBlueprint
            blueprint = ShieldedBlueprint(airport, blueprint)
        self.blueprint = blueprint
        self.last_report = {}

    def _rollout(self, env, action, deadline):
        current_round = env.game.aktuelle_runde
        simulation_step(env, action)
        while not env.done:
            if self.config.horizon == 'round' and env.game.aktuelle_runde != current_round:
                return round_value(env.view())
            if time.monotonic() >= deadline:
                return None
            # Each actor receives a freshly filtered view. The simulated engine
            # and its RNG are never passed to the policy.
            view, raw = env.view(), env.action_mask()
            action = self.blueprint.select(view, raw)
            simulation_step(env, action)
        return float(env.game.status == 'gewonnen') if self.config.horizon == 'game' else (1. if env.game.status == 'gewonnen' else -1.)

    def select(self, view, mask):
        started = time.monotonic()
        baseline, ranked = self.blueprint.rank(view, mask)
        config = self.config
        proposals = candidates(view, ranked, baseline, config.candidates)
        seconds = config.max_seconds
        if 'realtime' in view['modules_state']['modules']:
            # Leave time for the remaining team placements, bonus actions and UI.
            seconds = min(seconds, max(.01, (view['modules_state']['time_remaining'] - 3) / 24))
        deadline = started + seconds
        simulator = BeliefSimulator(self.airport, view)
        # Public input determinism, independent of actual game/global RNG.
        seed = int.from_bytes(hashlib.sha256(json.dumps(view, sort_keys=True).encode()).digest()[:8], 'big')
        scores = {index: [] for index in proposals}
        for sample in range(config.samples):
            if time.monotonic() >= deadline:
                break
            root = simulator.sample(seed + sample)
            batch = {}
            for index in proposals:
                value = self._rollout(fork_simulation(root), index, deadline)
                if value is None:
                    break
                batch[index] = value
            # A deadline may never bias comparison toward the first candidates.
            if len(batch) != len(proposals):
                break
            for index, value in batch.items():
                scores[index].append(value)
        count = len(scores[baseline])
        chosen = baseline
        gains = {}
        if count >= config.minimum_samples:
            for index, values in scores.items():
                differences = [a - b for a, b in zip(values, scores[baseline])]
                gains[index] = sum(differences) / count
            best = max(proposals, key=lambda i: (gains[i], i == baseline, -i))
            if gains[best] >= config.minimum_gain and gains[best] > 0:
                chosen = best
        self.last_report = dict(baseline=baseline, chosen=chosen, samples=count, candidates=proposals,
                                estimated_values={str(i): sum(v)/len(v) if v else None for i, v in scores.items()},
                                paired_gains=gains, seconds=time.monotonic()-started,
                                belief='iid_remaining_partner_dice', objective='terminal_win' if config.horizon == 'game' else 'round_survival_and_public_potential',
                                approximate=True, confidence_guarantee=False)
        return chosen


def round_value(view):
    """Bounded heuristic leaf, never described as a win probability.

    Controls consume four regular dice per future round. Ice and normal brakes
    are alternative tasks, while all remaining traffic and intern tokens count.
    Unissued bonus dice are not credited to necessary capacity bounds.
    """
    state = view['modules_state']
    future = max(0, int(view['height'] // 1000))
    rounds = future + 1
    gear, flaps = view['gear'].count(False), view['flaps'].count(False)
    ice = 4 - state['ice_progress'] if 'ice' in state['modules'] else 0
    brakes = int(not any(view['brake_progress'])) if not ice and 'ice' not in state['modules'] else 0
    traffic = sum(cell['planes'] for cell in view['track'])
    intern = len(state['intern'])
    pilot_tasks, copilot_tasks = gear + brakes + ice, flaps
    shared_tasks = traffic + ice
    slack_p, slack_c = 2 * rounds - pilot_tasks, 2 * rounds - copilot_tasks
    deficit = max(0, -slack_p) + max(0, -slack_c)
    deficit += max(0, shared_tasks - max(0, slack_p) - max(0, slack_c))
    impossible_distance = max(0, view['distance'] - 2 * future)
    fuel_deficit = max(0, rounds + 1 - view['fuel']['remaining']) if set(state['modules']) & {'kerosene', 'leak'} else 0
    work = gear + flaps + brakes + 2 * ice + traffic + intern
    potential = .55 - .018 * work + .012 * view['coffee'] + .018 * view['reroll_tokens']
    potential -= .15 * deficit + .2 * impossible_distance + .15 * fuel_deficit
    potential -= .025 * abs(view['attitude'])
    return max(-.8, min(.8, potential))
