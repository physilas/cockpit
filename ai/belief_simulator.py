"""Rebuild an engine from a permitted view, never from a private game/save.

Hidden remaining partner dice currently use an IID uniform prior. This is an
explicit approximation after informative partner actions, not a SPARTA belief
posterior. Rollout policies still see only their own simulated hand.
"""
from copy import deepcopy

from backend.spielplan import Spielplan
from backend.wuerfel import Wuerfel
from .actions import ROLES, slot_field
from .modules import ModuleEnv, MODULE_SLOTS


class PlanningClock:
    """Planning assumption only; actual evaluation keeps the real engine clock."""
    def __init__(self):
        self.now = 0.

    def __call__(self):
        return self.now


class BeliefSimulator:
    def __init__(self, airport, view):
        self.airport = airport
        self.view = deepcopy(view)
        if 'modules_state' not in view:
            raise ValueError('The simulator requires a schema-3 permitted view.')

    def sample(self, seed):
        view = self.view
        modules = view['modules_state']
        clock = PlanningClock()
        env = ModuleEnv(self.airport, abilities=modules['cards'], assistance_version=0,
                        clock=clock, round_reward=0., sync_weight=0., task_weight=0.)
        env.rng.seed(seed)
        # Constructor randomness is isolated too (intern token initialization).
        with env._engine_randomness():
            game = Spielplan(self.airport, faehigkeitskarten=modules['cards'], clock=clock)
        env.game = game
        c, landing, z = game.cockpit, game.landung, game.zusatz
        if set(modules['modules']) != c.module or len(view['track']) != landing.get_laenge():
            raise ValueError('Public view and requested scenario disagree.')
        geometry = [(p['distance'], p['traffic'], p['min'], p['max']) for p in view['track']]
        expected = list(zip(landing.get_entfernungswerte(), landing.get_flugzeugwuerfel(),
                            landing.get_kurven_min(), landing.get_kurven_max()))
        if geometry != expected:
            raise ValueError('Public route geometry does not match the engine scenario.')
        game.aktuelle_runde = view['round']
        game.am_zug, game.startspieler = view['regular_turn'], view['round_starter']
        game.letzte_runde, game.warteschleife = view['last_round'], view['holding']
        game.phase, game._vorbereitete_runde = 'platzieren', view['round']
        game.neuwurf_plaettchen = view['reroll_tokens']
        game._genutzte_neuwurf_hoehen = {h for h in view['reroll_heights'] if h >= view['height']}
        landing.hoehe, landing.entfernung = view['height'], view['distance']
        landing.flugzeuge = [p['planes'] for p in view['track']]
        c.fluglage, c.kaffeetassen = view['attitude'], view['coffee']
        c.aerodynamik_blau, c.aerodynamik_orange = view['aero_blue'], view['aero_orange']
        c.fahrwerk_ausgefahren = list(view['gear'])
        c.landeklappen_ausgefahren = list(view['flaps'])
        c.bremsen_aktiviert = list(view['brake_progress'])
        c.kerosin = view['fuel']['remaining'] if c.module & {'kerosene', 'leak'} else None
        c.wind_position, c.eis_fortschritt = modules['wind_position'], modules['ice_progress']
        z.praktikant = list(modules['intern'])
        z.platzierungen = modules['placements']
        z.kooperation = deepcopy(modules['swap'])
        z.kooperation_genutzt = not modules['swap_available']
        z.anpassung = {r: not modules['adaptation'][r] for r in ROLES}
        # Once a placement occurred, anticipation cannot be used this round.
        z.voraussicht_genutzt = bool(z.platzierungen) or not modules['anticipation']
        # A nonstarter view does not say whether anticipation was used; before
        # the first placement the starter is necessarily the regular actor.
        if view['role'] != game.startspieler and not z.platzierungen:
            z.voraussicht_genutzt = False
        z.ausgeloest = {name for name, indices in (('ruder', (0, 1)), ('triebwerk', (2, 3)))
                         if all(view['board'][i] is not None for i in indices)}
        if modules['sync_triggered']:
            z.ausgeloest.add('synchronisation')
        z.deadline = max(0., modules['time_remaining'] - 1.) if 'realtime' in c.module else None
        board = (view['board'] + [({'value': 1, 'owner': 'pilot'} if view['fuel']['occupied'] else None)]
                 + modules['extra_fields'])
        for slot, field in zip(MODULE_SLOTS, board):
            if field is not None:
                die = Wuerfel(field['owner'])
                die.augenzahl, die.platziert = field['value'], True
                target = (c.training[slot.owner] if slot.target == 'training' else
                          c.eisbremsen[slot.index] if slot.target == 'eisbremse' else slot_field(game, slot))
                target.wuerfel = die
        pending = modules['pending']
        if pending:
            die = Wuerfel(pending['role'])
            die.augenzahl, die.quelle = pending['value'], pending['source']
            z.offen = [{'rolle': pending['role'], 'wuerfel': die}]
        env.reroll = deepcopy(view['reroll'])
        own, partner = view['role'], env.other_role(view['role'])
        for index, value in enumerate(view['own_dice']):
            die = game._wuerfel_liste(own)[index]
            die.augenzahl, die.platziert = value or 1, not bool(value)
        # Public selections constrain indices, never hidden faces.
        required = set()
        if env.reroll and env.reroll['selections'][partner] is not None:
            required.update(env.reroll['selections'][partner])
        if z.kooperation and z.kooperation['auswahl'][partner] is not None:
            required.add(z.kooperation['auswahl'][partner])
        if len(required) > view['partner_remaining']:
            raise ValueError('Public partner selections exceed remaining dice.')
        available = required | set([i for i in range(4) if i not in required][:view['partner_remaining']-len(required)])
        for index, die in enumerate(game._wuerfel_liste(partner)):
            die.augenzahl = env.rng.randint(1, 6) if index in available else 1
            die.platziert = index not in available
        env.steps = round(env.max_steps * (1 - view['steps_remaining']))
        env.validate_scenario()
        return env


def fork_simulation(env):
    """Preserve object aliases, simulated RNG and virtual clock per branch."""
    return deepcopy(env)


def simulation_step(env, action):
    env.clock.now += .05
    return env.step(action)
