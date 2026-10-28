from copy import deepcopy
import random
import unittest

from ai.actions import Action
from ai.contract_planner import ContractAgent, Plan, apply_placement, legal_target, plan_round, capacity_penalty, progress_value, public_movement_target, landing_count_possible, final_value, IDS
from ai.module_training_eval import _official_cases
from ai.modules import MODULE_ACTIONS, ModuleEnv


class ContractPlannerTests(unittest.TestCase):
    def test_full_engine_games_always_receive_a_legal_first_action(self):
        class FirstLegal:
            def rank(self,view,mask):
                legal=[i for i,ok in enumerate(mask) if ok]
                return legal[0],legal
        for airport,cards in (('MUC',[]),('LOG_GIG_YELLOW',['adaptation']),
                              ('LOG_KEF_YELLOW',['synchronisation']),('LOG_HND_RED',['adaptation'])):
            env=ModuleEnv(airport,abilities=cards,clock=lambda:0.)
            env.reset(seed='train:contract-integration:'+airport)
            agent=ContractAgent(airport,FirstLegal(),beam=12)
            while not env.done:
                raw=env.action_mask()
                action=agent.select(env.view(),raw)
                self.assertTrue(raw[action],(airport,action))
                env.step(action)
            self.assertFalse(env.truncated,airport)

    def test_own_placement_projection_matches_real_module_engine(self):
        rng = random.Random(185)
        for airport, cards in list(_official_cases())[::19]:
            env = ModuleEnv(airport, abilities=cards, clock=lambda: 0.)
            env.reset(seed=14000200)
            for step in range(12):
                if env.done:
                    break
                view = env.view()
                pending = view['modules_state']['pending']
                node = Plan(view, virtual=pending['value'] if pending and pending['value'] else 0,
                            source=pending['source'] if pending else '')
                raw = env.action_mask()
                for index, ok in enumerate(raw):
                    action = MODULE_ACTIONS[index]
                    if not ok or action.kind not in ('place','bonus_place'):
                        continue
                    face = view['own_dice'][action.die] if action.kind=='place' else node.virtual
                    self.assertTrue(legal_target(node, action.slot, face), (airport,index))
                    projected = apply_placement(node,action.die if action.kind=='place' else 4,
                                                action.slot,face,view['coffee'],False)
                    branch = deepcopy(env)
                    branch.step(index)
                    if branch.game.status=='verloren' and branch.game.aktuelle_runde==env.game.aktuelle_runde:
                        # End-of-round losses are evaluated separately; only
                        # immediate rudder/fuel consequences return no projection.
                        if branch.game.verlust_grund in ('trudeln','kerosin_leer'):
                            self.assertIsNone(projected)
                        continue
                    if projected is None or branch.game.aktuelle_runde!=env.game.aktuelle_runde:
                        continue
                    actual = branch.view(view['role'])
                    for key in ('own_dice','board','gear','flaps','brake_progress','coffee',
                                'attitude','aero_blue','aero_orange','brakes','track','fuel'):
                        self.assertEqual(actual[key],projected.view[key],(airport,step,index,key))
                    for key in ('extra_fields','intern','ice_progress','wind_position'):
                        self.assertEqual(actual['modules_state'][key],projected.view['modules_state'][key],
                                         (airport,step,index,key))
                env.step(rng.choice([i for i,ok in enumerate(raw) if ok]))

    def test_intern_cannot_generate_coffee_or_train_again(self):
        env = ModuleEnv('LOG_HND_RED', abilities=['adaptation'])
        env.reset(seed=14000201)
        node = Plan(env.view(), virtual=2, source='intern')
        self.assertFalse(legal_target(node,17,2))
        self.assertFalse(legal_target(node,21,2))

    def test_public_control_coffee_after_spending_a_full_cup_pool(self):
        airport,cards = next((a,c) for (a,c),m in _official_cases().items() if c==('control',))
        env = ModuleEnv(airport, abilities=cards)
        env.reset(seed=14000202)
        env.game.cockpit.kaffeetassen=3
        partner=env.game.kopilot_wuerfel[0]
        partner.augenzahl,partner.platziert=3,True
        env.game.cockpit.ruder_kopilot.wuerfel=partner
        view=env.view()
        view['own_dice'][0]=2
        projected=apply_placement(Plan(view),0,0,3,2,False)
        self.assertEqual(3,projected.view['coffee'])

    def test_hidden_faces_and_game_rng_cannot_change_plan(self):
        env=ModuleEnv('MUC')
        env.reset(seed=14000203)
        view=env.view()
        first=plan_round(view,env.action_mask(),beam=12)
        for die in env.game.kopilot_wuerfel:
            die.augenzahl=7-die.augenzahl
        env.rng.seed(1)
        self.assertEqual(first,plan_round(env.view(),env.action_mask(),beam=12))
        self.assertTrue(first)
        self.assertTrue(all(env.action_mask()[index] for index in first))

    def test_unfinished_ice_half_is_not_a_persistent_upgrade(self):
        env=ModuleEnv('LOG_KEF_YELLOW', abilities=['adaptation'])
        env.reset(seed=14000204)
        view=env.view()
        view['height']=1000
        before=capacity_penalty(view)
        view['modules_state']['extra_fields'][2]={'value':2,'owner':'pilot'}
        self.assertEqual(before,capacity_penalty(view))

    def test_public_movement_contract_is_identical_for_both_private_views(self):
        env=ModuleEnv('LOG_GIG_YELLOW', abilities=['adaptation'])
        env.reset(seed=14000205)
        self.assertEqual(public_movement_target(env.view('pilot')),public_movement_target(env.view('kopilot')))
        view=env.view()
        target=public_movement_target(view)
        view['own_dice']=[1,1,1,1]
        self.assertEqual(target,public_movement_target(view))
        for cell in view['track']:
            if cell['distance']==view['distance']:
                cell['planes']=4
        self.assertEqual(0,public_movement_target(view))

    def test_public_contract_does_not_demand_physically_impossible_double_speed(self):
        env=ModuleEnv('MUC')
        env.reset(seed=14000206)
        env.game.landung.hoehe=3000
        env.game.cockpit.landeklappen_ausgefahren=[True]*4
        env.game.cockpit.aerodynamik_orange=12.5
        self.assertEqual(1,public_movement_target(env.view()))

    def test_impossible_ice_half_is_not_rewarded_as_progress(self):
        env=ModuleEnv('LOG_KEF_YELLOW',abilities=['adaptation'])
        env.reset(seed=14000207)
        root=env.view('kopilot')
        root['partner_remaining']=0
        changed=deepcopy(root)
        changed['own_dice']=[0]*4
        changed['modules_state']['extra_fields'][3]={'value':2,'owner':'kopilot'}
        self.assertEqual(0,progress_value(root,changed))

    def test_final_count_bound_and_unissued_bonus_abstention(self):
        env=ModuleEnv('LOG_KEF_YELLOW',abilities=['synchronisation'])
        env.reset(seed=14000208)
        view=env.view()
        view.update(last_round=True,distance=0,height=0,gear=[True]*3,flaps=[True]*4)
        for cell in view['track']:cell['planes']=0
        view['modules_state']['cards']=[]
        # Eight ice fields plus four controls cannot fit into eight dice.
        self.assertFalse(landing_count_possible(view))
        view['modules_state']['cards']=['synchronisation']
        self.assertTrue(landing_count_possible(view))
        view['modules_state']['cards']=[]
        view['modules_state']['ice_progress']=3
        self.assertTrue(landing_count_possible(view))
        view['board'][2]={'value':6,'owner':'pilot'}
        self.assertFalse(landing_count_possible(view))

    def test_impossible_tasks_still_distinguish_sensible_flight_controls(self):
        env=ModuleEnv('LOG_KEF_YELLOW',abilities=['adaptation'])
        env.reset(seed=14000209)
        root=env.view()
        root.update(last_round=True,distance=0,height=0,gear=[True]*3,flaps=[True]*4)
        for cell in root['track']:cell['planes']=0
        slow=deepcopy(root)
        slow['board'][0]={'value':3,'owner':'pilot'}
        slow['board'][2]={'value':1,'owner':'pilot'}
        fast=deepcopy(slow)
        fast['board'][2]={'value':6,'owner':'pilot'}
        a=final_value(root,slow,{},details=True)
        b=final_value(root,fast,{},details=True)
        self.assertEqual(0,a[0])
        self.assertEqual(0,b[0])
        self.assertGreater(a[2],b[2])

    def test_public_irreversibility_is_detected_before_the_landing_round(self):
        env=ModuleEnv('MUC');env.reset(seed='train:public-win-bound')
        view=env.view()
        for cell in view['track']:cell['planes']=0
        view.update(height=1000,distance=3)
        self.assertFalse(landing_count_possible(view))
        view['height']=6000
        cell=next(c for c in view['track'] if c['distance']>view['distance'])
        cell['planes']=1
        self.assertFalse(landing_count_possible(view))

    def test_every_official_start_passes_the_optimistic_public_bound(self):
        for airport,cards in _official_cases():
            env=ModuleEnv(airport,abilities=cards)
            env.reset(seed='train:public-bound-start:'+airport+','.join(cards))
            self.assertTrue(landing_count_possible(env.view()),(airport,cards))

    def test_early_ice_option_is_identical_on_routes_without_ice(self):
        for airport,cards in (('MUC',[]),('LOG_ATL_GREEN',[]),('LOG_PRG_YELLOW',['adaptation','control'])):
            env=ModuleEnv(airport,abilities=cards);env.reset(seed='train:ice-option:'+airport)
            self.assertEqual(plan_round(env.view(),env.action_mask(),beam=12),
                             plan_round(env.view(),env.action_mask(),beam=12,early_ice=True))
