"""Bounded public-information continuation model for the final three rounds.

Future hands are fair priors, never samples from the game's RNG. Control
feasibility is enumerated exactly; task/control dependence and future traffic
are approximated. The returned value is a search heuristic, not a win forecast.
"""
from functools import lru_cache
from itertools import combinations_with_replacement
from math import ceil, exp, factorial, prod


def _hands():
    result=[]
    for hand in combinations_with_replacement(range(1,7),4):
        weight=factorial(4)//prod(factorial(hand.count(n)) for n in set(hand))
        pairs={(a,b) for i,a in enumerate(hand) for j,b in enumerate(hand) if i!=j}
        bits=sum(1<<((a-1)*6+b-1) for a,b in pairs)
        result.append((hand,weight,pairs,bits))
    return tuple(result)


_HANDS=_hands()


@lru_cache(maxsize=2048)
def control_prior(delta,low,high,coffee):
    """Exact eight-die control feasibility, sharing each coffee unit once."""
    low,high=max(2,low),min(12,high)
    if low>high or abs(delta)>5:
        return 0.0
    compatible={}
    for a in range(1,7):
        for b in range(1,7):
            mask=0
            for c in range(1,7):
                rudder_cost=abs(c-a-delta)
                for d in range(1,7):
                    thrust_cost=max(0,low-b-d,b+d-high)
                    if rudder_cost+thrust_cost<=coffee:
                        mask|=1<<((c-1)*6+d-1)
            compatible[a,b]=mask
    wins=0
    for _,weight,pairs,_ in _HANDS:
        options=0
        for pair in pairs:
            options|=compatible[pair]
        wins+=weight*sum(other_weight for _,other_weight,_,bits in _HANDS if bits&options)
    return wins/6**8


@lru_cache(maxsize=1024)
def task_prior(requirements):
    """Availability of at most two optional tasks, without spending coffee."""
    if not requirements:
        return 1.0
    if len(requirements)>2:
        return 0.0
    wins=0
    for hand,weight,_,_ in _HANDS:
        if len(requirements)==1:
            good=any(d in requirements[0] for d in hand)
        else:
            good=any(a in requirements[0] and b in requirements[1]
                     for i,a in enumerate(hand) for j,b in enumerate(hand) if i!=j)
        wins+=weight*good
    return wins/6**4


