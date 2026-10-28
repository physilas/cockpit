"""Torch-free browser access to the exact training observation and action mask.

The authoritative game remains backend.bridge._spiel. No partner hand is
included in decisions or demonstration records.
"""
import json

from backend import bridge
from .environment import CrewEnv


def decision(role=None, reroll_json="null", steps=0, max_steps=256, assistance_version=0, schema_version=1):
    if assistance_version in (13,14):
        if schema_version!=3:
            raise ValueError('Die neue öffentliche Strategie benötigt KI-Schema3.')
        from .strategy_bridge import strategy_decision
        return strategy_decision(role,reroll_json,steps,max_steps,
                                 policy='contract' if assistance_version==13 else 'coherent')
    game = bridge._spiel
    if game is None:
        raise ValueError("Kein Spiel aktiv.")
    if schema_version not in (1, 2, 3):
        raise ValueError("Unbekanntes KI-Schema.")
    env_class = CrewEnv
    if schema_version == 3:
        from .modules import ModuleEnv
        env_class = ModuleEnv
    elif schema_version == 2:
        from .fuel import FuelEnv
        env_class = FuelEnv
    env = env_class(max_steps=max_steps, assistance_version=assistance_version)
    env.game = game
    env.validate_scenario()
    env.steps = steps
    env.reroll = json.loads(reroll_json)
    if role is not None and role != env.current_role:
        raise ValueError("Diese Rolle ist gerade nicht am Zug.")
    view = env.view()
    public = {key: value for key, value in view.items() if key != "own_dice"}
    info = env.info()
    return {"role": env.current_role, "observation": env.observation(),
            "action_mask": info['action_mask'], "public_state": public,
            **({'reference_action_mask':info['reference_action_mask']} if 'reference_action_mask' in info else {})}
