"""Research adapter: exact rules for all cases, issued shared dice and privacy."""
from copy import deepcopy
import itertools
import json
from pathlib import Path
import unittest

from backend.katalog import landekatalog
from backend.zusatzregeln import KARTEN
from ai.actions import execute_placement
from ai.modules import ModuleEnv,MODULE_ACTIONS,MODULE_FEATURES,shared_capacity

ROOT=Path(__file__).resolve().parents[1]
MATRIX=json.loads((ROOT/'ai/experiments/modules-50pct-2026-10-25/matrix.json').read_text())


def fixture(cards=()):
    case=next(c for c in MATRIX['cases'] if set(c['abilities'])==set(cards))
    env=ModuleEnv(case['airport'],abilities=case['abilities'],clock=lambda:0)
    env.reset(seed=43)
    return env


def choose(env,kind,**fields):
    return next(i for i,a in enumerate(MODULE_ACTIONS) if a.kind==kind and all(getattr(a,k)==v for k,v in fields.items()) and env.action_mask()[i])


class ModuleAdapterTests(unittest.TestCase):
    def test_all_186_cases_and_legal_engine_placements(self):
        expected={(s['engine_code'],tuple(c)) for s in landekatalog()['scenarios'] if s['kind']=='logbook'
                  for c in itertools.combinations(sorted(KARTEN),s['ability_count'])}
        self.assertEqual(expected,{(c['airport'],tuple(c['abilities'])) for c in MATRIX['cases']})
        self.assertEqual(len(expected),186)
        for case in MATRIX['cases']:
            env=ModuleEnv(case['airport'],abilities=case['abilities'],clock=lambda:0)
            obs,info=env.reset(seed=45)
            self.assertEqual(len(obs),len(MODULE_FEATURES))
            mask=info['action_mask']
            role=env.current_role
            for i,a in enumerate(MODULE_ACTIONS):
                if a.kind!='place':continue
                clone=deepcopy(env.game)
                answer=execute_placement(clone,role,a,env.slots)
                self.assertEqual(mask[i],answer.erfolg,(case,i,answer.grund))
            before=(deepcopy(env.view()),env.observation(),env.action_mask())
            for die in env.game._wuerfel_liste(env.other_role(role)):
                die.augenzahl=7-die.augenzahl
            self.assertEqual(before,(env.view(),env.observation(),env.action_mask()))

    def test_first_curriculum_preserves_the_fuel_player(self):
        from ai.fuel import FuelEnv
        for airport in ('LOG_OSL_GREEN','MUC'):
            fuel=FuelEnv(airport,assistance_version=7);fuel.reset(seed=46)
            module=ModuleEnv(airport,assistance_version=7);module.reset(seed=46)
            self.assertEqual(fuel.observation(),module.observation()[:352])
            self.assertEqual(fuel.action_mask(),module.action_mask()[:125])
            self.assertFalse(any(module.action_mask()[125:]))

    def test_synchronisation_is_one_shared_die_with_both_colours(self):
        env=fixture(['synchronisation'])
        env.game.am_zug='pilot';env.game.pilot_wuerfel[0].augenzahl=1
        env.step(choose(env,'place',die=0,slot=7))
        env.game.kopilot_wuerfel[0].augenzahl=1
        env.step(choose(env,'place',die=0,slot=10))
        capacity=shared_capacity(env.view())
        self.assertEqual(capacity['shared_bonus'],1)
        self.assertEqual(capacity['total'],7)
        env.step(choose(env,'bonus_roll'))
        self.assertIn(env.view()['modules_state']['pending']['value'],(2,3,4,5))
        mask=env.action_mask()
        targets=[env.slots[a.slot].owner for i,a in enumerate(MODULE_ACTIONS) if mask[i] and a.kind=='bonus_place']
        self.assertIn('pilot',targets);self.assertIn('kopilot',targets)
        for i,a in enumerate(MODULE_ACTIONS):
            if a.kind!='bonus_place':continue
            cloned=ModuleEnv();cloned.game=deepcopy(env.game)
            answer=cloned._special(a,cloned.current_role)
            self.assertEqual(mask[i],answer.erfolg)
        env.step(choose(env,'bonus_place'))
        self.assertEqual(shared_capacity(env.view())['shared_bonus'],0)

    def test_adaptation_and_confirmed_swap(self):
        env=fixture(['adaptation'])
        role=env.current_role;face=env.view()['own_dice'][0]
        env.step(choose(env,'adaptation',die=0))
        self.assertEqual(env.view()['own_dice'][0],7-face)
        self.assertFalse(any(ok and a.kind=='adaptation' for ok,a in zip(env.action_mask(),MODULE_ACTIONS)))
        env=fixture(['working-together'])
        before={r:env.game._wuerfel_liste(r)[0].augenzahl for r in ('pilot','kopilot')}
        env.step(choose(env,'swap_start'))
        env.step(choose(env,'swap_choose',die=0))
        self.assertEqual(env.current_role,'kopilot')
        env.step(choose(env,'swap_choose',die=0))
        self.assertEqual(env.game.pilot_wuerfel[0].augenzahl,before['kopilot'])
        self.assertEqual(env.game.kopilot_wuerfel[0].augenzahl,before['pilot'])

    def test_clock_expiry_is_a_game_outcome(self):
        case=next(c for c in MATRIX['cases'] if 'realtime' in c['modules'])
        now=[0.]
        env=ModuleEnv(case['airport'],abilities=case['abilities'],clock=lambda:now[0])
        env.reset(seed=46)
        action=next(i for i,ok in enumerate(env.action_mask()) if ok)
        now[0]=61.
        _,_,terminated,_,info=env.step(action)
        self.assertTrue(terminated)
        self.assertEqual(info['status'],'verloren')
        self.assertIn('pflichtfelder',info['reason'])


if __name__=='__main__':unittest.main()
