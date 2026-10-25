"""Static terminal assignment with tasks and controls in one dice/coffee budget.

Exact only under the explicitly declared IID-fair remaining-partner-hand model
and these static requirements. Sequencing, future coffee/cards/bonus generation
and the actual biased partner hand are NOT predicted. One own assignment and
task ownership are fixed BEFORE expectation over partner hands.
"""
from functools import lru_cache
from itertools import permutations, product
from math import inf

from .joint_round import _task_cost, _tasks, _hand
from .public_hand_prior import fair_hands, _weight


_REACH = {}


@lru_cache(maxsize=8192)
def control_task_costs(hand, missing, tasks):
    """Minimum L1 coffee for each target tuple, using distinct regular dice."""
    targets = tuple(product(range(1,7),repeat=missing))
    best = [inf]*len(targets)
    if missing+len(tasks)>len(hand):return tuple(zip(targets,best))
    raw = {}
    for indices in permutations(range(len(hand)),missing):
        faces=tuple(hand[i] for i in indices)
        rest=tuple(face for i,face in enumerate(hand) if i not in indices)
        cost=_task_cost(rest,tasks)
        raw[faces]=min(raw.get(faces,inf),cost)
    for index,target in enumerate(targets):
        best[index]=min((cost+sum(abs(a-b) for a,b in zip(faces,target))
                         for faces,cost in raw.items()),default=inf)
    return tuple(zip(targets,best))


def _reach(remaining,missing,tasks,cooperate):
    key=remaining,missing,tasks
    if key in _REACH:return _REACH[key]
    targets=tuple(product(range(1,7),repeat=missing))
    masks=[[0]*len(targets) for _ in range(4)]
    for number,(hand,_) in enumerate(fair_hands(remaining)):
        if cooperate is not None:cooperate()
        for index,(_,cost) in enumerate(control_task_costs(hand,missing,tasks)):
            if cost<=3:
                for budget in range(int(cost),4):masks[budget][index]|=1<<number
    result=targets,tuple(tuple(row) for row in masks)
    if len(_REACH)>=256:_REACH.pop(next(iter(_REACH)))
    _REACH[key]=result
    return result


def fair_task_value(valid_pairs,remaining,coffee,tasks=(),*,rudder=None,thrust=None,cooperate=None):
    """Expected static-success reward10000 plus retained-coffee tie breaker.

    Partner chooses its best compatible pair INSIDE each hypothetical hand.
    Successes are unioned before counting; several assignments of the same
    hand never count twice. Infeasible hands contribute zero, not a fake win.
    """
    if (len(valid_pairs)!=36 or any(type(v) is not bool for v in valid_pairs)
            or type(remaining) is not int or not 0<=remaining<=4
            or type(coffee) is not int or not 0<=coffee<=3):
        raise ValueError('Require36 Boolean pair outcomes,0..4 dice and0..3 coffee.')
    if any(v is not None and (type(v) is not int or not 1<=v<=6) for v in (rudder,thrust)):
        raise ValueError('Published control faces are immutable integer1..6.')
    tasks=_tasks(tasks)
    missing=int(rudder is None)+int(thrust is None)
    if remaining<missing+len(tasks) or not any(valid_pairs):return 0.
    targets,masks=_reach(remaining,missing,tasks,cooperate)
    covered,total=0,0.
    for cost in range(coffee+1):
        if cooperate is not None:cooperate()
        bits=0
        for index,target in enumerate(targets):
            r=target[0] if rudder is None else rudder
            t=target[-1] if thrust is None else thrust
            if valid_pairs[(r-1)*6+t-1]:bits|=masks[cost][index]
        new=bits&~covered
        total+=(10000.+1.5*(coffee-cost))*_weight(remaining,new)
        covered|=new
    return total/6**remaining


def own_options(hand,*,rudder=None,thrust=None,tasks=()):
    hand=_hand(hand);tasks=_tasks(tasks)
    missing=int(rudder is None)+int(thrust is None)
    return tuple((target[0] if rudder is None else rudder,
                  target[-1] if thrust is None else thrust,cost)
                 for target,cost in control_task_costs(hand,missing,tasks))
