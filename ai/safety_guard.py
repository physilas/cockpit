"""Public, engine-backed checks for avoidable immediate deterministic losses.

This shield is independent of win-rate shaping and neural weights. It does not
pretend that a legal move has a winning future. Random helper actions and turn
passing remain available; no sampled partner face is used to reject an action.
"""
from .belief_simulator import BeliefSimulator, fork_simulation, simulation_step
from .modules import MODULE_ACTIONS, MODULE_SLOTS


def safe_actions(airport, view, raw):
    if len(raw) != len(MODULE_ACTIONS) or any(type(flag) is not bool for flag in raw):
        raise ValueError('Expected the schema-3 engine-legal Boolean mask.')
    root = None
    result, rejected = list(raw), {}
    for index, allowed in enumerate(raw):
        if not allowed or MODULE_ACTIONS[index].kind not in ('place', 'bonus_place'):
            continue
        action = MODULE_ACTIONS[index]
        slot = MODULE_SLOTS[action.slot]
        face = (view['own_dice'][action.die] if action.kind == 'place'
                else view['modules_state']['pending']['value'])
        reason = None
        if slot.target == 'ruder':
            other = view['board'][1 if slot.owner == 'pilot' else 0]
            if other:
                attitude = view['attitude'] + (other['value'] - face if slot.owner == 'pilot' else face - other['value'])
                if abs(attitude) >= 3:
                    reason = 'trudeln'
        elif slot.target == 'triebwerk' and 'leak' in view['modules_state']['modules']:
            other = view['board'][3 if slot.owner == 'pilot' else 2]
            if other and abs(other['value'] - face) + 1 >= view['fuel']['remaining']:
                reason = 'kerosin_leer'
        elif slot.target == 'kerosin' and face >= view['fuel']['remaining']:
            reason = 'kerosin_leer'
        if reason:
            result[index] = False
            rejected[str(index)] = reason
            continue
        # Other deterministic placement losses only arise on round resolution.
        # Bonus-trigger deferral and exact final conditions stay in the engine.
        regular = sum(bool(value) for value in view['own_dice']) + view['partner_remaining']
        pending = view['modules_state']['pending']
        closing = regular == (1 if action.kind == 'place' else 0)
        if not closing:
            continue
        if root is None:
            root = BeliefSimulator(airport, view).sample(0)
        branch = fork_simulation(root)
        simulation_step(branch, index)
        if branch.game.status == 'verloren':
            # Placement can only read its own die and already placed public
            # partner controls. End of round means no free partner dice exist.
            result[index] = False
            rejected[str(index)] = branch.game.verlust_grund
    if not any(result):
        return list(raw), dict(rejected=rejected, fallback=True)
    return result, dict(rejected=rejected, fallback=False)


class ShieldedBlueprint:
    def __init__(self, airport, blueprint):
        self.airport, self.blueprint = airport, blueprint
        self.last_report = {}

    def select(self, view, mask):
        return self.rank(view, mask)[0]

    def rank(self, view, mask):
        safe, self.last_report = safe_actions(self.airport, view, mask)
        # Recompute guidance after removal. Old references can contain the
        # exact deterministic losing placement that was just rejected.
        return self.blueprint.rank(view, safe)
