"""Conservative public control reservations for a future research phase.

This module is deliberately not connected to the active training environment or
published profiles. It only removes engine-legal optional placements when a
known die is required for a still-empty rudder/thrust field. Intern training is
a replacement, and an issued black die is one shared resource. An uncertain
future synchronization trigger causes abstention, never automatic die credit.
"""
from .actions import ROLES
from .modules import CARDS, MODULES, MODULE_ACTIONS, MODULE_SLOTS


def control_budget(view):
    """Read own hand/public counts only; do not accept an engine or RNG."""
    role = view['role']
    if role not in ROLES:
        raise ValueError('Unknown acting role.')
    other = ROLES[1 - ROLES.index(role)]
    regular = {role: sum(bool(face) for face in view['own_dice']),
               other: view['partner_remaining']}
    missing = {r: sum(slot.owner == r and slot.target in ('ruder', 'triebwerk')
                      and view['board'][index] is None
                      for index, slot in enumerate(MODULE_SLOTS[:20])) for r in ROLES}
    state = view.get('modules_state', {})
    pending = state.get('pending')
    issued_intern = {r: 0 for r in ROLES}
    shared = 0
    unknown = False
    if pending:
        if pending.get('source') == 'intern' and pending.get('role') in ROLES:
            issued_intern[pending['role']] = 1
        elif pending.get('source') == 'synchronisation':
            shared = 1
        else:
            unknown = True
    available = {r: regular[r] + issued_intern[r] for r in ROLES}
    deficits = {r: max(0, missing[r] - available[r]) for r in ROLES}
    # Readiness refers to currently occupied public fields, matching the real
    # trigger. Public capacity provides only an upper bound on future creation;
    # unseen faces are neither read nor assumed favorable for a chosen move.
    gear_ready = any(view['board'][index] is not None for index in range(7, 10))
    flap_ready = any(view['board'][index] is not None for index in range(10, 14))
    cards = set(state.get('cards', ()))
    sync_uncertain = ('synchronisation' in cards and not state.get('sync_triggered', False)
                      and not shared and (gear_ready or available['pilot'] > 0)
                      and (flap_ready or available['kopilot'] > 0))
    return {'regular': regular, 'issued_intern': issued_intern,
            'available_by_role': available, 'missing_by_role': missing,
            'shared_bonus': shared, 'total_available': sum(available.values()) + shared,
            'deficit_by_role': deficits, 'future_sync_uncertain': bool(sync_uncertain),
            'unknown_state': (unknown or bool(cards - set(CARDS))
                              or bool(set(state.get('modules', ())) - set(MODULES)))}


def reserve_controls(view, engine_legal_mask):
    """Return a conservative subset; the caller supplies actual engine legality.

    Helper actions retain their legality. A known infeasible/unknown state is
    left unchanged because this primitive is not a complete rescue search.
    """
    if len(engine_legal_mask) != len(MODULE_ACTIONS) or any(type(flag) is not bool for flag in engine_legal_mask):
        raise ValueError('Expected the schema-3 engine-legal Boolean mask.')
    original = list(engine_legal_mask)
    budget = control_budget(view)
    if budget['unknown_state'] or budget['future_sync_uncertain']:
        return original
    if sum(budget['deficit_by_role'].values()) > budget['shared_bonus']:
        return original
    state = view.get('modules_state', {})
    pending = state.get('pending')
    role = view['role']
    forced_role = None
    if pending and pending['source'] == 'synchronisation':
        deficient = [r for r in ROLES if budget['deficit_by_role'][r]]
        if len(deficient) == 1:
            forced_role = deficient[0]
    elif pending and pending['source'] == 'intern':
        owner = pending['role']
        if budget['regular'][owner] < budget['missing_by_role'][owner]:
            forced_role = owner
    elif (budget['regular'][role] > 0
          and budget['regular'][role] == budget['missing_by_role'][role]):
        forced_role = role
    if forced_role is None:
        return original
    result = list(original)
    for index, (allowed, action) in enumerate(zip(original, MODULE_ACTIONS)):
        if not allowed or action.kind not in ('place', 'bonus_place'):
            continue
        slot = MODULE_SLOTS[action.slot]
        control = slot.owner == forced_role and slot.target in ('ruder', 'triebwerk')
        # A regular training placement spends one regular die and immediately
        # issues one same-role token. With an empty own control it preserves
        # control capacity, rather than spending a die on an optional task.
        replacement = (not pending and action.kind == 'place'
                       and slot.target == 'training' and slot.owner == forced_role)
        if not control and not replacement:
            result[index] = False
    # Never manufacture a no-action terminal from a limited reservation rule.
    return result if any(result) else original
