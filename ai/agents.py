"""All agents receive only a permitted view and its action mask."""
import random

from .actions import ACTIONS, SLOTS, ROLES, subset_indices
from .observation import encode


class RandomAgent:
    def __init__(self, seed=0):
        self.rng = random.Random(seed)

    def select(self, view, mask):
        return self.rng.choice([i for i, valid in enumerate(mask) if valid])


class ModelAgent:
    def __init__(self, model, deterministic=True, uniform_mix=0.0):
        self.model = model
        self.deterministic = deterministic
        if not 0 <= uniform_mix <= 1:
            raise ValueError("uniform_mix must be between 0 and 1.")
        self.uniform_mix = uniform_mix

    def select(self, view, mask):
        import torch
        device = next(self.model.parameters()).device
        with torch.no_grad():
            if self.model.config["observation_size"] != len(encode(view)):
                if self.model.config["observation_size"] == 352:
                    from .fuel import fuel_encode
                    observation = fuel_encode(view)
                else:
                    from .modules import module_encode
                    observation = module_encode(view)
            else:
                observation = encode(view)
            action, _, _ = self.model.act(torch.tensor(observation, dtype=torch.float32, device=device),
                                           mask, deterministic=self.deterministic,
                                           uniform_mix=0.0 if self.deterministic else self.uniform_mix)
        return int(action.item())


def _slot_index(target, role):
    return next(i for i, slot in enumerate(SLOTS) if slot.target == target and slot.owner == role)


class HeuristicAgent:
    """A deliberately small baseline, not an optimal solver or privileged teacher."""
    def _placement_score(self, view, action, value=None):
        if action.slot == len(SLOTS) and view.get('fuel', {}).get('present'):
            face = view['own_dice'][action.die] if value is None else value
            return 40 - 9 * face - (1000 if face >= view['fuel']['remaining'] else 0)
        slot = SLOTS[action.slot]
        value = view["own_dice"][action.die] if value is None else value
        role = view["role"]
        partner = ROLES[1 - ROLES.index(role)]
        missing = sum(view["board"][_slot_index(t, role)] is None for t in ("ruder", "triebwerk"))
        remaining = sum(bool(v) for v in view["own_dice"])
        required = slot.target in ("ruder", "triebwerk")
        score = -100.0 if remaining <= missing and not required else 0.0
        if slot.target == "ruder":
            other = view["board"][_slot_index("ruder", partner)]
            if other:
                attitude = view["attitude"] + (other["value"] - value if role == "pilot" else value - other["value"])
                score += 25 - 5 * abs(attitude) if abs(attitude) < 3 else -150
            else:
                score += 8 - abs(value - 3.5)
        elif slot.target == "triebwerk":
            other = view["board"][_slot_index("triebwerk", partner)]
            if other:
                speed = other["value"] + value
                if view["last_round"]:
                    score += 25 if speed <= view["brakes"] else -90 - speed
                elif view["holding"]:
                    score += 15
                else:
                    movement = int(speed >= view["aero_blue"]) + int(speed >= view["aero_orange"])
                    desired = min(2, max(0, round(view["distance"] / max(1, view["height"] / 1000))))
                    score += 15 - 7 * abs(movement - desired)
                    if movement > view["distance"]:
                        score -= 100
            else:
                score += 5 - abs(value - (2 if view["last_round"] else 3.5))
        elif slot.target in ("fahrwerk", "landeklappe", "bremse"):
            progress = view[{"fahrwerk": "gear", "landeklappe": "flaps", "bremse": "brake_progress"}[slot.target]]
            score += -8 if progress[slot.index] else (10 if slot.target == "bremse" else 17)
        elif slot.target == "funk":
            distance = view["distance"] - value + 1
            planes = next((p["planes"] for p in view["track"] if p["distance"] == distance), 0)
            score += (35 if distance == view["distance"] else 20) if planes else -5
        else:
            score += 4 if view["coffee"] < 3 else -10
        return score

    def select(self, view, mask):
        actions = ACTIONS
        if view.get('fuel', {}).get('present'):
            from .fuel import FUEL_ACTIONS
            actions = FUEL_ACTIONS
        legal = [i for i, valid in enumerate(mask) if valid]
        placements = [i for i in legal if actions[i].kind == "place"]
        best_now = max((self._placement_score(view, actions[i]) for i in placements), default=-200)
        scores = {}
        for i in legal:
            action = actions[i]
            if action.kind == "place":
                scores[i] = self._placement_score(view, action)
            elif action.kind == "coffee":
                # Reuse the placement legality rules on a hypothetical, permitted own die.
                from copy import deepcopy
                changed = deepcopy(view)
                changed["own_dice"][action.die] += action.delta
                changed["coffee"] -= abs(action.delta)
                from .public_rules import legal_placement_in_view
                candidates = [a for a in ACTIONS if a.kind == "place" and a.die == action.die
                              and legal_placement_in_view(changed, a)]
                improved = max((self._placement_score(changed, a) for a in candidates), default=-200)
                scores[i] = improved - 0.5 * abs(action.delta) if improved > best_now + 1 else -200
            elif action.kind == "reroll_start":
                scores[i] = 0 if best_now < -20 else -200
            else:
                # Keep dice that can currently do useful work, reroll the rest.
                from .public_rules import legal_placement_in_view
                wanted = [j for j, value in enumerate(view["own_dice"]) if value and not any(
                    self._placement_score(view, a) >= 10 for a in ACTIONS
                    if a.kind == "place" and a.die == j and legal_placement_in_view(view, a))]
                selected = subset_indices(action.subset)
                scores[i] = -len(set(selected) ^ set(wanted))
        return max(legal, key=lambda i: scores[i])
