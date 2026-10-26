"""Cooperative public-view teams: guided policies retain their own references.

Mixed rollouts learn only from the designated role. Partner decisions and
rewards advance the game but are never mislabeled as learner actions.
"""
from collections import Counter
from .modules import ModuleEnv
from .agents import ModelAgent
from .evaluate import summarize_episodes
from .module_training_eval import case_key, _development_seed, _official_cases
from .throttle import CpuBudget

class PublicLeagueEnv(ModuleEnv):
    # collect_rollout normally disables assistance on a generic partner. Here
    # both partners are public-profile-12 neural players, so both require it.
    @property
    def assisted_roles(self):return ('pilot','kopilot')
    @assisted_roles.setter
    def assisted_roles(self, value):pass

    def reset(self,**kwargs):
        self.role_decisions=Counter()
        return super().reset(**kwargs)

    def step(self,action):
        role=self.current_role
        result=super().step(action)
        self.role_decisions[role]+=1
        return result

    def episode_record(self,seed,ai_role,total_return):
        row=super().episode_record(seed,ai_role,total_return)
        row['engine_decisions']=row['steps']
        if ai_role in ('pilot','kopilot'):
            row['steps']=self.role_decisions[ai_role]
            row['partner_decisions']=sum(self.role_decisions.values())-row['steps']
        return row

def run_team_case(pilot,kopilot,case,games,seed,*,duty=.6):
    _development_seed(seed,games)
    if _official_cases().get((case['airport'],tuple(sorted(case['abilities']))))!=sorted(case['modules']):
        raise ValueError('Use an exact official route/card/module case.')
    if not 0<duty<=.6:raise ValueError('League duty must be at most .6.')
    env=PublicLeagueEnv(case['airport'],abilities=case['abilities'],assistance_version=12,max_steps=256,
       round_reward=0.,sync_weight=0.,task_weight=0.,planning_cpu_duty_cycle=duty)
    agents={'pilot':ModelAgent(pilot),'kopilot':ModelAgent(kopilot)}
    budget=CpuBudget(duty);records=[]
    for ordinal in range(games):
        _,info=env.reset(seed=seed+ordinal);total=0.
        while not env.done:
            action=agents[env.current_role].select(env.view(),info['action_mask'],reference_mask=info['reference_action_mask'])
            _,reward,_,_,info=env.step(action);total+=reward;budget.pause()
        row=env.episode_record(seed+ordinal,'both',total)
        row.update(airport=case['airport'],abilities=case['abilities'],modules=case['modules'],case_key=case_key(case))
        records.append(row)
    return dict(complete=True,release_evidence=False,clock_model='engine_wall_clock',airport=case['airport'],abilities=case['abilities'],modules=case['modules'],
                case_key=case_key(case),**summarize_episodes(records))
