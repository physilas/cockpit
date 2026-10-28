"""Browser inputs for new public strategies, without changing old profiles."""
import json

from backend import bridge
from .modules import ModuleEnv


def strategy_decision(role=None,reroll_json='null',steps=0,max_steps=256,*,policy='contract'):
    game=bridge._spiel
    if game is None:
        raise ValueError('Kein Spiel aktiv.')
    if policy not in ('contract','coherent'):
        raise ValueError('Unbekannte öffentliche Strategie.')
    env=ModuleEnv(max_steps=max_steps,assistance_version=0)
    env.game=game;env.validate_scenario()
    env.steps=steps;env.reroll=json.loads(reroll_json)
    if role is not None and role!=env.current_role:
        raise ValueError('Diese Rolle ist gerade nicht am Zug.')
    view=env.view();raw=env.action_mask()
    airport=game.landung._flughafen_code
    if policy=='contract':
        from .public_contract import public_contract_inputs
        allowed,reference,plan=public_contract_inputs(airport,view,raw)
    else:
        from .coherent_advice import coherent_masks
        allowed,reference,_=coherent_masks(airport,view,raw)
    return dict(role=env.current_role,observation=env.observation(),action_mask=allowed,
                reference_action_mask=reference,
                **({'public_plan':plan} if policy=='contract' else {}),
                public_state={key:value for key,value in view.items() if key!='own_dice'})
