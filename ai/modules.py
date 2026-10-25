"""Research schema 3: all engine modules/cards, with an explicit privacy boundary.

This adapter exposes legal engine actions. It is not a claim of a qualified
policy; published players must pass every route/card case independently.
"""
import math
import random

from backend.landung import load_yaml
from backend.spielplan import Spielplan
from backend.wuerfel import Wuerfel
from .actions import ACTIONS, SLOTS, Action, Slot, ROLES, placement_is_legal, subset_indices
from .environment import CrewEnv
from .fuel import FUEL_ACTIONS, FUEL_SLOTS, FUEL_FEATURES, fuel_encode
from .observation import MAX_TRACK_LENGTH

MODULES=('kerosene','leak','wind','ice','intern','realtime')
CARDS=('working-together','synchronisation','mastery','control','anticipation','adaptation')
MODULE_SLOTS=FUEL_SLOTS+(Slot('training','pilot'),Slot('training','kopilot'))+tuple(
    Slot('eisbremse','pilot' if i%2==0 else None,i) for i in range(8))
MODULE_ACTIONS=FUEL_ACTIONS+tuple(Action('place',die=d,slot=s) for d in range(4) for s in range(21,len(MODULE_SLOTS)))+tuple(
    Action('bonus_place',slot=s) for s in range(len(MODULE_SLOTS)))+tuple(
    Action('bonus_coffee',delta=d) for d in (-3,-2,-1,1,2,3))+(Action('bonus_roll'),)+tuple(
    Action(kind,die=d) for kind in ('adaptation','anticipation') for d in range(4))+(Action('swap_start'),)+tuple(
    Action('swap_choose',die=d) for d in range(4))+(Action('swap_cancel'),)
MODULE_FEATURES=FUEL_FEATURES+[f'module.{m}' for m in MODULES]+[f'card.{c}' for c in CARDS]+[
    f'wind.position.{i}' for i in range(18)]+['wind.value','ice.progress']+[
    f'intern.{i}.{face}' for i in range(6) for face in range(7)]+[
    f'extra_field.{i}.{key}' for i in range(10) for key in ('occupied','value','pilot','kopilot')]+[
    'pending.present','pending.pilot','pending.kopilot','pending.synchronisation','pending.intern','pending.rolled','pending.value',
    'sync.triggered','swap.active','swap.wait.pilot','swap.wait.kopilot','swap.available',
    'adaptation.pilot','adaptation.kopilot','anticipation.available','placements','realtime.remaining']+[
    f'swap.{r}.{name}' for r in ROLES for name in ('selected','index','confirmed')]


def module_schema():
    from dataclasses import asdict
    return {'version':3,'features':MODULE_FEATURES,'actions':[asdict(a) for a in MODULE_ACTIONS],
            'slots':[asdict(s) for s in MODULE_SLOTS]}


def module_encode(view):
    x=view['modules_state']
    result=fuel_encode(view)+[float(m in x['modules']) for m in MODULES]+[float(c in x['cards']) for c in CARDS]
    result += [float(i==x['wind_position']) for i in range(18)]+[x['wind_value']/3,x['ice_progress']/4]
    result += [float((x['intern'][i] if i<len(x['intern']) else 0)==face) for i in range(6) for face in range(7)]
    for field in x['extra_fields']:
        result += [float(field is not None),field['value']/6 if field else 0,
                   float(field is not None and field['owner']=='pilot'),float(field is not None and field['owner']=='kopilot')]
    pending=x['pending'];swap=x['swap']
    result += [float(pending is not None),float(bool(pending and pending['role']=='pilot')),
               float(bool(pending and pending['role']=='kopilot')),
               float(bool(pending and pending['source']=='synchronisation')),float(bool(pending and pending['source']=='intern')),
               float(bool(pending and pending['value'] is not None)),pending['value']/6 if pending and pending['value'] is not None else 0,
               float(x['sync_triggered']),float(swap is not None),float(bool(swap and swap['wartet_auf']=='pilot')),
               float(bool(swap and swap['wartet_auf']=='kopilot')),float(x['swap_available']),
               float(x['adaptation']['pilot']),float(x['adaptation']['kopilot']),float(x['anticipation']),
               x['placements']/16,x['time_remaining']/60]
    for role in ROLES:
        chosen=swap['auswahl'][role] if swap else None
        result += [float(chosen is not None),(chosen+1)/4 if chosen is not None else 0,
                   float(bool(swap and swap['bestaetigt'][role]))]
    if len(result)!=len(MODULE_FEATURES):raise RuntimeError('Module feature schema drift.')
    return result


