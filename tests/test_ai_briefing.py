import copy
import json
import random
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from backend import bridge
from play_options import neues_spiel
from ai.briefing import proposals, suggest, start_round, validate_plan
from ai.briefing_browser import decision
from ai.ability_browser import decision as legacy
from ai.briefing_planner import plan_briefed_round
from ai.modules import ModuleEnv, MODULE_ACTIONS
from ai.actions import Action

ROOT=Path(__file__).resolve().parents[1]


def plan_for(state, **changes):
    return {'version':1,'round':state['runde'],**{g['key']:g['selected'] for g in proposals(state)['goals']},**changes}


def traffic():
    while bridge.zustand()['phase']=='verkehr':bridge.wirf_verkehrswuerfel()


class BriefingTests(unittest.TestCase):
    def test_preparation_does_not_roll_or_start_clock_and_skip_preserves_rng(self):
        for airport,cards in [('LOG_YUL_GREEN',[]),('LOG_ATL_GREEN',[]),('LOG_PBH_RED',['control','synchronisation'])]:
            with self.subTest(airport=airport):
                random.seed(90210);neues_spiel(airport,json.dumps(cards));traffic();bridge.wuerfeln_fuer_runde()
                expected=bridge.zustand();expected_rng=random.getstate()
                random.seed(90210);neues_spiel(airport,json.dumps(cards),briefing=True);traffic()
                state=bridge.zustand();self.assertEqual('vorbereitung',state['phase'])
                self.assertEqual([None]*4,state['pilot_wuerfel']);self.assertIsNone(state['timer_deadline_ms'])
                before=random.getstate();suggest();self.assertEqual(before,random.getstate())
                actual=start_round()
                for key in ('pilot_wuerfel','kopilot_wuerfel','flugzeuge','praktikant','kerosin'):
                    self.assertEqual(expected[key],actual[key])
                self.assertEqual(expected_rng,random.getstate())
                if 'realtime' in actual['module']:self.assertIsNotNone(actual['timer_deadline_ms'])
                with self.assertRaises(ValueError):suggest()

    def test_proposals_only_depend_on_public_information_and_reject_invalid_plans(self):
        state=neues_spiel('LOG_YUL_GREEN',briefing=True)
        before=proposals(state)
        changed={**state,'pilot_wuerfel':[6]*4,'kopilot_wuerfel':[1]*4,'timer_deadline_ms':1}
        self.assertEqual(before,proposals(changed));self.assertNotIn('pilot_wuerfel',before['public_state'])
        self.assertEqual('Fahrwerk & Klappen',next(o['label'] for g in before['goals'] for o in g['options'] if o['value']=='tasks'))
        valid=plan_for(state);self.assertEqual(valid,validate_plan(valid,state))
        for bad in ({**valid,'round':2},{**valid,'movement_preference':True},{**valid,'movement_preference':3},
                    {**valid,'coordination':'synchronisation'},{**valid,'hidden_die':6},{**valid,'focus':'ignore rules'}):
            with self.assertRaises(ValueError):validate_plan(bad,state)
        before=random.getstate()
        with self.assertRaises(ValueError):start_round(json.dumps({**valid,'round':2}))
        self.assertEqual(before,random.getstate());self.assertEqual('vorbereitung',bridge.zustand()['phase'])

    def test_no_plan_delegates_every_released_profile_exactly_and_import_is_torch_free(self):
        neues_spiel('LOG_YUL_GREEN')
        for profile in (0,12,13,14,15):
            self.assertEqual(legacy(assistance_version=profile,schema_version=3),decision(assistance_version=profile,schema_version=3))
        subprocess.run([sys.executable,'-c',"import sys;import ai.briefing_browser;assert 'torch' not in sys.modules"],cwd=ROOT,check=True,timeout=10)

    def test_different_movement_goals_change_complete_physical_hand_plans(self):
        env=ModuleEnv('LOG_YUL_GREEN');env.reset(seed='briefing-movement-fixture')
        view=env.view();view['distance']=2;view['height']=6000
        view['board'][:4]=[{'value':2,'owner':'pilot'},{'value':2,'owner':'kopilot'},None,{'value':2,'owner':'kopilot'}]
        view['own_dice']=[0,2,6,0];view['partner_remaining']=0;view['gear']=[True]*3;view['flaps']=[True]*4
        view['coffee']=0;view['aero_blue']=4.5;view['aero_orange']=8.5
        for cell in view['track']:cell['planes']=0
        mask=[a.kind=='place' and (a.slot==2 or a.slot==17) for a in MODULE_ACTIONS]
        ids={a:i for i,a in enumerate(MODULE_ACTIONS)}
        low,high=ids[Action('place',die=1,slot=2)],ids[Action('place',die=2,slot=2)]
        ranks=[]
        for move in (0,1):
            v={**view,'_briefing':{'movement_preference':move,'focus':'coffee','coordination':'level'}}
            ranks.append(plan_briefed_round(v,mask))
        self.assertGreater(ranks[0][low],ranks[0][high]);self.assertGreater(ranks[1][high],ranks[1][low])

    def test_accepted_plan_preserves_native_mask_and_never_looks_at_partner_faces(self):
        env=ModuleEnv('LOG_KUL_YELLOW',abilities=['synchronisation']);env.reset(seed='briefing-hidden-partner')
        with patch.object(bridge,'_spiel',env.game):
            p=plan_for(bridge.zustand());actual=decision(assistance_version=15,schema_version=3,plan_json=json.dumps(p))
            native=env.action_mask()
            self.assertTrue(all(not a or b for a,b in zip(actual['action_mask'],native)))
            self.assertTrue(actual['public_plan']['scores']);self.assertEqual('briefing-v1',actual['communication_policy'])
            for w in env.game.kopilot_wuerfel:w.augenzahl=7-w.augenzahl
            self.assertEqual(actual,decision(assistance_version=15,schema_version=3,plan_json=json.dumps(p)))

    def test_focus_changes_real_placement_between_tasks_radio_and_coffee(self):
        from ai.modules import MODULE_SLOTS
        env=ModuleEnv('LOG_YUL_GREEN');env.reset(seed='briefing-focus-fixture')
        v=env.view();v.update(distance=2,height=6000,coffee=0,own_dice=[0,3,0,0],partner_remaining=0,
                             gear=[True,False,True],flaps=[True]*4,aero_blue=6.5,aero_orange=6.5)
        v['board'][:4]=[{'value':2,'owner':r} for r in ('pilot','kopilot','pilot','kopilot')]
        for cell in v['track']:cell['planes']=int(cell['distance']==0)
        mask=[a.kind=='place' for a in MODULE_ACTIONS]
        for focus,target in [('tasks','fahrwerk'),('radio','funk'),('coffee','konzentration')]:
            view={**v,'_briefing':{'movement_preference':0,'focus':focus,'coordination':'level'}}
            ranks=plan_briefed_round(view,mask);action=MODULE_ACTIONS[max(ranks,key=ranks.get)]
            self.assertEqual(target,MODULE_SLOTS[action.slot].target)

    def test_unrolled_briefing_survives_save_and_resume(self):
        state=neues_spiel('LOG_YUL_GREEN',briefing=True);p=plan_for(state)
        saved=bridge.spiel_speichern();bridge.spiel_laden(saved)
        self.assertEqual(1,suggest()['round']);start_round(json.dumps(p))
        self.assertEqual('platzieren',bridge.zustand()['phase'])


