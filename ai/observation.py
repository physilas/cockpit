"""Explicit information boundary: no partner hand, RNG state, or hidden labels."""
from .actions import ROLES, SLOTS, slot_field


MAX_TRACK_LENGTH = 32


def visible_state(game, role, reroll=None, steps_remaining=1.0):
    if role not in ROLES:
        raise ValueError("Unbekannte Rolle.")
    partner = ROLES[1 - ROLES.index(role)]
    c, landing = game.cockpit, game.landung
    return {
        "role": role,
        "regular_turn": game.am_zug,
        "round_starter": game.startspieler,
        "round": game.aktuelle_runde,
        "height": landing.hoehe,
        "distance": landing.entfernung,
        "last_round": game.letzte_runde,
        "holding": game.warteschleife,
        "attitude": c.fluglage,
        "aero_blue": c.aerodynamik_blau,
        "aero_orange": c.aerodynamik_orange,
        "brakes": c.bremsstaerke(),
        "coffee": c.kaffeetassen,
        "reroll_tokens": game.neuwurf_plaettchen,
        "reroll_heights": landing.get_neuwurf_hoehen(),
        "gear": list(c.fahrwerk_ausgefahren),
        "flaps": list(c.landeklappen_ausgefahren),
        "brake_progress": list(c.bremsen_aktiviert),
        "own_dice": [w.augenzahl if w.ist_verfuegbar() else 0 for w in game._wuerfel_liste(role)],
        "partner_remaining": len(game.verfuegbare_wuerfel(partner)),
        "board": [None if slot_field(game, s).ist_frei() else {
            "value": slot_field(game, s).wuerfel.augenzahl,
            "owner": slot_field(game, s).wuerfel.besitzer,
        } for s in SLOTS],
        "track": [{"distance": d, "planes": p, "traffic": t, "min": low, "max": high}
                  for d, p, t, low, high in zip(landing.get_entfernungswerte(), landing.flugzeuge,
                      landing.get_flugzeugwuerfel(), landing.get_kurven_min(), landing.get_kurven_max())],
        # Only public selections/readiness, never the other role's die faces.
        "reroll": None if reroll is None else {
            "initiator": reroll["initiator"],
            "selections": {r: None if reroll["selections"][r] is None else list(reroll["selections"][r]) for r in ROLES},
        },
        "steps_remaining": steps_remaining,
    }


def _features(state):
    """Yield named features in one canonical order, shared with checkpoints."""
    for name in ("role", "regular_turn", "round_starter"):
        for role in ROLES:
            yield f"{name}.{role}", float(state[name] == role)
    for name, scale in (("round", 8), ("height", 6000), ("distance", MAX_TRACK_LENGTH),
                        ("attitude", 3), ("aero_blue", 12), ("aero_orange", 12),
                        ("brakes", 6), ("coffee", 3), ("reroll_tokens", 3), ("partner_remaining", 4)):
        yield name, state[name] / scale
    for name in ("last_round", "holding", "steps_remaining"):
        yield name, float(state[name])
    for i, height in enumerate(range(0, 7000, 1000)):
        yield f"reroll_height.{i}", float(height in state["reroll_heights"])
    for name in ("gear", "flaps", "brake_progress"):
        for i, value in enumerate(state[name]):
            yield f"{name}.{i}", float(value)
    for i, die in enumerate(state["own_dice"]):
        for face in range(7):  # 0 explicitly means unavailable, 1..6 are faces.
            yield f"die.{i}.{face}", float(die == face)
    for i, field in enumerate(state["board"]):
        yield f"field.{i}.occupied", float(field is not None)
        yield f"field.{i}.value", field["value"] / 6 if field else 0.0
        for role in ROLES:
            yield f"field.{i}.{role}", float(field is not None and field["owner"] == role)
    for i in range(MAX_TRACK_LENGTH):
        cell = state["track"][i] if i < len(state["track"]) else None
        yield f"track.{i}.present", float(cell is not None)
        for name, scale in (("distance", MAX_TRACK_LENGTH), ("planes", 12), ("traffic", 6), ("min", 3), ("max", 3)):
            yield f"track.{i}.{name}", cell[name] / scale if cell else 0.0
    pending = state["reroll"]
    yield "reroll.active", float(pending is not None)
    for role in ROLES:
        selected = pending["selections"][role] if pending else None
        yield f"reroll.{role}.initiator", float(pending is not None and pending["initiator"] == role)
        yield f"reroll.{role}.confirmed", float(selected is not None)
        for i in range(4):
            yield f"reroll.{role}.selected.{i}", float(selected is not None and i in selected)


def encode(state):
    return [value for _, value in _features(state)]


def feature_names():
    # Obtain structure without constructing a game or consuming randomness.
    empty = {"role": "pilot", "regular_turn": "pilot", "round_starter": "pilot",
             "gear": [False] * 3, "flaps": [False] * 4, "brake_progress": [False] * 3,
             "own_dice": [0] * 4, "board": [None] * len(SLOTS), "track": [],
             "reroll": None, "reroll_heights": []}
    for key in ("round", "height", "distance", "attitude", "aero_blue", "aero_orange", "brakes",
                "coffee", "reroll_tokens", "partner_remaining", "last_round", "holding", "steps_remaining"):
        empty[key] = 0
    return [name for name, _ in _features(empty)]


OBSERVATION_SIZE = len(feature_names())
