"""Union alternative static partner tasks before counting hypothetical hands.

Each alternative consumes distinct dice and the same single coffee budget.
Alternatives are contingent choices for one fixed own plan, never sums of
overlapping win probabilities or access to the actual partner hand.
"""
from .joint_landing_prior import _reach
from .joint_round import _tasks
from .public_hand_prior import _weight


def alternative_task_value(groups, remaining, coffee, *, rudder=None, thrust=None):
    if (type(remaining) is not int or not 0<=remaining<=4 or type(coffee) is not int
            or not 0<=coffee<=3 or any(v is not None and (type(v) is not int or not 1<=v<=6)
                                     for v in (rudder,thrust))):
        raise ValueError('Use a fair remaining hand and one valid coffee budget.')
    missing=int(rudder is None)+int(thrust is None)
    prepared=[]
    for pairs,tasks in groups:
        if len(pairs)!=36 or any(type(v) is not bool for v in pairs):
            raise ValueError('Every alternative needs 36 Boolean physical outcomes.')
        tasks=_tasks(tasks)
        if missing+len(tasks)>remaining or not any(pairs):
            continue
        targets,masks=_reach(remaining,missing,tasks,None)
        indices=[]
        for index,target in enumerate(targets):
            r=target[0] if rudder is None else rudder
            t=target[-1] if thrust is None else thrust
            if pairs[(r-1)*6+t-1]:
                indices.append(index)
        prepared.append((indices,masks))
    covered=0
    total=0.
    for cost in range(coffee+1):
        bits=0
        for indices,masks in prepared:
            for index in indices:
                bits|=masks[cost][index]
        newly=bits&~covered
        total+=(10000.+1.5*(coffee-cost))*_weight(remaining,newly)
        covered|=bits
    return total/6**remaining
