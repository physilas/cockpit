"""Torch-free browser access to the exact training observation and action mask.

The authoritative game remains backend.bridge._spiel. No partner hand is
included in decisions or demonstration records.
"""
import json

from backend import bridge
from .environment import CrewEnv


def decision(role=None, reroll_json="null", steps=0, max_steps=256):
    game = bridge._spiel
    if game is None:
        raise ValueError("Kein Spiel aktiv.")
    if game.cockpit.module or game.zusatz.karten:
        raise ValueError("Die KI unterstützt bisher Grundspiel-Strecken ohne Module und Karten.")
    env = CrewEnv(max_steps=max_steps)
    env.game = game
    env.steps = steps
    env.reroll = json.loads(reroll_json)
    if role is not None and role != env.current_role:
        raise ValueError("Diese Rolle ist gerade nicht am Zug.")
    view = env.view()
    public = {key: value for key, value in view.items() if key != "own_dice"}
    return {"role": env.current_role, "observation": env.observation(),
            "action_mask": env.action_mask(), "public_state": public}
