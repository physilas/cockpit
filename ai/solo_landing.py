"""Engine-proven final-round continuations from own/public information only.

This is a deliberately narrow research solver, not a general world simulator.
The partner has no regular dice left. Unknown rolls, intern replacements and
real-time deadlines are outside scope. No running game or RNG enters this API.
Issued, already rolled synchronization dice are one shared resource. A future
unrolled bonus causes abstention on that branch, never a guessed extra die.
"""
from copy import deepcopy
from dataclasses import dataclass
import json
import time

from backend.spielplan import Spielplan
from backend.wuerfel import Wuerfel
from .actions import ROLES, slot_field
from .modules import MODULE_ACTIONS, MODULE_SLOTS, ModuleEnv
from .throttle import CpuBudget


def eligible(view):
    x = view.get('modules_state', {})
    pending = x.get('pending')
    known_bonus = bool(pending and pending['source'] == 'synchronisation'
                       and type(pending['value']) is int and 1 <= pending['value'] <= 6)
    return bool(view.get('last_round') and view.get('height') == 0 and view.get('distance') == 0
        and view.get('partner_remaining') == 0 and view.get('role') in ROLES
        and not view.get('reroll') and not x.get('swap')
        and set(x.get('modules', ())) <= {'wind', 'ice', 'kerosene', 'leak'}
        and (known_bonus or pending is None and view.get('regular_turn') == view['role'])
        and (any(view.get('own_dice', ())) or known_bonus))


def reconstruct(view, airport):
    """Create an independent current-round engine, never copy the live engine.

    Spent private dice get inert face1 placeholders, not inferred old faces.
    Public field tokens are separate objects: their old hand indices are not
    public and cannot matter for an action on a spent regular die. Fuel payment
    is public; an occupied fuel field needs only an inert occupied placeholder.
    Route metadata is checked against the public track, not used to add planes.
    """
    if not eligible(view):
        raise ValueError('Only supported final-round public states can be reconstructed.')
    x = view['modules_state']
    game = Spielplan(airport, startspieler=view['round_starter'], faehigkeitskarten=x['cards'])
    c, z, landing = game.cockpit, game.zusatz, game.landung
    static = list(zip(landing.get_entfernungswerte(), landing.get_flugzeugwuerfel(),
                      landing.get_kurven_min(), landing.get_kurven_max()))
    if (set(x['modules']) != c.module or static != [(r['distance'], r['traffic'], r['min'], r['max']) for r in view['track']]
            or set(landing.get_neuwurf_hoehen()) != set(view['reroll_heights'])):
        raise ValueError('Public route metadata and reconstruction route differ.')
    game.phase = 'platzieren'
    game.aktuelle_runde = game._vorbereitete_runde = view['round']
    game.am_zug = view['regular_turn']
    game.letzte_runde, game.warteschleife = True, view['holding']
    game.neuwurf_plaettchen = view['reroll_tokens']
    # At height0 every printed reroll height has already been visited. Search
    # never uses rerolls; this also preserves Mastery's token-cap calculation.
    game._genutzte_neuwurf_hoehen = set(view['reroll_heights'])
    landing.hoehe = landing.entfernung = 0
    landing.flugzeuge[:] = [r['planes'] for r in view['track']]
    for name, key in (('fahrwerk_ausgefahren','gear'), ('landeklappen_ausgefahren','flaps'),
                      ('bremsen_aktiviert','brake_progress')):
        getattr(c, name)[:] = view[key]
    c.fluglage, c.kaffeetassen = view['attitude'], view['coffee']
    c.aerodynamik_blau, c.aerodynamik_orange = view['aero_blue'], view['aero_orange']
    c.wind_position, c.eis_fortschritt = x['wind_position'], x['ice_progress']
    if c.kerosin is not None:
        c.kerosin = view['fuel']['remaining']
    for role in ROLES:
        for index, die in enumerate(game._wuerfel_liste(role)):
            face = view['own_dice'][index] if role == view['role'] else 0
            die.augenzahl, die.platziert = face or 1, not bool(face)
    fields = [slot_field(game, slot) for slot in MODULE_SLOTS[:21]]
    public = list(view['board']) + [dict(value=1,owner='pilot') if view['fuel']['occupied'] else None]
    fields += [*c.training.values(), *c.eisbremsen]
    public += x['extra_fields']
    for field, record in zip(fields, public):
        if record:
            token = Wuerfel(record['owner']); token.augenzahl = record['value']; token.platziert = True
            field.wuerfel = token
    z.platzierungen = x['placements']
    z.anpassung = {r: not x['adaptation'][r] for r in ROLES}
    z.voraussicht_genutzt = not x['anticipation']
    z.kooperation_genutzt = not x['swap_available']
    for target, indices in (('ruder',(0,1)), ('triebwerk',(2,3))):
        if all(view['board'][i] for i in indices):
            z.ausgeloest.add(target)  # Already paid/resolved, including wind and leak.
    if x['sync_triggered']:
        z.ausgeloest.add('synchronisation')
    if x['pending']:
        p = x['pending']; token = Wuerfel(p['role'])
        token.quelle, token.augenzahl = 'synchronisation', p['value']
        z.offen.append(dict(rolle=p['role'],wuerfel=token))
    env = ModuleEnv(airport, abilities=x['cards'], assistance_version=0, max_steps=512)
    env.game = game
    return env


