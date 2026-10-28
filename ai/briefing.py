"""Public pre-roll goals. No dice faces or language-model download required."""
import json
import hashlib
from functools import lru_cache
from pathlib import Path
from backend import bridge

PUBLIC_KEYS = ('szenario_id', 'runde', 'hoehe', 'entfernung', 'letzte_runde', 'warteschleife',
               'module', 'faehigkeitskarten', 'flugzeuge', 'laenge', 'kerosin', 'kaffeetassen',
               'fahrwerk_ausgefahren', 'landeklappen_ausgefahren', 'bremsen_aktiviert',
               'eis_fortschritt', 'wind_position', 'wind_wert', 'fluglage')


@lru_cache(maxsize=1)
def policy_fingerprint():
    root=Path(__file__).resolve().parents[1]
    digest=hashlib.sha256(b'briefing-v1')
    for name in ('ai/briefing.py','ai/briefing_browser.py','ai/briefing_planner.py','play_options.py'):
        digest.update(name.encode());digest.update((root/name).read_bytes())
    return digest.hexdigest()


def proposals(state):
    public = {key: state[key] for key in PUBLIC_KEYS}
    distance, rounds = state['entfernung'], max(1, state['hoehe']//1000)
    stationary = state['letzte_runde'] or state['warteschleife'] or distance == 0
    traffic = state['flugzeuge'][state['laenge']-1-distance] if 0 <= distance < state['laenge'] else 0
    movement = 0 if stationary or traffic > 3 else min(2, (distance+rounds-1)//rounds)
    if movement == 2 and distance >= 1:
        next_index=state['laenge']-distance
        if traffic+state['flugzeuge'][next_index] > 3:movement=1
    def choice(value, label, reason):
        return dict(value=value, label=label, reason=reason)
    movements = [choice(i, 'Stehen bleiben' if i == 0 else f'{i} Feld' + ('er' if i != 1 else '') + ' weiter',
        'Zeit für die Aufgaben und den Verkehr gewinnen.' if i == 0 else 'Reststrecke und verbleibende Runden aufeinander abstimmen.')
        for i in range(1 if stationary else min(2,distance)+1)]
    tasks = (3-sum(state['fahrwerk_ausgefahren'])) + (4-sum(state['landeklappen_ausgefahren']))
    focus = [choice('radio', 'Flugzeuge entfernen', 'Den Flugweg rechtzeitig freifunken.'),
             choice('tasks', 'Fahrwerk & Klappen', f'Noch {tasks} Aufgaben an Fahrwerk und Landeklappen sind offen.'),
             choice('coffee', 'Kaffee ansparen', 'Eine Reserve für ungünstige Würfel aufbauen.')]
    modules, cards = state['module'], state['faehigkeitskarten']
    if state['kerosin'] is not None:
        focus.append(choice('fuel', 'Kerosin schonen', 'Den Verbrauch und die verbleibenden Runden im Blick behalten.'))
    coordination = [choice('level', 'Waagerechte Fluglage', 'Gemeinsam auf eine ausgeglichene Fluglage hinarbeiten.'),
                    choice('brakes', 'Bremsen vorbereiten', 'Die Bremsen für die Landung rechtzeitig erledigen.')]
    if 'synchronisation' in cards:
        coordination.insert(0, choice('synchronisation', 'Synchronisation anstreben', 'Fahrwerk und Klappen möglichst in derselben Runde erledigen.'))
    if 'wind' in modules:
        coordination.insert(0, choice('wind', 'Wind für die Landung planen', 'Auch die nächsten Drehungen des Windrads berücksichtigen.'))
    chosen_focus = 'radio' if traffic else 'tasks' if tasks else 'coffee'
    if state['kerosin'] is not None and state['kerosin'] <= rounds+5:
        chosen_focus = 'fuel'
    preferred = 'synchronisation' if 'synchronisation' in cards and tasks else 'wind' if 'wind' in modules else 'brakes' if not all(state['bremsen_aktiviert']) else 'level'
    return dict(version=1, round=state['runde'], public_state=public, goals=[
        dict(key='movement_preference', title='Flugweite', options=movements, selected=movement),
        dict(key='focus', title='Schwerpunkt', options=focus, selected=chosen_focus),
        dict(key='coordination', title='Zusammenspiel', options=coordination, selected=preferred)])


def validate_plan(value, state):
    if not isinstance(value, dict) or set(value) != {'version','round','movement_preference','focus','coordination'}:
        raise ValueError('Ungültiger Rundenplan.')
    if type(value['version']) is not int or value['version'] != 1 or type(value['round']) is not int or value['round'] != state['runde']:
        raise ValueError('Dieser Plan gehört nicht zur aktuellen Runde.')
    for goal in proposals(state)['goals']:
        selected = value[goal['key']]
        if not any(type(selected) is type(option['value']) and selected == option['value'] for option in goal['options']):
            raise ValueError('Dieses Ziel ist hier nicht verfügbar.')
    return dict(value)


def suggest():
    game = bridge._spiel
    if game is None or game.status != 'laeuft' or game.phase != 'vorbereitung':
        raise ValueError('Eine Absprache ist nur vor dem Würfeln möglich.')
    if any(w.augenzahl is not None for w in game.pilot_wuerfel + game.kopilot_wuerfel):
        raise ValueError('Die Würfel wurden bereits geworfen.')
    return {**proposals(game.zustand()),"policy_sha256":policy_fingerprint()}


def start_round(plan_json='null'):
    suggest()  # Validate the phase before parsing or consuming any RNG.
    value = json.loads(plan_json)
    if value is not None:
        validate_plan(value, bridge.zustand())
    return bridge.wuerfeln_fuer_runde()
