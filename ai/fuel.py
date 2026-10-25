"""Schema 2: base-game prefix plus one shared kerosene field (no cards).

Torch-free, identical in native training and Pyodide. Neither a partner hand
nor future random outcomes are available to the fuel planner.
"""
from dataclasses import asdict
from functools import lru_cache
import json

from .actions import ACTIONS, SLOTS, Action, Slot
from .environment import CrewEnv
from .observation import encode, feature_names

FUEL_SLOTS = SLOTS + (Slot('kerosin'),)
FUEL_ACTIONS = ACTIONS + tuple(Action('place', die=i, slot=len(SLOTS)) for i in range(4))
FUEL_FEATURES = feature_names() + ['fuel.present', 'fuel.remaining', 'fuel.occupied']


def fuel_schema():
    return {'version': 2, 'features': FUEL_FEATURES,
            'actions': [asdict(a) for a in FUEL_ACTIONS], 'slots': [asdict(s) for s in FUEL_SLOTS]}


def fuel_encode(view):
    fuel = view['fuel']
    return encode(view) + [float(fuel['present']), fuel['remaining'] / 20, float(fuel['occupied'])]


def fuel_capacity_mask(view, mask):
    """Necessary shared-die/fuel bounds, with no partner faces or extra dice.

    With R future rounds at least R fuel must remain plus one to stay alive.
    If leaving the field empty violates that bound, the team's last spare die
    cannot be spent on another task. Shared work is counted only once.
    """
    if view['fuel']['occupied']:
        return mask
    result = list(mask)
    role = view['role']
    partner = 'kopilot' if role == 'pilot' else 'pilot'
    missing = {r:sum(s.owner==r and s.target in ('ruder','triebwerk') and view['board'][i] is None
                    for i,s in enumerate(SLOTS)) for r in (role,partner)}
    own = sum(bool(v) for v in view['own_dice'])
    partner_spare = view['partner_remaining'] - missing[partner]
    future = 0 if view['last_round'] else int(view['height']//1000)
    maximum = view['fuel']['remaining'] - future - 1
    must_pay = maximum < 6
    for i,a in enumerate(FUEL_ACTIONS):
        if not result[i] or a.kind != 'place':
            continue
        if a.slot == len(SLOTS):
            result[i] = view['own_dice'][a.die] <= maximum
        elif must_pay and partner_spare <= 0:
            mandatory = SLOTS[a.slot].target in ('ruder','triebwerk')
            result[i] = own - 1 - (missing[role] - int(mandatory)) >= 1
    return result if any(result) else mask


@lru_cache(maxsize=512)
def _fuel_assist(serialized, mask, profile):
    # Research profile 9 widens only placement shortlists relative to profile
    # 7. Budget bounds, coffee options and rescue rerolls retain their meaning.
    # Schema-1's separately versioned profile 9 is unchanged.
    from .tactics import assisted_mask, capacity_mask, plan_actions
    view = json.loads(serialized)
    view['_fuel_profile'] = profile
    plan_version = 4 if profile in (4, 5, 8) else 3
    if not view['fuel']['present']:
        if profile == 9:
            from .tactics import _assisted_mask
            return tuple(_assisted_mask({k: v for k, v in view.items() if k != 'fuel'},
                                        mask[:len(ACTIONS)], 3, placement_margin=16) + [False] * 4)
        return tuple(assisted_mask({k: v for k, v in view.items() if k != 'fuel'}, mask[:len(ACTIONS)], version=3) + [False] * 4)
    if view['reroll']:
        from .tactics import _future_action_mask
        future = _future_action_mask(view, coffee=True)
        required = sum(s.owner == view['role'] and s.target in ('ruder','triebwerk') and view['board'][i] is None
                       for i,s in enumerate(SLOTS))
        spare = sum(bool(v) for v in view['own_dice']) > required
        future += [bool(v and spare and not view['fuel']['occupied']) for v in view['own_dice']]
        planned = {**view, 'board': view['board'] + ([{'value':1,'owner':'pilot'}] if view['fuel']['occupied'] else [None])}
        ranked, _ = plan_actions(planned, future, version=plan_version, beam=64)
        poor = max(ranked.values(), default=-10000) < -100
        wanted = sum(1 << i for i,v in enumerate(view['own_dice']) if v) if poor else 0
        eligible = [i for i,a in enumerate(ACTIONS) if mask[i] and a.kind=='reroll_select']
        result = [False]*len(mask)
        if eligible:
            result[min(eligible, key=lambda i:(ACTIONS[i].subset ^ wanted).bit_count())] = True
        return tuple(result if any(result) else mask)
    base = capacity_mask(view, mask[:len(ACTIONS)], include_traffic=True) + list(mask[len(ACTIONS):])
    if profile in (7,8,9):
        base = fuel_capacity_mask(view, base)
    planned = dict(view)
    planned['board'] = view['board'] + ([{'value': 1, 'owner': 'pilot'}] if view['fuel']['occupied'] else [None])
    planning_mask = [allowed and a.kind not in ('reroll_start', 'reroll_select') for a, allowed in zip(FUEL_ACTIONS, base)]
    ranked, _ = plan_actions(planned, planning_mask, version=plan_version, beam=64)
    best = max(ranked.values(), default=-10000)
    # Leave alternatives for PPO to learn task/fuel tradeoffs. Keep the base
    # profile's justified rescue reroll when no complete own plan survives.
    result = [bool(base[i] and ranked.get(i, -1e30) >= best -
                   (16 if profile == 9 and FUEL_ACTIONS[i].kind == 'place' else 4))
              for i in range(len(mask))]
    reroll_id = next(i for i, a in enumerate(ACTIONS) if a.kind == 'reroll_start')
    if base[reroll_id] and best < -100:
        result = [False] * len(mask)
        result[reroll_id] = True
    return tuple(result if any(result) else base)


class FuelEnv(CrewEnv):
    actions, slots = FUEL_ACTIONS, FUEL_SLOTS

    def validate_scenario(self):
        if self.game.cockpit.module - {'kerosene'} or self.game.zusatz.karten:
            raise ValueError('Schema 2 unterstützt nur Grundspiel oder Kerosin ohne Fähigkeitskarten/Zusatzwürfel.')

    def view(self, role=None):
        view = super().view(role)
        c = self.game.cockpit
        view['fuel'] = {'present': 'kerosene' in c.module, 'remaining': c.kerosin or 0,
                        'occupied': not c.kerosin_feld.ist_frei()}
        return view

    def observation(self):
        return fuel_encode(self.view())

    def action_mask(self):
        mask = super().action_mask()
        if self.game and 'kerosene' not in self.game.cockpit.module:
            mask[len(ACTIONS):] = [False] * 4
        return mask

    def _assist(self, mask):
        if self.game and 'kerosene' not in self.game.cockpit.module:
            mask = mask[:len(ACTIONS)] + [False] * 4
        if not self.assistance_version or self.current_role not in self.assisted_roles:
            return mask
        self.validate_scenario()
        if self.assistance_version not in (3,4,5,6,7,8,9):
            raise ValueError('Unbekanntes Kerosin-Assistenzprofil.')
        return list(_fuel_assist(json.dumps(self.view(), sort_keys=True), tuple(mask), self.assistance_version))
