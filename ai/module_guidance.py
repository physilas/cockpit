"""Profile 10: public module advice, separate from the released profile 9.

Reference masks guide the existing network; they do not remove alternatives.
Only independently qualified route/card cases may be advertised in the app.
"""
import json

from .fuel import _fuel_assist
from .module_capacity import reserve_controls
from .modules import MODULE_ACTIONS, MODULE_SLOTS


def _legacy(view, raw):
    """Exact old 9/7 behavior on base/fuel without cards."""
    prefix = list(raw[:125])
    own = sum(bool(value) for value in view['own_dice'])
    missing = sum(slot.owner == view['role'] and slot.target in ('ruder', 'triebwerk')
                  and view['board'][index] is None
                  for index, slot in enumerate(MODULE_SLOTS[:20]))
    if own <= missing:
        for index, action in enumerate(MODULE_ACTIONS[:125]):
            if action.kind == 'place' and MODULE_SLOTS[action.slot].target not in ('ruder', 'triebwerk'):
                prefix[index] = False
    serialized = json.dumps(view, sort_keys=True)
    padding = [False] * (len(raw)-125)
    return (list(_fuel_assist(serialized, tuple(prefix), 9)) + padding,
            list(_fuel_assist(serialized, tuple(prefix), 7)) + padding)


def module_guidance(view, raw):
    """Return (allowed, reference), using own dice and public state only.

    Compatible kerosene/card physics can reuse public fuel advice. Wind, ice
    and leak deliberately retain legal choices until their scoring is ready.
    An issued intern token has its own deterministic public continuation.
    """
    if len(raw) != len(MODULE_ACTIONS) or any(type(flag) is not bool for flag in raw):
        raise ValueError('Expected a schema-3 Boolean engine mask.')
    raw = list(raw)
    if not any(raw):
        return raw, list(raw)
    state = view['modules_state']
    modules, cards = set(state['modules']), state['cards']
    if modules <= {'kerosene'} and not cards:
        return _legacy(view, raw)
    allowed = reserve_controls(view, raw)
    if any(ok and action.kind == 'swap_choose' for ok, action in zip(allowed, MODULE_ACTIONS)):
        for index, action in enumerate(MODULE_ACTIONS):
            if action.kind == 'swap_cancel':
                allowed[index] = False
    if 'intern' in modules:
        from .intern_advice import intern_reference
        reference = intern_reference(view, allowed)
    elif (modules <= {'kerosene', 'realtime'} and not state['pending'] and not state['swap']
          and any(allowed[:125])):
        prefix = list(_fuel_assist(json.dumps(view, sort_keys=True), tuple(allowed[:125]), 7))
        reference = prefix + [False] * (len(allowed)-125)
    else:
        reference = list(allowed)
    reference = [bool(legal and advised) for legal, advised in zip(allowed, reference)]
    return allowed, reference if any(reference) else list(allowed)
