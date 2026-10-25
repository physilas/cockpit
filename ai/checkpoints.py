"""Versioned state_dict checkpoints, loaded with weights_only=True."""
from dataclasses import asdict
from pathlib import Path
import hashlib
import json

import torch

from .actions import ACTIONS, SLOTS, SCHEMA_VERSION
from .nn_model import build_model
from .observation import feature_names


def schema(version=1):
    if version == 3:
        from .modules import module_schema
        return module_schema()
    if version == 2:
        from .fuel import fuel_schema
        return fuel_schema()
    if version != 1:
        raise ValueError("Unknown model schema.")
    return {"version": SCHEMA_VERSION, "features": feature_names(),
            "actions": [asdict(a) for a in ACTIONS], "slots": [asdict(s) for s in SLOTS]}


def model_schema(model):
    dimensions = (model.config["observation_size"], model.config["action_count"])
    for version in (1, 2, 3):
        candidate = schema(version)
        if dimensions == (len(candidate["features"]), len(candidate["actions"])):
            return candidate
    raise ValueError("Unregistered model dimensions.")


def weight_fingerprint(model):
    """Stable across checkpoint metadata, devices and torch.save containers."""
    digest = hashlib.sha256(json.dumps(model.config, sort_keys=True).encode())
    for name, tensor in sorted(model.state_dict().items()):
        digest.update(name.encode())
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def planner_fingerprint(version=1):
    digest = hashlib.sha256()
    for name in ('tactics.py', 'horizon.py', 'public_rules.py', 'environment.py', 'actions.py', 'observation.py', 'fuel.py'):
        digest.update(name.encode())
        digest.update(Path(__file__).with_name(name).read_bytes())
    if version == 3:
        for name in ('modules.py', 'module_guidance.py', 'module_capacity.py', 'intern_advice.py',
                     'leak_advice.py', 'leak_card_advice.py', 'module_physics.py', 'throttle.py'):
            digest.update(name.encode())
            digest.update(Path(__file__).with_name(name).read_bytes())
    return digest.hexdigest()


def save_checkpoint(path, model, **metadata):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {**metadata, "schema": model_schema(model), "model_config": model.config,
               "model_state": model.state_dict()}
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(payload, temporary)
    temporary.replace(path)


def load_checkpoint(path, device="cpu"):
    payload = torch.load(path, map_location=device, weights_only=True)
    if payload.get("schema") != schema(payload.get("schema", {}).get("version")):
        raise ValueError("Checkpoint und aktuelles Beobachtungs-/Aktionsformat passen nicht zusammen.")
    model = build_model(payload["model_config"]).to(device)
    if model_schema(model) != payload["schema"]:
        raise ValueError("Model dimensions do not match its schema.")
    model.load_state_dict(payload["model_state"])
    model.eval()
    return model, payload
