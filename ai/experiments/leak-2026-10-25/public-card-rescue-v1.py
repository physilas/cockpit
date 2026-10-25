"""Deterministic public profile-11 counterexample; no NN or game-win claim.

Run from the repository root with:
  .venv/bin/python ai/experiments/leak-2026-10-25/public-card-rescue-v1.py

The fixture supplies all chosen faces explicitly. The planner receives only
the acting hand and public board/counts. It never sees unused partner faces.
No qualification seed, checkpoint or future game RNG is used for evaluation.
"""
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from ai.actions import Action
from ai.modules import MODULE_ACTIONS, ModuleEnv


def run():
    env = ModuleEnv('LOG_ATL_YELLOW', abilities=['adaptation'],
                    assistance_version=11, clock=lambda: 0.)
    env.reset(seed='train:public-leak-audit:adaptation-rescue')
    game = env.game
    # Explicit technical preconditions, not a sampled successful game.
    game.landung.flugzeuge[:] = [0] * len(game.landung.flugzeuge)
    game.neuwurf_plaettchen = 0
    for role in ('pilot', 'kopilot'):
        for die in game._wuerfel_liste(role):
            die.augenzahl = 1
    sequence = [
        ('pilot', 1, 'triebwerk', None, 3),
        ('kopilot', 0, 'ruder', None, 4),
        ('pilot', 2, 'funk', None, 1),
        ('kopilot', 1, 'triebwerk', None, 3),
        ('pilot', 3, 'fahrwerk', 0, 1),
        ('kopilot', 2, 'landeklappe', 0, 1),
    ]
    public_moves = []
    for role, die, target, index, face in sequence:
        game._wuerfel_liste(role)[die].augenzahl = face
        result = game.platziere(role, die, target, index)
        assert result.erfolg and not result.verloren, (role, target, result)
        public_moves.append(dict(role=role, die=die, target=target,
                                 index=index, published_face=face))
    view = env.view()
    info = env.info()
    rudder_id = MODULE_ACTIONS.index(Action('place', die=0, slot=0))
    flip_id = MODULE_ACTIONS.index(Action('adaptation', die=0))
    assert view['role'] == 'pilot' and view['own_dice'] == [1, 0, 0, 0]
    assert view['board'][1]['value'] == 4 and view['attitude'] == 0
    assert view['coffee'] == 0 and view['fuel']['remaining'] == 19
    assert info['action_mask'][rudder_id] and info['action_mask'][flip_id]
    assert info['reference_action_mask'][rudder_id]
    assert not info['reference_action_mask'][flip_id]
    assert sum(info['reference_action_mask']) == 1

    direct = deepcopy(game)
    bad = direct.platziere('pilot', 0, 'ruder')
    rescued = deepcopy(game)
    flip = rescued.zusatz.aktion('pilot', 'adaptation', {'wuerfel_index': 0})
    safe = rescued.platziere('pilot', 0, 'ruder')
    assert bad.verloren and bad.grund == 'trudeln'
    assert flip.erfolg and safe.erfolg and not safe.verloren
    assert rescued.cockpit.fluglage == -2

    def choices(mask):
        return [dict(id=i, action=asdict(action))
                for i, (action, allowed) in enumerate(zip(MODULE_ACTIONS, mask))
                if allowed]

    sources = ('ai/leak_advice.py', 'ai/tactics.py', 'ai/module_physics.py',
               'ai/modules.py', 'ai/module_guidance.py', 'ai/module_capacity.py',
               'backend/cockpit.py', 'backend/spielplan.py', 'backend/zusatzregeln.py')
    return {
        'complete': True,
        'kind': 'deterministic_public_engine_counterexample',
        'release_evidence': False,
        'nn_policy_evaluated': False,
        'claim': ('Profile 11 recommends a placement that immediately stalls, '
                  'while legal adaptation followed by that placement avoids '
                  'the immediate stall. This proves neither a win nor actual '
                  'NN preference for the failing move.'),
        'reproduce': '.venv/bin/python ai/experiments/leak-2026-10-25/public-card-rescue-v1.py',
        'source_sha256': {name: sha256((ROOT / name).read_bytes()).hexdigest()
                          for name in sources},
        'fixture': {'airport': 'LOG_ATL_YELLOW', 'abilities': ['adaptation'],
                    'assistance_version': 11, 'all_traffic_cleared': True,
                    'reroll_tokens': 0,
                    'initial_explicit_faces': {'pilot': [1, 1, 1, 1]},
                    'unused_partner_faces_consumed_by_planner': False},
        'public_placement_sequence': public_moves,
        'own_hand_and_public_decision_view': view,
        'allowed_actions': choices(info['action_mask']),
        'reference_actions': choices(info['reference_action_mask']),
        'direct_rudder': {'success': bad.erfolg, 'lost': bad.verloren,
                          'reason': bad.grund, 'attitude': direct.cockpit.fluglage},
        'adaptation_then_rudder': {
            'adaptation_success': flip.erfolg,
            'published_face': rescued.pilot_wuerfel[0].augenzahl,
            'placement_success': safe.erfolg, 'lost': safe.verloren,
            'reason': safe.grund, 'attitude': rescued.cockpit.fluglage,
            'game_status': rescued.status,
        },
    }


if __name__ == '__main__':
    result = run()
    output = Path(__file__).with_name('public-card-rescue-v1.json')
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print('Verified public adaptation rescue; wrote', output.relative_to(ROOT))
