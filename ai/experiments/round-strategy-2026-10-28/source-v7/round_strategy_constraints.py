"""Necessary public goal constraints, independent of dice or learned estimates.

These prune AI suggestions. The player's legal goal choices remain unchanged.
"""

def constrain(state, heads, mask):
    allowed={key:{value for i,value in enumerate(values) if mask[sum(len(v) for _,v in heads[:h])+i]}
             for h,(key,values) in enumerate(heads)}
    movements=allowed['movement_preference']
    if not (state['letzte_runde'] or state['warteschleife'] or state['entfernung']==0):
        # Without wind, even two sixes cannot cross an orange threshold >12.
        # Gear/flaps only increase thresholds; a future movement of 2 can then
        # never become possible again. Otherwise use the optimistic bound 2.
        maximum=1 if 'wind' not in state['module'] and state.get('aerodynamik_orange',8.5)>12 else 2
        automatic={None} if None in movements else set()
        possible={move for move in movements if move is not None and move<=maximum}
        future=max(0,state['hoehe']//1000-1)
        minimum=max(0,state['entfernung']-maximum*future)
        feasible={move for move in possible if move>=minimum}
        # If the position is already irrecoverable, still suggest the greatest
        # achievable progress instead of an arbitrary waiting goal.
        allowed['movement_preference']=(feasible or {max(possible)})|automatic
    focus=allowed['focus']
    gear_left=3-sum(state['fahrwerk_ausgefahren'])
    flaps_left=4-sum(state['landeklappen_ausgefahren'])
    if not sum(state['flugzeuge']):focus.discard('radio')
    if not gear_left+flaps_left:focus.discard('tasks')
    coordination=allowed['coordination']
    if not gear_left or not flaps_left:coordination.discard('synchronisation')
    braking_done=(state.get('eis_fortschritt',0)>=4 if 'ice' in state['module']
                  else all(state['bremsen_aktiviert']))
    if braking_done:coordination.discard('brakes')
    if state['letzte_runde']:coordination.discard('wind')
    if any(not choices for choices in allowed.values()):raise ValueError('A public goal head has no feasible choices.')
    return [value in allowed[key] for key,values in heads for value in values]