@dataclass(frozen=True)
class Proof:
    actions: tuple = ()
    nodes: int = 0
    exhausted: bool = False
    unknown_roll: bool = False
    eligible: bool = False


def prove_landing(view, airport, *, allowed=None, max_nodes=1500, max_actions=32, cpu_duty_cycle=1.):
    """Return ONE actual winning sequence, or abstain. Failure is not a proof.

    Search includes every native legal placement and coffee/adaptation action,
    independent of the old strategic mask; the first action must also pass the
    supplied live mask. Cycles merge by public state. Fixed node/action limits
    control work; CPU pacing never changes candidate membership or ordering.
    """
    if type(max_nodes) is not int or not 1 <= max_nodes <= 10000 or type(max_actions) is not int or not 1 <= max_actions <= 64:
        raise ValueError('Use a finite positive node/action budget.')
    budget = CpuBudget(cpu_duty_cycle)
    if allowed is not None and (len(allowed) != len(MODULE_ACTIONS) or any(type(flag) is not bool for flag in allowed)):
        raise ValueError('The live action mask must contain217 booleans.')
    if not eligible(view):
        return Proof()
    env = reconstruct(view, airport)
    nodes, exhausted, unknown, last_pause = 0, False, False, time.perf_counter()
    visited = {}

    def walk(current, depth):
        nonlocal nodes, exhausted, unknown, last_pause
        if current.game.status == 'gewonnen':
            return ()
        if current.done or depth >= max_actions:
            return None
        pending = current.game.zusatz.offen
        if pending and pending[0]['wuerfel'].augenzahl is None:
            unknown = True
            return None
        state = current.view()
        state.pop('steps_remaining')
        key = json.dumps(state, sort_keys=True)
        if visited.get(key, max_actions + 1) <= depth:
            return None
        if nodes >= max_nodes:
            exhausted = True
            return None
        visited[key] = depth
        nodes += 1
        if time.perf_counter() - last_pause >= .02:
            budget.pause(); last_pause = time.perf_counter()
        legal = current.action_mask()
        candidates = [i for i, flag in enumerate(legal) if flag and MODULE_ACTIONS[i].kind in
                      ('place','coffee','adaptation','bonus_place','bonus_coffee') and (depth or allowed is None or allowed[i])]
        # Prefer mandatory tasks/controls, then other placements, then helpers.
        # Complete search still considers coffee before a placement when needed.
        def rank(i):
            a = MODULE_ACTIONS[i]
            if a.kind not in ('place','bonus_place'): return 2, i
            return (0 if MODULE_SLOTS[a.slot].target in ('ruder','triebwerk','eisbremse','fahrwerk','landeklappe','funk','kerosin','bremse') else 1), i
        for i in sorted(candidates, key=rank):
            if exhausted:
                break
            child = deepcopy(current)  # Only the already reconstructed, independent world.
            child.step(i)
            path = walk(child, depth + 1)
            if path is not None:
                return (i,) + path
        return None

    path = walk(env, 0)
    budget.pause()
    return Proof(path or (), nodes, exhausted, unknown, True)