def shared_capacity(view):
    """Count an issued synchronization die ONCE, separate from private hands."""
    pending=view['modules_state']['pending']
    counts={view['role']:sum(bool(d) for d in view['own_dice']),
            CrewEnv.other_role(view['role']):view['partner_remaining']}
    shared=int(bool(pending and pending['source']=='synchronisation'))
    if pending and pending['source']=='intern':counts[pending['role']]+=1
    return {'regular_and_intern':counts,'shared_bonus':shared,'total':sum(counts.values())+shared}


def _target(slot,targets):
    return next((t for t in targets if t['ziel']==slot.target and t['index']==slot.index and t['funk_feld']==slot.radio_index
                 and (slot.owner is None or t['ziel_besitzer']==slot.owner)),None)


class ModuleEnv(CrewEnv):
    actions,slots=MODULE_ACTIONS,MODULE_SLOTS

    def __init__(self,*args,abilities=None,curriculum_cases=(),clock=None,**kwargs):
        super().__init__(*args,**kwargs)
        self.abilities=None if abilities is None else tuple(abilities)
        self.curriculum_cases=tuple(curriculum_cases)
        self.clock=clock

    def validate_scenario(self):
        if self.game.cockpit.module-set(MODULES) or set(self.game.zusatz.karten)-set(CARDS):
            raise ValueError('Unregistered module/card.')

    def reset(self,*,seed=None):
        if seed is not None:self.rng.seed(seed)
        self.reroll,self.steps,self.truncated=None,0,False
        self.blocked=False;self.rounds_resolved=0;self.task_urgency=0
        self.reward_components={k:0. for k in ('outcome','round','sync','tasks')}
        self.reward_totals=self.reward_components.copy();self._reset_diagnostics()
        with self._engine_randomness():
            case=random.choice(self.curriculum_cases) if self.curriculum_cases else None
            airport=case['airport'] if case else random.choice(self.curriculum_airports) if self.curriculum_airports else self.airport
            abilities=case['abilities'] if case else self.abilities
            if abilities is None:abilities=CARDS[:(load_yaml(airport).get('faehigkeitskarten') or 0)]
            self.game=Spielplan(airport,faehigkeitskarten=list(abilities),clock=self.clock)
            self.validate_scenario()
            if self.game.landung.get_laenge()>MAX_TRACK_LENGTH:raise ValueError('Route too long.')
            self.game.starte_spiel();self._advance()
        return self.observation(),self.info()

    @property
    def current_role(self):
        if self.game.zusatz.offen:return self.game.zusatz.offen[0]['rolle']
        if self.game.zusatz.kooperation:return self.game.zusatz.kooperation['wartet_auf']
        return super().current_role

    def _advance(self):
        if self.game.zusatz.offen or self.game.zusatz.kooperation:return False
        return super()._advance()

    def view(self,role=None):
        view=super().view(role)
        c,z=self.game.cockpit,self.game.zusatz
        snapshot=z.snapshot()
        fields=[*c.training.values(),*c.eisbremsen]
        view['fuel']={'present':'kerosene' in c.module and 'leak' not in c.module,
                      'remaining':c.kerosin or 0,'occupied':not c.kerosin_feld.ist_frei()}
        pending=z.offen[0] if z.offen else None
        view['modules_state']={'modules':sorted(c.module),'cards':list(z.karten),
            'wind_position':c.wind_position,'wind_value':c.wind_wert(),'ice_progress':c.eis_fortschritt,
            'intern':list(z.praktikant),'extra_fields':[None if f.ist_frei() else {'value':f.wuerfel.augenzahl,'owner':f.wuerfel.besitzer} for f in fields],
            'pending':{'role':pending['rolle'],'source':pending['wuerfel'].quelle,'value':pending['wuerfel'].augenzahl} if pending else None,
            'sync_triggered':'synchronisation' in z.ausgeloest,'swap':snapshot['kooperation'],
            'swap_available':snapshot['kooperation_verfuegbar'],'adaptation':snapshot['anpassung_verfuegbar'],
            'anticipation':snapshot['voraussicht_verfuegbar'] and view['role']==self.game.startspieler,
            'placements':z.platzierungen,
            'time_remaining':max(0,min(60,math.ceil(z.deadline-z.clock()))) if z.deadline is not None else 0}
        return view

    def observation(self):return module_encode(self.view())

    def unfinished_tasks(self):
        tasks=super().unfinished_tasks()
        c=self.game.cockpit
        tasks.update(ice=4-c.eis_fortschritt if 'ice' in c.module else 0,
                     intern=len(self.game.zusatz.praktikant))
        return tasks

    def action_mask(self):
        mask=[False]*len(self.actions)
        if self.done:return mask
        role=self.current_role;c=self.game.cockpit;z=self.game.zusatz
        dice=self.game._wuerfel_liste(role)
        if z.offen:
            pending=z.offen[0];die=pending['wuerfel'];targets=z.platzierziele()
            for i,a in enumerate(self.actions):
                if a.kind=='bonus_roll':mask[i]=die.quelle=='synchronisation' and die.augenzahl is None
                elif a.kind=='bonus_coffee':mask[i]=die.quelle=='synchronisation' and die.augenzahl is not None and a.delta in c.moegliche_kaffee_deltas(die.augenzahl)
                elif a.kind=='bonus_place':mask[i]=_target(self.slots[a.slot],targets) is not None
        elif z.kooperation:
            for i,a in enumerate(self.actions):
                if a.kind=='swap_choose':mask[i]=not z.kooperation['bestaetigt'][role] and dice[a.die].ist_verfuegbar()
                elif a.kind=='swap_cancel':mask[i]=True
        elif self.reroll:
            other=self.reroll['selections'][self.other_role(role)]
            for i,a in enumerate(self.actions):
                if a.kind=='reroll_select':
                    selected=subset_indices(a.subset)
                    nonempty=bool(selected or other) or other is None and bool(self.game.verfuegbare_wuerfel(self.other_role(role)))
                    mask[i]=nonempty and all(dice[j].ist_verfuegbar() for j in selected)
        else:
            for i,a in enumerate(self.actions):
                if a.kind=='place':
                    slot=self.slots[a.slot];die=dice[a.die]
                    if not die.ist_verfuegbar() or slot.owner is not None and slot.owner!=role:continue
                    if slot.target=='training':
                        if 'intern' in c.module and z.praktikant and c.training[role].ist_frei():
                            value=z.praktikant[0 if role=='pilot' else -1]
                            token=Wuerfel(role);token.augenzahl=value;token.quelle='intern'
                            mask[i]=value!=die.augenzahl and bool(z.platzierziele({'rolle':role,'wuerfel':token}))
                    elif slot.target=='eisbremse':
                        f=c.eisbremsen[slot.index]
                        mask[i]='ice' in c.module and slot.index//2==c.eis_fortschritt and f.ist_frei() and f.erlaubt(role,die.augenzahl)
                    elif slot.target=='kerosin':
                        mask[i]='kerosene' in c.module and 'leak' not in c.module and c.kerosin_feld.ist_frei()
                    elif slot.target!='bremse' or 'ice' not in c.module:
                        mask[i]=placement_is_legal(self.game,role,die,slot)
                elif a.kind=='coffee':mask[i]=dice[a.die].ist_verfuegbar() and a.delta in self.game.moegliche_kaffee_deltas(role,a.die)
                elif a.kind=='reroll_start':mask[i]=self.game.neuwurf_plaettchen>0 and any(w.ist_verfuegbar() for w in dice)
                elif a.kind=='adaptation':mask[i]='adaptation' in z.karten and not z.anpassung[role] and dice[a.die].ist_verfuegbar()
                elif a.kind=='anticipation':mask[i]='anticipation' in z.karten and not z.voraussicht_genutzt and not z.platzierungen and role==self.game.startspieler and dice[a.die].ist_verfuegbar()
                elif a.kind=='swap_start':mask[i]='working-together' in z.karten and not z.kooperation_genutzt and all(self.game.verfuegbare_wuerfel(r) for r in ROLES)
        return self._assist(mask)

    def _assist(self,mask):
        if not self.assistance_version or self.current_role not in self.assisted_roles:return mask
        if self.game.cockpit.module <= {'kerosene'} and not self.game.zusatz.karten and self.assistance_version in (3,4,5,6,7,8,9):
            # Exact compatibility for the first PPO curriculum stage. Other
            # modules already expose legal actions but need their own planner.
            import json
            from .fuel import _fuel_assist
            prefix=list(mask[:125])
            own=sum(bool(v) for v in self.view()['own_dice'])
            missing=sum(s.owner==self.current_role and s.target in ('ruder','triebwerk') and self.view()['board'][i] is None for i,s in enumerate(SLOTS))
            if own<=missing:
                for i,a in enumerate(FUEL_ACTIONS):
                    if a.kind=='place' and self.slots[a.slot].target not in ('ruder','triebwerk'):prefix[i]=False
            serialized=json.dumps(self.view(),sort_keys=True)
            if self.assistance_version==9:
                self._reference_mask=list(_fuel_assist(serialized,tuple(prefix),7))+[False]*(len(mask)-125)
            return list(_fuel_assist(serialized,tuple(prefix),self.assistance_version))+[False]*(len(mask)-125)
        raise ValueError('This research planner stage supports only base game/kerosene without cards.')

    def info(self):
        result=super().info()
        if self.assistance_version==9:
            # Pure public/own-hand advice, not another legality constraint.
            result['reference_action_mask']=(list(self._reference_mask)
                if any(result['action_mask']) and self.current_role in self.assisted_roles
                else list(result['action_mask']))
        return result

    def _special(self,action,role):
        z=self.game.zusatz
        if action.kind=='bonus_roll':return z.aktion(role,'synchronisation_wuerfeln',{})
        if action.kind=='bonus_coffee':return z.aktion(role,'bonus_kaffee',{'delta':action.delta})
        if action.kind=='bonus_place':return z.aktion(role,'zusatz_platzieren',_target(self.slots[action.slot],z.platzierziele()) or {})
        if action.kind=='swap_start':return z.aktion(role,'kooperation_start',{})
        if action.kind=='swap_cancel':return z.aktion(role,'kooperation_abbrechen',{})
        if action.kind=='swap_choose':
            answer=z.aktion(role,'kooperation_wahl',{'wuerfel_index':action.die})
            return z.aktion(role,'kooperation_bestaetigen',{}) if answer.erfolg else answer
        return z.aktion(role,action.kind,{'wuerfel_index':action.die})

    def step(self,action_id):
        if self.game and self.game.status=='laeuft' and self.game.zusatz.deadline is not None and self.game.zusatz.clock()>=self.game.zusatz.deadline:
            old_round=self.game.aktuelle_runde
            with self._engine_randomness():
                self.game.zusatz.tick()
                resolved=self._advance()
            self.steps+=1
            return self._finish_special(old_round,resolved)
        if type(action_id) is not int or not 0<=action_id<len(self.actions) or not self.action_mask()[action_id]:raise ValueError('Illegal module action.')
        action=self.actions[action_id]
        if action.kind in ('place','coffee','reroll_start','reroll_select'):return super().step(action_id)
        role=self.current_role;old_round=self.game.aktuelle_runde
        self._last_action=(role,action)
        with self._engine_randomness():
            result=self._special(action,role)
            if not result.erfolg:raise RuntimeError(f'Mask/engine mismatch: {result.grund}')
            resolved=self._advance()
        self.steps+=1
        self.diagnostics['special_actions']=self.diagnostics.get('special_actions',0)+1
        return self._finish_special(old_round,resolved)

    def _finish_special(self,old_round,resolved):
        if self.game.status=='laeuft' and not any(self.action_mask()):self.blocked=True
        terminated=self.game.status!='laeuft' or self.blocked
        self.truncated=self.steps>=self.max_steps and not terminated
        self.reward_components={'outcome':(1. if self.game.status=='gewonnen' else -1.) if terminated else 0.,
            'round':self.round_reward*(self.game.aktuelle_runde-old_round),
            'sync':-self.sync_weight*self.sync_error() if resolved else 0.,
            'tasks':self._task_penalty(resolved,terminated)}
        for k,v in self.reward_components.items():self.reward_totals[k]+=v
        return self.observation(),sum(self.reward_components.values()),terminated,self.truncated,self.info()