class BriefingParityTests(unittest.TestCase):
    def test_all_six_crews_match_actual_javascript_weights_with_accepted_goals(self):
        import torch
        from ai.agents import ModelAgent
        from ai.checkpoints import load_checkpoint
        from ai.public_contract import arbitrate_contract
        torch.set_num_threads(1)
        catalog=json.loads((ROOT/'frontend/web/js/ai-models.js').read_text().split(' = ',1)[1].rstrip(';\n'))
        fixtures=[];expected=[]
        for entry in (m for m in catalog['models'] if m.get('crew_number')):
            model=load_checkpoint(ROOT/'ai/releases'/entry['id'])[0];agent=ModelAgent(model)
            for move in (0,1):
                env=ModuleEnv('LOG_YUL_GREEN');env.reset(seed=f"briefing-portable:{entry['crew_number']}")
                with patch.object(bridge,'_spiel',env.game):
                    p=plan_for(bridge.zustand(),movement_preference=move)
                    d=decision(assistance_version=entry['assistance_version'],schema_version=3,plan_json=json.dumps(p))
                    public=d['public_plan'];base=agent.select(env.view(),public['baseline_mask'],reference_mask=d.get('reference_action_mask'))
                    chosen=arbitrate_contract(base,d['action_mask'],public)
                    self.assertTrue(env.action_mask()[chosen]);expected.append(chosen)
                    fixtures.append({'id':entry['id'],'decision':d})
        script="""const fs=require('fs');global.window={};eval(fs.readFileSync('frontend/web/js/ai-policy.js','utf8'));const catalog=JSON.parse(fs.readFileSync('frontend/web/js/ai-models.js','utf8').split(' = ')[1].trim().replace(/;$/,''));const rows=JSON.parse(fs.readFileSync(0,'utf8'));console.log(JSON.stringify(rows.map(row=>{const m=catalog.models.find(m=>m.id===row.id);return window.CockpitPolicy.create(JSON.parse(fs.readFileSync('frontend/web/'+m.url,'utf8')),{schema:m.schema||catalog.schema}).select(row.decision);})));"""
        result=subprocess.run(['node','-e',script],input=json.dumps(fixtures),text=True,capture_output=True,cwd=ROOT,check=True,timeout=30)
        self.assertEqual(expected,json.loads(result.stdout));self.assertEqual(12,len(fixtures))
