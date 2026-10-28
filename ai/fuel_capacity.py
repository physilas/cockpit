"""Necessary count of future kerosene-field payments from public fuel alone.

An empty field costs6; a die can reduce that cost by at most5 (face1).
This counts dice that a long-horizon task budget cannot spend on upgrades or
radio at the same time. It promises no actual face, owner or future card die.
"""
from math import ceil


def necessary_fuel_fields(view):
    modules=set(view['modules_state']['modules'])
    if 'kerosene' not in modules or 'leak' in modules:
        return dict(applicable=False,minimum_payments=0,unpaid_rounds=0,possible=True)
    future=0 if view['last_round'] else max(0,int(view['height']//1000))
    unpaid=future+int(not view['fuel']['occupied'])
    remaining=view['fuel']['remaining']
    minimum=max(0,ceil((6*unpaid-remaining+1)/5))
    return dict(applicable=True,minimum_payments=minimum,unpaid_rounds=unpaid,
                possible=minimum<=unpaid)
