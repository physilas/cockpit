"""Local JSON saves with explicit engine types; never pickle or executable data.

This contains private dice/RNG for resuming the local engine. It must never be
included in AI observations or uploaded learning records.
"""
import json
import math
import time
from .spielplan import Spielplan
from .cockpit import Cockpit, Ergebnis
from .landung import Landung
from .wuerfel import Wuerfel
from .wuerfelfeld import Wuerfelfeld
from .zusatzregeln import Zusatzregeln

TYPES = {c.__name__: c for c in (Spielplan, Cockpit, Ergebnis, Landung, Wuerfel, Wuerfelfeld, Zusatzregeln)}


def dump_game(game, history, rng):
    nodes, seen = [], {}
    saved_at = time.time()

    def encode(value, depth=0):
        if depth > 80:
            raise ValueError('Spielstand zu tief verschachtelt.')
        if value is None or type(value) in (bool, int, str):
            return value
        if type(value) is float:
            if not math.isfinite(value): raise ValueError('Ungültige Zahl.')
            return value
        if value is time.time:
            return {'clock': True}
        if type(value) in (list, tuple, set):
            return {'container': type(value).__name__, 'items': [encode(v, depth+1) for v in value]}
        if type(value) is dict:
            if any(type(k) not in (str, int) for k in value): raise ValueError('Ungültiger Schlüssel.')
            return {'container': 'dict', 'items': [[k, encode(v, depth+1)] for k,v in value.items()]}
        name = type(value).__name__
        if TYPES.get(name) is not type(value): raise ValueError('Unbekannter Spielstandtyp.')
        key = id(value)
        if key not in seen:
            seen[key] = len(nodes); nodes.append(None)
            nodes[seen[key]] = {'type': name, 'attrs': {k: encode(v, depth+1) for k,v in vars(value).items()}}
        return {'ref': seen[key]}

    root = encode([game, list(history)[-8:], rng])
    return json.dumps({'format': 1, 'saved_at': saved_at, 'root': root, 'nodes': nodes}, separators=(',', ':'))


def load_game(raw):
    if not isinstance(raw, str) or len(raw) > 5_000_000: raise ValueError('Ungültiger Spielstand.')
    data = json.loads(raw)
    if data.get('format') != 1 or not isinstance(data.get('nodes'), list) or len(data['nodes']) > 5000:
        raise ValueError('Unbekannter Spielstand.')
    saved_at = data.get('saved_at')
    if type(saved_at) not in (int, float) or not math.isfinite(saved_at): raise ValueError('Ungültige Speicherzeit.')
    nodes = data['nodes']
    objects = []
    for node in nodes:
        if not isinstance(node, dict) or node.get('type') not in TYPES or not isinstance(node.get('attrs'), dict):
            raise ValueError('Unbekannter Spielstandtyp.')
        if any(not isinstance(k,str) or k.startswith('__') for k in node['attrs']): raise ValueError('Ungültiges Attribut.')
        objects.append(TYPES[node['type']].__new__(TYPES[node['type']]))

    def decode(value, depth=0):
        if depth > 80: raise ValueError('Spielstand zu tief verschachtelt.')
        if value is None or type(value) in (bool, int, str): return value
        if type(value) is float and math.isfinite(value): return value
        if not isinstance(value, dict): raise ValueError('Ungültiger Spielstandwert.')
        if value == {'clock': True}: return time.time
        if set(value) == {'ref'}:
            i=value['ref']
            if type(i) is not int or not 0<=i<len(objects): raise ValueError('Ungültiger Verweis.')
            return objects[i]
        if set(value) != {'container','items'} or not isinstance(value['items'],list) or len(value['items'])>10000:
            raise ValueError('Ungültiger Container.')
        kind, items = value['container'], value['items']
        if kind == 'dict':
            if any(not isinstance(p,list) or len(p)!=2 or type(p[0]) not in (str,int) for p in items): raise ValueError('Ungültiges Wörterbuch.')
            return {k:decode(v,depth+1) for k,v in items}
        if kind not in ('list','tuple','set'): raise ValueError('Unbekannter Container.')
        return {'list':list,'tuple':tuple,'set':set}[kind](decode(v,depth+1) for v in items)

    for node,obj in zip(nodes,objects):
        obj.__dict__.update({k:decode(v) for k,v in node['attrs'].items()})
    game, history, rng = decode(data['root'])
    if type(game) is not Spielplan or any(type(g) is not Spielplan for g in history): raise ValueError('Kein Spielstand.')
    offset = time.time()-saved_at
    for obj in objects:
        if type(obj) is Zusatzregeln:
            obj.clock = time.time
            if obj.deadline is not None: obj.deadline += offset
    if game.cockpit.landung is not game.landung or game.zusatz.spiel is not game or game.zusatz.c is not game.cockpit:
        raise ValueError('Beschädigte Spielverweise.')
    if game.status not in ('laeuft','gewonnen','verloren') or game.am_zug not in ('pilot','kopilot'):
        raise ValueError('Ungültige Partie.')
    game.zustand()
    return game, history, rng
