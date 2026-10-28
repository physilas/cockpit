"""Additive browser adapter: old model IDs still call the frozen old bridge."""
import json
from backend import bridge
from .browser_bridge import decision as legacy_decision
from .modules import ModuleEnv
from .ability_policy import ability_inputs


def decision(role=None, reroll_json='null', steps=0, max_steps=256, assistance_version=0, schema_version=1):
    if assistance_version != 15:
        return legacy_decision(role, reroll_json, steps, max_steps, assistance_version, schema_version)
    if schema_version != 3 or max_steps != 256:
        raise ValueError('Ability planning requires schema 3 and a 256-decision budget.')
    game = bridge._spiel
    if game is None:
        raise ValueError('Kein Spiel aktiv.')
    env = ModuleEnv(max_steps=max_steps, assistance_version=0)
    env.game = game
    env.validate_scenario()
    env.steps, env.reroll = steps, json.loads(reroll_json)
    if role is not None and role != env.current_role:
        raise ValueError('Diese Rolle ist gerade nicht am Zug.')
    view, raw = env.view(), env.action_mask()
    allowed, reference, plan = ability_inputs(game.landung._flughafen_code, view, raw)
    return dict(role=env.current_role, observation=env.observation(), action_mask=allowed,
                reference_action_mask=reference, public_plan=plan,
                public_state={key:value for key,value in view.items() if key != 'own_dice'})
