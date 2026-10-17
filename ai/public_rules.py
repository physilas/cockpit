"""Placement checks on public observations, for the simple heuristic only.

The environment mask remains authoritative. This helper cannot access a game.
"""
from .actions import SLOTS


def legal_placement_in_view(view, action):
    slot = SLOTS[action.slot]
    value = view["own_dice"][action.die]
    if not value or (slot.owner is not None and slot.owner != view["role"]) or view["board"][action.slot]:
        return False
    if slot.target == "fahrwerk":
        return value in ((1, 2), (3, 4), (5, 6))[slot.index]
    if slot.target in ("landeklappe", "bremse"):
        progress = view["flaps"] if slot.target == "landeklappe" else view["brake_progress"]
        first = next((i for i, done in enumerate(progress) if not done), len(progress))
        if not progress[slot.index] and slot.index != first:
            return False
        return value in ((1, 2), (2, 3), (4, 5), (5, 6))[slot.index] if slot.target == "landeklappe" else value == (2, 4, 6)[slot.index]
    return True
