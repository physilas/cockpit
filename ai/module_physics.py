"""Pure public wind/ice/fuel projections checked against the actual engine.

These are physical consequences and necessary resource bounds, not a policy or
proof that enough dice exist to realize a plan. Callers supply their own known
faces or independently sampled hypotheses. This module has no engine instance,
partner hand, random generator, future real rolls or released planner changes.
"""
import math

from backend.cockpit import Cockpit


WIND_RING = tuple(Cockpit.WIND_RING)


def active_modules(view):
    if 'modules_state' in view:
        return frozenset(view['modules_state']['modules'])
    return frozenset({'kerosene'} if view.get('fuel', {}).get('present') else ())


def _face(value):
    if type(value) is not int or not 1 <= value <= 6:
        raise ValueError('Control hypotheses must be integer faces in 1..6.')
    return value


def _pair(view, target, pilot_value, kopilot_value):
    indices = (0, 1) if target == 'ruder' else (2, 3)
    values = []
    for index, supplied in zip(indices, (pilot_value, kopilot_value)):
        placed = view['board'][index]
        if placed is not None:
            public = _face(placed['value'])
            if supplied is not None and _face(supplied) != public:
                raise ValueError('A hypothetical assignment cannot change a public placed die.')
            values.append(public)
        elif supplied is not None:
            values.append(_face(supplied))
        else:
            values.append(None)
    return values, all(view['board'][index] is not None for index in indices)


def wind_value(position):
    if type(position) is not int or not 0 <= position < len(WIND_RING):
        raise ValueError('Wind position must be an integer ring index in 0..17.')
    return WIND_RING[position]


def predict_rudder(view, pilot_value=None, kopilot_value=None):
    """Resolve one complete rudder pair exactly once, including wind/control.

    Already placed pairs have already changed the attitude/wind/coffee gauge.
    On a stall the engine skips the wind/card post-placement hook entirely.
    """
    values, resolved = _pair(view, 'ruder', pilot_value, kopilot_value)
    if None in values:
        raise ValueError('A complete rudder hypothesis or public pair is required.')
    attitude = view['attitude'] if resolved else view['attitude'] + values[1] - values[0]
    stalled = abs(attitude) >= 3
    modules = active_modules(view)
    position = view.get('modules_state', {}).get('wind_position', 0)
    if 'wind' in modules:
        wind_value(position)
        if not resolved and not stalled:
            position = (position + attitude) % len(WIND_RING)
        wind = wind_value(position)
    else:
        position, wind = None, 0
    cards = view.get('modules_state', {}).get('cards', ())
    coffee = view['coffee']
    gain = int(not resolved and not stalled and values[0] == values[1] and 'control' in cards and coffee < 3)
    return {'attitude': attitude, 'wind_position': position, 'wind_value': wind,
            'stalled': stalled, 'reason': 'trudeln' if stalled else '',
            'already_resolved': resolved, 'coffee': coffee+gain, 'coffee_gain': gain}


def landing_speed_bound(view, *, additional_ice_pairs=0, additional_brakes=0):
    """Exact inclusive integer speed bound; ice uses the engine's strict test."""
    modules = active_modules(view)
    if type(additional_ice_pairs) is not int or type(additional_brakes) is not int:
        raise ValueError('Brake upgrades must be integer counts.')
    if 'ice' in modules:
        progress = view['modules_state']['ice_progress']
        if (type(progress) is not int or not 0 <= progress <= 4 or
                not 0 <= additional_ice_pairs <= 4-progress or additional_brakes):
            raise ValueError('Invalid prospective ice-brake progress.')
        strength, strict = 1.5 + progress + additional_ice_pairs, True
    else:
        progress = sum(bool(value) for value in view['brake_progress'])
        if additional_ice_pairs or not 0 <= additional_brakes <= 3-progress:
            raise ValueError('Invalid prospective regular-brake progress.')
        strength, strict = view['brakes'] + 2*additional_brakes, False
    maximum = math.ceil(strength)-1 if strict else math.floor(strength)
    return {'strength': strength, 'strict': strict, 'maximum_integer_speed': maximum}


def ice_brake_bound(view, additional_pairs=0):
    if 'ice' not in active_modules(view):
        raise ValueError('Ice-brake bounds require the ice module.')
    return landing_speed_bound(view, additional_ice_pairs=additional_pairs)


