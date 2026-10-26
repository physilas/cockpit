"""Validate and freeze winning human demonstrations for an auxiliary actor loss.

These observation/action pairs are never on-policy PPO rollouts or critic targets.
Imports no torch until tensors are requested, so the importer can run independently.
"""
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path

from .actions import ACTIONS, ACTION_MASK_VERSION, ROLES, SCHEMA_VERSION, SLOTS
from .observation import feature_names


@dataclass
class Demonstrations:
    observations: list
    masks: list
    actions: list
    manifest: dict

    def tensors(self, device="cpu"):
        import torch
        return {"observations": torch.tensor(self.observations, dtype=torch.float32, device=device),
                "masks": torch.tensor(self.masks, dtype=torch.bool, device=device),
                "actions": torch.tensor(self.actions, dtype=torch.long, device=device)}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def load_demonstrations(paths, airport):
    """Latest revision per session; only consented, won KI-no games on this route.

    A later lost/aborted revision supersedes an earlier win. Conflicting snapshots
    with the same session/revision are rejected, while duplicate exports are harmless.
    Fingerprints describe the actual learning pairs, independent of file locations.
    """
    files = set()
    for source in paths:
        path = Path(source)
        if not path.exists():
            raise ValueError(f"Demonstrationsquelle fehlt: {path}")
        files.update(path.rglob("*.json") if path.is_dir() else [path])
    latest = {}
    for path in sorted(files):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("version") != 1:
            raise ValueError(f"Unbekannte Demonstrationsversion in {path}")
        if data.get("format") == "flyteam-learning-session":
            sessions = [data["session"]]
        elif data.get("format") == "flyteam-learning-data":
            sessions = data["sessions"]
        else:
            raise ValueError(f"Kein KI-Lernexport: {path}")
        for session in sessions:
            identity, revision = session.get("id"), session.get("data_revision")
            if not isinstance(identity, str) or not identity or type(revision) is not int or revision < 1:
                raise ValueError(f"Session-ID oder Revision fehlt in {path}")
            snapshot = {"session": session, "schema": data["schema"],
                        "action_mask_version": data.get("action_mask_version")}
            previous = latest.get(identity)
            if previous and revision == previous[0] and _canonical(snapshot) != _canonical(previous[1]):
                raise ValueError(f"Widersprüchliche Demonstration: {identity}, Revision {revision}")
            if previous is None or revision > previous[0]:
                latest[identity] = revision, snapshot, path

    expected_schema = {"version": SCHEMA_VERSION, "features": feature_names(),
                       "actions": [asdict(a) for a in ACTIONS], "slots": [asdict(s) for s in SLOTS]}
    observations, masks, actions, sources, roles = [], [], [], [], Counter()
    excluded = Counter(voided=0, non_decision=0, incompatible=0, non_human=0)
    fingerprint_pairs = []
    for identity, (revision, snapshot, path) in sorted(latest.items()):
        s = snapshot["session"]
        if (s.get("mode") != "examples" or s.get("status") != "gewonnen"
                or s.get("scenario", {}).get("engine_code") != airport or not s.get("consent")):
            continue
        consent = s["consent"]
        if not isinstance(consent, dict) or consent.get("version") != "2026-10-18":
            raise ValueError(f"Unbekannte Einwilligungsversion in {path}")
        accepted = datetime.fromisoformat(consent.get("accepted_at", "").replace("Z", "+00:00"))
        if accepted.tzinfo is None:
            raise ValueError(f"Einwilligungszeitpunkt ohne Zeitzone in {path}")
        if (snapshot["schema"] != expected_schema or s.get("schema_version") != SCHEMA_VERSION
                or snapshot["action_mask_version"] != ACTION_MASK_VERSION
                or s.get("action_mask_version") != ACTION_MASK_VERSION):
            raise ValueError(f"Demonstration und aktuelles Schema/Aktionsmaske passen nicht: {path}")
        live = [e for e in s["events"] if e.get("voided") is False and not e.get("withdrawn")]
        if not live or live[-1].get("outcome", {}).get("status") != "gewonnen":
            raise ValueError(f"Sieg nicht durch letztes gültiges Ereignis bestätigt: {path}")
        start = len(actions)
        for e in s["events"]:
            if e.get("withdrawn"):
                excluded["withdrawn"] += 1
                continue
            if e.get("voided") is True:
                excluded["voided"] += 1
                continue
            if e.get("voided") is not False:
                raise ValueError(f"Unklarer Rückgängig-Status in {path}")
            if e.get("action_id") is None:
                excluded["non_decision"] += 1
                continue
            if e.get("actor") != "human":
                excluded["non_human"] += 1
                continue
            if e.get("training_compatible") is not True:
                excluded["incompatible"] += 1
                continue
            a, decision = e["action_id"], e["decision"]
            observation, mask, role = decision["observation"], decision["action_mask"], decision["role"]
            if (type(a) is not int or not 0 <= a < len(ACTIONS) or role not in ROLES
                    or len(observation) != len(expected_schema["features"])
                    or not all(type(x) in (int, float) and math.isfinite(x) for x in observation)
                    or len(mask) != len(ACTIONS) or not all(type(x) is bool for x in mask) or not mask[a]
                    or observation[:2] != [float(role == r) for r in ROLES]):
                raise ValueError(f"Ungültige Beobachtung/Aktion/Maske in {path}, Ereignis {e.get('id')}")
            expected, actual = ACTIONS[a], e["action"]
            correct = expected.kind == actual.get("kind") and actual.get("role") == role
            if expected.kind in ("place", "coffee"):
                correct &= expected.die == actual.get("die")
            if expected.kind == "place":
                slot = SLOTS[expected.slot]
                correct &= (slot.owner in (None, role) and slot.target == actual.get("target")
                            and slot.index == actual.get("index") and slot.radio_index == actual.get("radio_index", 0))
            elif expected.kind == "coffee":
                correct &= expected.delta == actual.get("delta")
            elif expected.kind == "reroll_select":
                correct &= expected.subset == actual.get("subset")
            if not correct:
                raise ValueError(f"Aktions-ID und aufgezeichneter Zug widersprechen sich: {path}, Ereignis {e.get('id')}")
            observations.append(observation)
            masks.append(mask)
            actions.append(a)
            roles[role] += 1
            fingerprint_pairs.append([identity, observation, mask, a])
        if len(actions) == start:
            raise ValueError(f"Gewonnene Partie ohne nutzbare menschliche Entscheidungen: {path}")
        sources.append({"session_id": identity, "revision": revision, "path": str(path.resolve()),
                        "decisions": len(actions) - start})
    if not actions:
        raise ValueError(f"Keine gewonnenen, kompatiblen KI-no-Partien für {airport} gefunden.")
    manifest = {"version": 1, "sha256": hashlib.sha256(_canonical(fingerprint_pairs)).hexdigest(),
                "sessions": len(sources), "decisions": len(actions), "roles": dict(roles),
                "excluded": dict(excluded), "sources": sources}
    return Demonstrations(observations, masks, actions, manifest)


def coefficient(initial, steps, start, decay_steps):
    """Linear decay in NEW environment decisions; 0 explicitly means constant."""
    return initial * max(0.0, 1 - max(0, steps - start) / decay_steps) if decay_steps else initial