def make_forecast(view):
    """Prepare a two-future-round rollout shared by current leaf plans.

    Future preparation follows a latest-deadline policy, with a choice of
    radio allocation, movement and attitude. Optional work/control priors are
    multiplied as an approximation; they do not assert independent dice use.
    """
    cells=tuple((c['distance'],c['min'],c['max'],c['traffic']) for c in view['track'])
    base_blue=view['aero_blue']-sum(view['gear'])
    base_orange=view['aero_orange']-sum(view['flaps'])
    height=int(view['height']//1000)
    partner='kopilot' if view['role']=='pilot' else 'pilot'
    from .actions import SLOTS
    missing=sum(s.owner==partner and s.target in ('ruder','triebwerk') and view['board'][i] is None
                for i,s in enumerate(SLOTS))
    radios=sum(s.owner==partner and s.target=='funk' and view['board'][i] is None
               for i,s in enumerate(SLOTS))
    current_clearance=max(0,min(radios,view['partner_remaining']-missing))

    def clear(traffic,distance,count):
        changed=list(traffic);faces=[]
        for i in sorted(range(len(cells)),key=lambda i:cells[i][0],reverse=True):
            face=distance-cells[i][0]+1
            if not 1<=face<=6:
                continue
            take=min(changed[i],count-len(faces))
            changed[i]-=take;faces.extend([face]*take)
            if len(faces)==count:
                break
        return tuple(changed),tuple(faces)

    def prepare(gear,flaps,brakes,pilot_work,copilot_work):
        p=[];c=[]
        if pilot_work and not brakes:
            p.append((2,));brakes=1;pilot_work-=1
        for i in range(3):
            if pilot_work and not gear&(1<<i):
                p.append(((1,2),(3,4),(5,6))[i]);gear|=1<<i;pilot_work-=1
        for _ in range(copilot_work):
            index=flaps.bit_count()
            if index<4:
                c.append(((1,2),(2,3),(4,5),(5,6))[index]);flaps|=1<<index
        return gear,flaps,brakes,tuple(p),tuple(c)

    @lru_cache(maxsize=4096)
    def landing(attitude,gear,flaps,brakes,coffee,traffic):
        # No plane behind the airport can still be reached by a positive die.
        if any(n and cells[i][0]!=0 for i,n in enumerate(traffic)):
            return 0.0
        pwork=3-gear.bit_count()+int(not brakes)
        cwork=4-flaps.bit_count()
        if max(pwork,cwork)>2:
            return 0.0
        gear,flaps,brakes,p,c=prepare(gear,flaps,brakes,pwork,cwork)
        count=sum(traffic);best=0.0
        for rp in range(min(1,2-len(p),count)+1):
            rc=count-rp
            if not 0<=rc<=min(2,2-len(c)):
                continue
            for extra in range(min(2-len(p)-rp,3-brakes)+1):
                brake_tasks=tuple(((2,4,6)[i],) for i in range(brakes,brakes+extra))
                chance=control_prior(-attitude,2,2*(brakes+extra),coffee)
                chance*=task_prior(tuple(sorted(p+((1,),)*rp+brake_tasks)))
                chance*=task_prior(tuple(sorted(c+((1,),)*rc)))
                best=max(best,chance)
        return best

    @lru_cache(maxsize=8192)
    def future(distance,attitude,gear,flaps,brakes,coffee,traffic,horizon,h):
        if any(n and cells[i][0]>distance for i,n in enumerate(traffic)):
            return 0.0
        if h==0:
            return landing(attitude,gear,flaps,brakes,coffee,traffic) if distance==0 else 0.0
        if distance>(int(12>=base_blue+gear.bit_count())+int(12>=base_orange+flaps.bit_count()))*h:
            return 0.0
        pneed=3-gear.bit_count()+int(not brakes);cneed=4-flaps.bit_count()
        if max(pneed,cneed)>2*(h+1) or pneed+cneed+sum(traffic)>4*(h+1):
            return 0.0
        if horizon==0:
            return exp(-.12*(pneed+cneed)-.08*sum(traffic))
        pwork=max(0,pneed-2*h);cwork=max(0,cneed-2*h)
        g,f,b,p,c=prepare(gear,flaps,brakes,pwork,cwork)
        blue,orange=ceil(base_blue+g.bit_count()),ceil(base_orange+f.bit_count())
        best=0.0
        for move in range(min(2,distance)+1):
            crossed=[i for i,cell in enumerate(cells) if distance-move<cell[0]<=distance]
            needed=sum(traffic[i] for i in crossed)
            maximum=min(sum(traffic),min(1,2-len(p))+min(2,2-len(c)))
            if needed>maximum:
                continue
            for count in sorted({needed,min(maximum,needed+1)}):
                remaining,faces=clear(traffic,distance,count)
                if len(faces)!=count or any(remaining[i] for i in crossed):
                    continue
                for rp in range(min(1,2-len(p),count)+1):
                    rc=count-rp
                    if not 0<=rc<=min(2,2-len(c)):
                        continue
                    work=task_prior(tuple(sorted(p+tuple((n,) for n in faces[:rp]))))
                    work*=task_prior(tuple(sorted(c+tuple((n,) for n in faces[rp:]))))
                    if not work:
                        continue
                    next_coffee=min(3,max(0,coffee-1)+4-len(p)-len(c)-count)
                    if distance==0:
                        low,high=2,12
                    else:
                        low,high=((2,blue-1),(blue,orange-1),(orange,12))[move]
                    for target in range(-2,3):
                        if any(not cells[i][1]<=target<=cells[i][2] for i in crossed):
                            continue
                        chance=control_prior(target-attitude,low,high,coffee)*work
                        if chance<=best:
                            continue
                        tail=future(distance-move,target,g,f,b,next_coffee,remaining,horizon-1,h-1)
                        # Public traffic-die locations affect expected workload;
                        # the actual future traffic rolls are never inspected.
                        stars=next((cell[3] for cell in cells if cell[0]==distance),0)
                        chance*=tail*exp(-.08*stars)
                        best=max(best,chance)
        return best

    @lru_cache(maxsize=1024)
    def after_round(move,attitude,gear,flaps,brakes,coffee,traffic):
        distance=view['distance']-move
        if distance<0:
            return 0.0
        passed=[i for i,cell in enumerate(cells) if distance<cell[0]<=view['distance']]
        if sum(traffic[i] for i in passed)>current_clearance:
            return 0.0
        traffic=tuple(0 if i in passed else n for i,n in enumerate(traffic))
        return future(distance,attitude,gear,flaps,brakes.bit_count(),coffee,traffic,2,height-1)

    return after_round