def movement_projection(view, speed, attitude=None, *, additional_ice_pairs=0, additional_brakes=0):
    """Project the engine's end-of-round motion/braking, excluding final tasks.

    The engine checks traffic at the current distance and curves on every
    crossed cell. Holding suppresses movement; landing compares braking instead
    of aerodynamic markers. Gear/flaps/final traffic checks remain separate.
    """
    if not isinstance(speed, (int, float)) or isinstance(speed, bool) or not math.isfinite(speed):
        raise ValueError('Speed must be finite.')
    attitude = view['attitude'] if attitude is None else attitude
    if type(attitude) is not int:
        raise ValueError('Attitude must be an integer.')
    result = {'speed': speed, 'movement': 0, 'attempted_movement': 0, 'reason': '', 'blocked_distance': None}
    if view['last_round']:
        bound = landing_speed_bound(view, additional_ice_pairs=additional_ice_pairs, additional_brakes=additional_brakes)
        result['braking'] = bound
        too_fast = speed >= bound['strength'] if bound['strict'] else speed > bound['strength']
        if too_fast:
            result['reason'] = 'zu_schnell_gelandet'
        return result
    if view['holding']:
        return result
    movement = int(speed >= view['aero_blue']) + int(speed >= view['aero_orange'])
    result['attempted_movement'] = movement
    if not movement:
        return result
    if movement > view['distance']:
        result['reason'] = 'uebers_ziel_hinaus'
        return result
    cells = {cell['distance']: cell for cell in view['track']}
    if cells[view['distance']]['planes'] > 0:
        result['reason'] = 'kollision'
        result['blocked_distance'] = view['distance']
        return result
    for offset in range(movement):
        distance = view['distance'] - offset
        cell = cells[distance]
        if not cell['min'] <= attitude <= cell['max']:
            result['reason'] = 'ruder_verbotene_stellung'
            result['blocked_distance'] = distance
            return result
    result['movement'] = movement
    return result


def fuel_budget(view, pilot_thrust=None, kopilot_thrust=None, *, kerosene_payment=None):
    """Current fuel consequence plus necessary one-unit-per-future-round bound.

    Unresolved leak with no complete thrust hypothesis uses its minimum cost1;
    it never asserts that the team can actually produce equal thrust. An empty
    kerosene field costs6 unless an explicit prospective payment is supplied.
    Publicly paid controls/kerosene are not charged again. Survival requires
    strictly positive fuel even after the final round.
    """
    modules = active_modules(view)
    future_rounds = 0 if view['last_round'] else max(0, int(view['height']//1000))
    if not modules & {'kerosene', 'leak'}:
        return {'present': False, 'remaining': None, 'current_cost': 0, 'after_current': None,
                'future_rounds': future_rounds, 'necessary_survival': True,
                'survival_margin': None, 'reason': ''}
    remaining = view['fuel']['remaining']
    if type(remaining) is not int or remaining < 0:
        raise ValueError('Fuel must be a nonnegative integer.')
    if 'leak' in modules:
        if kerosene_payment is not None:
            raise ValueError('Leak has no kerosene payment field.')
        values, resolved = _pair(view, 'triebwerk', pilot_thrust, kopilot_thrust)
        cost = 0 if resolved else abs(values[0]-values[1])+1 if None not in values else 1
        exact = resolved or None not in values
    else:
        if view['fuel']['occupied']:
            if kerosene_payment is not None:
                raise ValueError('An already occupied kerosene field is already paid.')
            cost = 0
        else:
            cost = 6 if kerosene_payment is None else _face(kerosene_payment)
        exact = True
    after = max(0, remaining-cost)
    margin = after-future_rounds-1
    return {'present': True, 'remaining': remaining, 'current_cost': cost, 'current_cost_exact': exact,
            'after_current': after, 'future_rounds': future_rounds,
            'minimum_future_cost': future_rounds, 'minimum_after_current': future_rounds+1,
            'maximum_safe_current_cost': remaining-future_rounds-1,
            'necessary_survival': margin >= 0, 'survival_margin': margin,
            'reason': 'kerosin_leer' if after == 0 else ''}


def predict_thrust(view, pilot_value=None, kopilot_value=None, *, rudder=None,
                   kerosene_payment=None, additional_ice_pairs=0, additional_brakes=0):
    """Complete thrust pair with the projected wind, ice braking and fuel.

    For wind, an unfinished rudder pair requires an explicit projected rudder
    outcome. Current wind alone is not a forecast of the future final speed.
    """
    values, resolved = _pair(view, 'triebwerk', pilot_value, kopilot_value)
    if None in values:
        raise ValueError('A complete thrust hypothesis or public pair is required.')
    modules = active_modules(view)
    if rudder is None:
        if 'wind' in modules:
            if view['board'][0] is None or view['board'][1] is None:
                raise ValueError('Wind speed needs the prospective complete rudder outcome.')
            rudder = predict_rudder(view)
        else:
            rudder = {'attitude': view['attitude'], 'wind_value': 0, 'stalled': abs(view['attitude']) >= 3}
    speed = values[0] + values[1] + (rudder['wind_value'] if 'wind' in modules else 0)
    motion = movement_projection(view, speed, rudder['attitude'],
        additional_ice_pairs=additional_ice_pairs, additional_brakes=additional_brakes)
    fuel = fuel_budget(view, values[0], values[1], kerosene_payment=kerosene_payment)
    failures = []
    if rudder['stalled']: failures.append('trudeln')
    if fuel['reason']: failures.append(fuel['reason'])
    if motion['reason']: failures.append(motion['reason'])
    if failures:
        motion['movement'] = 0
    return {**motion, 'attitude': rudder['attitude'], 'wind_value': rudder['wind_value'],
            'already_resolved': resolved, 'fuel': fuel, 'failures': failures,
            'motion_reason': motion['reason'], 'reason': failures[0] if failures else '',
            'physics_safe': not failures}
