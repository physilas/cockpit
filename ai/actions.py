"""Stable base-game action IDs and engine placement constraints."""
from dataclasses import asdict, dataclass


ROLES = ("pilot", "kopilot")
SCHEMA_VERSION = 1
# Mask changes do not change model features/action IDs or invalidate weights.
# v2 reserves each role's remaining dice for its unfilled mandatory fields.
ACTION_MASK_VERSION = 2


@dataclass(frozen=True)
class Slot:
    target: str
    owner: str | None = None
    index: int | None = None
    radio_index: int = 0

    @property
    def label(self):
        name = {"ruder": "Ruder", "triebwerk": "Triebwerk", "funk": "Funk",
                "fahrwerk": "Fahrwerk", "landeklappe": "Landeklappe",
                "bremse": "Bremse", "konzentration": "Konzentration"}[self.target]
        number = self.radio_index if self.target == "funk" else self.index
        suffix = f" {number + 1}" if number is not None else ""
        return f"{name}{suffix}" + (f" ({self.owner})" if self.owner else "")


SLOTS = tuple(
    [Slot(target, role) for target in ("ruder", "triebwerk") for role in ROLES]
    + [Slot("funk", "pilot"), Slot("funk", "kopilot"), Slot("funk", "kopilot", radio_index=1)]
    + [Slot("fahrwerk", "pilot", i) for i in range(3)]
    + [Slot("landeklappe", "kopilot", i) for i in range(4)]
    + [Slot("bremse", "pilot", i) for i in range(3)]
    + [Slot("konzentration", index=i) for i in range(3)]
)


@dataclass(frozen=True)
class Action:
    kind: str
    die: int = -1
    slot: int = -1
    delta: int = 0
    subset: int = 0

    def to_dict(self):
        return asdict(self)

    def label(self):
        if self.kind == "place":
            return f"Würfel {self.die + 1} → {SLOTS[self.slot].label}"
        if self.kind == "coffee":
            return f"Kaffee: Würfel {self.die + 1} um {self.delta:+d} ändern"
        if self.kind == "reroll_start":
            return "Gemeinsamen Neuwurf starten"
        selected = subset_indices(self.subset)
        return "Neuwurf bestätigen: " + (", ".join(str(i + 1) for i in selected) or "keinen eigenen Würfel")


ACTIONS = tuple(
    [Action("place", die=i, slot=j) for i in range(4) for j in range(len(SLOTS))]
    + [Action("coffee", die=i, delta=d) for i in range(4) for d in (-3, -2, -1, 1, 2, 3)]
    + [Action("reroll_start")]
    + [Action("reroll_select", subset=s) for s in range(16)]
)
ACTION_COUNT = len(ACTIONS)
ACTION_IDS = {action: i for i, action in enumerate(ACTIONS)}


def subset_indices(bits):
    return [i for i in range(4) if bits & (1 << i)]


def slot_field(game, slot):
    c = game.cockpit
    if slot.target == "ruder":
        return c.ruder_pilot if slot.owner == "pilot" else c.ruder_kopilot
    if slot.target == "triebwerk":
        return c.schub_pilot if slot.owner == "pilot" else c.schub_kopilot
    if slot.target == "funk":
        return c.funk_pilot if slot.owner == "pilot" else c.funk_kopilot[slot.radio_index]
    return getattr(c, {"landeklappe": "landeklappen", "bremse": "bremsen"}.get(slot.target, slot.target))[slot.index]


def placement_is_legal(game, role, die, slot):
    """Use the engine's field constraints; mirror only its two ordering checks.

    Intentionally do NOT predict stalls, collisions, or future mandatory fields.
    The environment separately reserves dice for mandatory fields in its mask.
    Exhaustive differential tests compare this predicate to engine execution.
    """
    if slot.owner is not None and slot.owner != role:
        return False
    if not die.ist_verfuegbar():
        return False
    field = slot_field(game, slot)
    if not field.ist_frei() or not field.erlaubt(role, die.augenzahl):
        return False
    if slot.target in ("landeklappe", "bremse"):
        progress = getattr(game.cockpit, "landeklappen_ausgefahren" if slot.target == "landeklappe" else "bremsen_aktiviert")
        first = next((i for i, done in enumerate(progress) if not done), len(progress))
        if not progress[slot.index] and slot.index != first:
            return False
    return True


def execute_placement(game, role, action):
    slot = SLOTS[action.slot]
    if slot.owner is not None and slot.owner != role:
        from backend.cockpit import Ergebnis
        return Ergebnis(False, "feld_ungueltig")
    return game.platziere(role, action.die, slot.target, index=slot.index, funk_feld=slot.radio_index)
