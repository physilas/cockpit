"""Versioned state_dict checkpoints, loaded with weights_only=True."""
from dataclasses import asdict
from pathlib import Path

import torch

from .actions import ACTIONS, SLOTS, SCHEMA_VERSION
from .nn_model import ActorCritic
from .observation import feature_names


def schema():
    return {"version": SCHEMA_VERSION, "features": feature_names(),
            "actions": [asdict(a) for a in ACTIONS], "slots": [asdict(s) for s in SLOTS]}


def save_checkpoint(path, model, **metadata):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {**metadata, "schema": schema(), "model_config": model.config,
               "model_state": model.state_dict()}
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(payload, temporary)
    temporary.replace(path)


def load_checkpoint(path, device="cpu"):
    payload = torch.load(path, map_location=device, weights_only=True)
    if payload.get("schema") != schema():
        raise ValueError("Checkpoint und aktuelles Beobachtungs-/Aktionsformat passen nicht zusammen.")
    model = ActorCritic(**payload["model_config"]).to(device)
    model.load_state_dict(payload["model_state"])
    model.eval()
    return model, payload
