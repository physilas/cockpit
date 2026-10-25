"""Capacity-preserving mask checked against engine effects and winning paths."""
from copy import deepcopy
import random
import unittest
from unittest.mock import patch

from ai.actions import Action
from ai.landing_task_budget import task_budget
from ai.modules import MODULE_ACTIONS,MODULE_SLOTS,ModuleEnv
from ai.module_physics import WIND_RING
from ai.task_deadline_guard import preserve_task_budget
from ai.task_deadline_environment import TaskDeadlineEnv
from ai.wind_ice_advice import _after_placement
from ai.joint_landing_environment import JointLandingEnv
from tests.test_ai_joint_landing import ice_fixture,brake_fixture,radio_fixture
from tests.test_ai_solo_landing import black_fixture
from tests.test_ai_wind_ice_counterexamples import _action,_place


def deadline_fixture():
    env=ice_fixture();game,c=env.game,env.game.cockpit
    game.landung.hoehe=1000;game.letzte_runde=False;game.warteschleife=True
    c.fahrwerk_ausgefahren[:]=[False]*3;c.landeklappen_ausgefahren[:]=[True,False,False,False]
    return env


class TaskDeadlineTests(unittest.TestCase):
    def test_exact_two_round_budget_protects_task_die_but_keeps_helpers(self):
        env=deadline_fixture();env.game.cockpit.kaffeetassen=3
        view,original=env.view(),env.action_mask()
        self.assertTrue(task_budget(view)['possible'])
        allowed,meta=preserve_task_budget(view,original)
        bad=_action(3,'konzentration',index=0);good=_action(2,'eisbremse',index=6)
        self.assertTrue(original[bad]);self.assertFalse(allowed[bad]);self.assertTrue(allowed[good])
        self.assertTrue(meta['eligible']);self.assertIn(bad,meta['removed'])
        for i,action in enumerate(MODULE_ACTIONS):
            if action.kind!='place':self.assertEqual(allowed[i],original[i])
        self.assertTrue(all(not flag or original[i] for i,flag in enumerate(allowed)))

    def test_current_radio_flap_control_budget_excludes_empty_radio_and_concentration(self):
        env=radio_fixture();original=env.action_mask()
        allowed,_=preserve_task_budget(env.view(),original)
        good=_action(0,'funk',owner='kopilot');coffee=_action(0,'konzentration',index=0)
        # Copilot5 on radio would not remove the required airport plane.
        useless=_action(3,'funk',owner='kopilot')
        self.assertTrue(allowed[good]);self.assertFalse(allowed[coffee]);self.assertFalse(allowed[useless])

    def test_infeasible_unknown_dialog_and_empty_result_abstain(self):
        env=deadline_fixture();view=env.view();original=env.action_mask()
        bad=_action(3,'konzentration',index=0)
        single=[i==bad for i in range(len(original))]
        result,meta=preserve_task_budget(view,single)
        self.assertEqual(result,single);self.assertTrue(meta['fallback'])
        variants=[]
        impossible=deepcopy(view);impossible['track'][-1]['planes']=3;variants.append(impossible)
        sync=deepcopy(view);sync['modules_state']['cards']=['synchronisation'];variants.append(sync)
        for pending in (dict(role='pilot',source='synchronisation',value=5),dict(role='pilot',source='synchronisation',value=None)):
            dialog=deepcopy(view);dialog['modules_state']['pending']=pending;variants.append(dialog)
        reroll=deepcopy(view);reroll['reroll']=dict(initiator='pilot',selections={'pilot':None,'kopilot':None});variants.append(reroll)
        for altered in variants:
            result,meta=preserve_task_budget(altered,original)
            self.assertEqual(result,original);self.assertFalse(meta['eligible'])
        bonus=black_fixture();original=bonus.action_mask()
        result,meta=preserve_task_budget(bonus.view(),original)
        self.assertEqual(result,original)
        self.assertEqual(meta['before_budget']['issued_shared_bonus'],1)

    def test_projected_ongoing_public_count_effects_match_native_engine_for_all_legal_placements(self):
        checked=0
        for make in (ice_fixture,brake_fixture,radio_fixture,deadline_fixture):
            for coffee in (0,3):
                env=make();env.game.cockpit.kaffeetassen=coffee
                source=env.view();mask=env.action_mask()
                if task_budget(source)['possible'] is not True:continue
                for i,flag in enumerate(mask):
                    a=MODULE_ACTIONS[i]
                    if not flag or a.kind!='place':continue
                    actual=deepcopy(env);slot=MODULE_SLOTS[a.slot]
                    result=actual.game.platziere(source['role'],a.die,slot.target,index=slot.index,funk_feld=slot.radio_index)
                    self.assertTrue(result.erfolg)
                    if result.verloren:continue
                    c=actual.game.cockpit
                    if source['last_round'] and not c.ruder_pilot.ist_frei() and not c.ruder_kopilot.ist_frei() and c.fluglage!=0:
                        continue  # Already fixed nonlevel final rudder cannot win; wind can differ.
                    predicted,_=_after_placement(source,a.die,a.slot,source['own_dice'][a.die],source['coffee'])
                    self.assertEqual(task_budget(predicted),task_budget(actual.view(source['role'])),(make.__name__,i))
                    checked+=1
        self.assertGreater(checked,100)

    def test_all_actions_in_successful_engine_landings_remain_available(self):
        exercises=[(ice_fixture(),(('pilot',2,'eisbremse',6),('kopilot',0,'ruder',None),
            ('pilot',0,'ruder',None),('kopilot',1,'triebwerk',None),('pilot',1,'triebwerk',None),
            ('kopilot',2,'eisbremse',7),('pilot',3,'konzentration',0),('kopilot',3,'konzentration',1))),
            (brake_fixture(),(('pilot',2,'bremse',0),('kopilot',0,'ruder',None),('pilot',0,'ruder',None),
            ('kopilot',1,'triebwerk',None),('pilot',1,'triebwerk',None),('kopilot',2,'landeklappe',3),
            ('pilot',3,'konzentration',0),('kopilot',3,'konzentration',1)))]
        # Third exercise: strong headwind allows no regular brake at all.
        env=brake_fixture();env.game.cockpit.wind_position=WIND_RING.index(-3)
        env.game.cockpit.landeklappen_ausgefahren[:]=[True]*4
        exercises.append((env,(('pilot',0,'ruder',None),('kopilot',0,'ruder',None),
            ('pilot',1,'triebwerk',None),('kopilot',1,'triebwerk',None),('pilot',2,'konzentration',0),
            ('kopilot',2,'landeklappe',3),('pilot',3,'konzentration',1),('kopilot',3,'konzentration',2))))
        for env,sequence in exercises:
            for role,die,target,index in sequence:
                original=env.action_mask();allowed,_=preserve_task_budget(env.view(),original)
                choice=_action(die,target,owner=role if target in ('ruder','triebwerk') else None,index=index)
                self.assertTrue(allowed[choice],(target,index))
                _place(env.game,role,die,target,index)
            self.assertTrue(env.game.rundenende().gewonnen)

    def test_no_mutation_rng_or_unknown_partner_face_dependency_and_pacing(self):
        env=deadline_fixture();view=env.view();snapshot=deepcopy(view);mask=env.action_mask()
        rng=random.getstate();expected=preserve_task_budget(view,mask)
        for die in env.game.kopilot_wuerfel:die.augenzahl=6
        self.assertEqual(env.view(),view)
        with patch('ai.task_deadline_guard.CpuBudget.pause') as pause:
            self.assertEqual(preserve_task_budget(env.view(),mask,cpu_duty_cycle=.7),expected)
            self.assertTrue(pause.called)
        self.assertEqual(view,snapshot);self.assertEqual(random.getstate(),rng)

    def test_environment_preserves_original_masks_reference_inputs_clock_and_cache(self):
        source=JointLandingEnv('LOG_KEF_YELLOW',abilities=['adaptation'])
        candidate=TaskDeadlineEnv('LOG_KEF_YELLOW',abilities=['adaptation'])
        fixed=deadline_fixture().game
        source.game=deepcopy(fixed);candidate.game=deepcopy(fixed)
        before=source.info();after=candidate.info()
        self.assertEqual(source.view(),candidate.view());self.assertEqual(source.observation(),candidate.observation())
        self.assertEqual(before['action_mask'],after['pre_guard_action_mask'])
        self.assertEqual(before['reference_action_mask'],after['pre_guard_reference_action_mask'])
        self.assertNotEqual(after['action_mask'],before['action_mask'])
        self.assertTrue(all(not v or after['action_mask'][i] for i,v in enumerate(after['reference_action_mask'])))
        self.assertEqual(source.rng.getstate(),candidate.rng.getstate());self.assertIsNone(candidate.clock)
        with patch('ai.task_deadline_environment.preserve_task_budget',side_effect=AssertionError('Cache')):candidate.info()
        after['task_deadline']['before_budget']['available_total']=-1
        self.assertGreater(candidate.info()['task_deadline']['before_budget']['available_total'],0)

    def test_non_wind_ice_and_future_sync_environment_paths_remain_exact(self):
        for airport,cards in (('LOG_ATL_YELLOW',['adaptation']),('LOG_ATL_GREEN',[]),('MUC',[]),
                ('LOG_KEF_YELLOW',['synchronisation'])):
            source=JointLandingEnv(airport,abilities=cards);candidate=TaskDeadlineEnv(airport,abilities=cards)
            seed='train:task-deadline-fallback:251072:'+airport
            a,ia=source.reset(seed=seed);b,ib=candidate.reset(seed=seed)
            self.assertEqual(a,b);self.assertEqual(ia['action_mask'],ib['action_mask'])
            self.assertEqual(ia['reference_action_mask'],ib['reference_action_mask'])
            self.assertEqual(source.rng.getstate(),candidate.rng.getstate())


if __name__=='__main__':unittest.main()
