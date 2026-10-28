"""Train a public macro-policy on terminal landing outcomes; old crews stay frozen.

Learned rollouts use briefing-v2; the fixed-goal comparison uses frozen
briefing-v1. Both retain the original Crew 6 checkpoint.
One round action comprises movement/focus/coordination, held until round end.
Training uses a frozen simulation clock; independent evaluation uses wall time.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
import hashlib
import json
import math
from pathlib import Path
import random
import time
import torch
from torch import nn
from backend import bridge
from .briefing_browser import decision as original_decision
from .briefing_browser_v2 import decision,execution_fingerprint
from .round_strategy import FEATURES,HEADS,OFFSETS,OUTPUTS,FORMAT,GOALS_SCHEMA,inputs,choose,potential
from .briefing import policy_fingerprint
from .round_strategy_options import PLAN_VERSION,is_expert_plan
from .checkpoints import load_checkpoint,weight_fingerprint
from .agents import ModelAgent
from .modules import ModuleEnv
from .public_contract import arbitrate_contract
from .preview_matrix_eval import catalogue_cases
from .module_training_eval import case_key


def atomic(path,data):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(p)


class RoundActor(nn.Module):
    def __init__(self):
        super().__init__();self.hidden=nn.Linear(len(FEATURES),48);self.output=nn.Linear(48,OUTPUTS+1);self.training_updates=0
        nn.init.orthogonal_(self.hidden.weight,1.);nn.init.zeros_(self.hidden.bias)
        nn.init.orthogonal_(self.output.weight,.01);nn.init.zeros_(self.output.bias)
    def forward(self,x):return self.output(torch.tanh(self.hidden(x)))
    def portable(self):
        return dict(format=FORMAT,features=list(FEATURES),goals_schema=GOALS_SCHEMA,training_updates=self.training_updates,hidden_weight=self.hidden.weight.detach().tolist(),hidden_bias=self.hidden.bias.detach().tolist(),actor_weight=self.output.weight[:OUTPUTS].detach().tolist(),actor_bias=self.output.bias[:OUTPUTS].detach().tolist())


def load_actor_weights(actor,weights):
    if weights.get('features')!=list(FEATURES):raise ValueError('Wrong warm-start feature schema.')
    with torch.no_grad():
        actor.hidden.weight.copy_(torch.tensor(weights['hidden_weight']))
        actor.hidden.bias.copy_(torch.tensor(weights['hidden_bias']))
        actor.output.weight.zero_();actor.output.bias.zero_()
        if weights.get('format')==FORMAT:
            if weights.get('goals_schema')!=GOALS_SCHEMA:raise ValueError('Wrong warm-start goal schema.')
            actor.output.weight[:OUTPUTS].copy_(torch.tensor(weights['actor_weight']))
            actor.output.bias[:OUTPUTS].copy_(torch.tensor(weights['actor_bias']))
            actor.training_updates=weights.get('training_updates',0)
        # Old 11-output actors transfer their public encoder only. The new
        # 14-output head starts at the exact expert option, with no new goals
        # forced on the already strong autonomous policy.



def sample(actor,state,stochastic,head=None,boost=False):
    x,mask,prior=inputs(state);row=actor(torch.tensor(x,dtype=torch.float32));p=row[:OUTPUTS]+torch.tensor(prior)
    if stochastic and head is not None:
        for h,(a,b) in enumerate(zip(OFFSETS,OFFSETS[1:])):
            if h==head:continue
            best=max((i for i in range(a,b) if mask[i]),key=lambda i:float(p[i].detach()))
            for i in range(a,b):mask[i]=i==best
    p=p.masked_fill(~torch.tensor(mask),-1e9);actions=[];logp=0.;behavior_logp=0.
    for a,b in zip(OFFSETS,OFFSETS[1:]):
        dist=torch.distributions.Categorical(logits=p[a:b]);behavior=dist
        if stochastic and boost and head is not None and a==OFFSETS[head] and sum(mask[a:b])>1:
            alternatives=torch.tensor(mask[a:b],dtype=torch.float32);alternatives[int(p[a:b].argmax())]=0
            behavior=torch.distributions.Categorical(probs=.2*dist.probs+.8*alternatives/alternatives.sum())
        action=behavior.sample() if stochastic else p[a:b].argmax()
        actions.append(int(action));logp=logp+dist.log_prob(action);behavior_logp=behavior_logp+behavior.log_prob(action)
    plan={'version':PLAN_VERSION,'round':state['runde'],**{key:values[i] for (key,values),i in zip(HEADS,actions)}}
    return plan,dict(x=x,mask=mask,prior=prior,actions=actions,logp=float(logp.detach()),behavior_logp=float(behavior_logp.detach()),value=float(row[-1].detach()),phi=potential(state),round=state['runde'])


def play(model,case,seed,actor=None,weights=None,stochastic=False,wall_clock=False,mode='plan',single_exploration=False,exploration_choice=None):
    env=ModuleEnv(case['airport'],abilities=case['abilities'],assistance_version=0,max_steps=256,round_reward=0.,sync_weight=0.,task_weight=0.,clock=None if wall_clock else lambda:0.)
    env.reset(seed=seed);agent=ModelAgent(model);rows=[];round_id=None;plan=None;decisions=0;started=time.monotonic();unsafe=0;goal_violations=0;bonus_rolls=0;trace=[]
    exploration=random.Random(seed+':exploration');explore_round,explore_head=exploration_choice or (exploration.randint(1,6),exploration.randrange(3))
    from .ability_policy import AbilityAgent
    legacy=AbilityAgent(case['airport'],model)
    try:
        while not env.done:
            if round_id!=env.game.aktuelle_runde:
                round_id=env.game.aktuelle_runde;state=env.game.zustand()
                if trace:
                    trace[-1].update(actual_movement=trace[-1]['distance']-state['entfernung'],
                        new_gear=sum(state['fahrwerk_ausgefahren'])-trace[-1]['gear_done'],
                        new_flaps=sum(state['landeklappen_ausgefahren'])-trace[-1]['flaps_done'])
                if actor is not None:
                    if rows:
                        rows[-1]['next_phi']=potential(state)
                        with torch.no_grad():rows[-1]['next_value']=float(actor(torch.tensor(inputs(state)[0]))[-1])
                    varied=stochastic and (not single_exploration or round_id==explore_round)
                    with torch.no_grad():plan,row=sample(actor,state,varied,explore_head if single_exploration and varied else None,boost=single_exploration)
                    row['policy_weight']=float(varied);rows.append(row)
                else:plan=choose(state,weights)
                allowed_goals=inputs(state)[1]
                goal_violations+=sum(not allowed_goals[OFFSETS[h]+values.index(plan[key])] for h,(key,values) in enumerate(HEADS))
                trace.append({'round':round_id,'plan':dict(plan),'public_features':inputs(state)[0],'exploration':bool(actor is not None and varied),'potential':potential(state),'distance':state['entfernung'],'gear_done':sum(state['fahrwerk_ausgefahren']),'flaps_done':sum(state['landeklappen_ausgefahren']),'expert_option':is_expert_plan(plan),'applied':mode!='autonomous'})
            view,raw=env.view(),env.action_mask()
            if mode=='autonomous':selected=legacy.select(view,raw)
            else:
                bridge._spiel=env.game
                executor=original_decision if mode=='default' else decision
                d=executor(reroll_json=json.dumps(env.reroll),steps=env.steps,assistance_version=15,schema_version=3,plan_json=json.dumps(plan))
                baseline=agent.select(view,d['public_plan']['baseline_mask'],reference_mask=d.get('reference_action_mask'))
                selected=arbitrate_contract(baseline,d['action_mask'],d['public_plan'])
            if not raw[selected]:raise RuntimeError('Action outside native mask')
            from .coherent_safety import coherent_safe_actions
            _,audit=coherent_safe_actions(case['airport'],view,raw)
            unsafe+=int(str(selected) in audit['rejected'] and not audit['fallback'])
            bonus_rolls+=int(env.actions[selected].kind=='bonus_roll')
            env.step(selected);decisions+=1
        won=env.game.status=='gewonnen'
        if trace:
            final=env.game.zustand()
            trace[-1].update(actual_movement=trace[-1]['distance']-env.game.landung.entfernung,
                new_gear=sum(final['fahrwerk_ausgefahren'])-trace[-1]['gear_done'],
                new_flaps=sum(final['landeklappen_ausgefahren'])-trace[-1]['flaps_done'])
        if rows:rows[-1].update(next_phi=0.,next_value=0.)
        for i,row in enumerate(rows):
            outcome=(1. if won else -1.) if i==len(rows)-1 else 0.
            row['return']=(1. if won else -1.)-row['phi']
            row['td_advantage']=outcome+row['next_phi']-row['phi']+row['next_value']-row['value']
        return rows,env.episode_record(seed,'both',1. if won else -1.) | dict(round_plans=trace,case=case_key(case),won=won,status=env.game.status,rounds=env.game.aktuelle_runde,decisions=decisions,truncated=env.truncated,avoidable_immediate_losses=unsafe,public_goal_violations=goal_violations,strategy_overrides=sum(not p['expert_option'] for p in trace),synchronisation_rolls=bonus_rolls,paired_new_upgrade_rounds=sum(p['new_gear']>0 and p['new_flaps']>0 for p in trace),unpaired_new_flaps=sum(max(0,p['new_flaps']-int(p['new_gear']>0)) for p in trace),unpaired_new_gears=sum(max(0,p['new_gear']-int(p['new_flaps']>0)) for p in trace),seconds=time.monotonic()-started)
    finally:bridge._spiel=None


def update(actor,optimizer,rows):
    x=torch.tensor([r['x'] for r in rows]);mask=torch.tensor([r['mask'] for r in rows]);prior=torch.tensor([r['prior'] for r in rows]);actions=torch.tensor([r['actions'] for r in rows]);oldlogp=torch.tensor([r['logp'] for r in rows]);returns=torch.tensor([r['return'] for r in rows]);oldv=torch.tensor([r['value'] for r in rows]);adv=torch.tensor([r.get('advantage',r['return']-r['value']) for r in rows]);adv=adv/adv.square().mean().sqrt().clamp_min(.02)
    importance=torch.tensor([math.exp(r['logp']-r.get('behavior_logp',r['logp'])) for r in rows]).clamp(max=5.)
    policy_weight=torch.tensor([r.get('policy_weight',1.) for r in rows]);normalizer=policy_weight.sum().clamp_min(1.)
    for _ in range(6):
        out=actor(x);p=(out[:,:OUTPUTS]+prior).masked_fill(~mask,-1e9);logp=0.;entropy=0.
        for head,(a,b) in enumerate(zip(OFFSETS,OFFSETS[1:])):
            dist=torch.distributions.Categorical(logits=p[:,a:b]);logp=logp+dist.log_prob(actions[:,head]);entropy=entropy+dist.entropy()
        ratio=(logp-oldlogp).exp();policy=-(torch.minimum(ratio*adv,ratio.clamp(.8,1.2)*adv)*policy_weight*importance).sum()/normalizer
        loss=policy+.5*(out[:,-1]-returns).square().mean()-.015*(entropy*policy_weight).sum()/normalizer+.002*out[:,:OUTPUTS].square().mean()
        optimizer.zero_grad();loss.backward();nn.utils.clip_grad_norm_(actor.parameters(),.5);optimizer.step()
    actor.training_updates+=1
    return {'loss':float(loss.detach()),'policy_loss':float(policy.detach()),'mean_return':float(returns.mean()),'rounds':len(rows),'explored_rounds':int(policy_weight.sum()),'sampled_nonzero_advantages':sum(r.get('advantage',0.)!=0 for r in rows)}


_worker_model=None

def initialize_worker(checkpoint):
    global _worker_model
    torch.set_num_threads(1);_worker_model=load_checkpoint(checkpoint)[0]


def collect_pair(task):
    index,case,seed,state=task
    torch.manual_seed(int(hashlib.sha256(seed.encode()).hexdigest()[:8],16))
    actor=RoundActor();actor.load_state_dict({name:torch.tensor(values) for name,values in state.items()})
    control_rows,control=play(_worker_model,case,seed,actor=actor,stochastic=False)
    candidates=[(row['round'],[h for h,(a,b) in enumerate(zip(OFFSETS,OFFSETS[1:])) if sum(row['mask'][a:b])>1]) for row in control_rows]
    candidates=[(round_id,heads) for round_id,heads in candidates if heads]
    exploration=random.Random(seed+':reachable-exploration')
    round_id,heads=exploration.choice(candidates);head=exploration.choice(heads)
    rows,record=play(_worker_model,case,seed,actor=actor,stochastic=True,single_exploration=True,exploration_choice=(round_id,head))
    record['explored_round']=round_id;record['explored_head']=HEADS[head][0]
    advantage=float(record['won'])-float(control['won'])
    controls={row['round']:row for row in control_rows}
    for row in rows:
        row['advantage']=(row['td_advantage']-controls[row['round']]['td_advantage']+2*advantage) if row['policy_weight'] else 0.
    record['sampled_learning_advantages']=[row['advantage'] for row in rows if row['policy_weight']]
    record['greedy_control']=control;record['paired_advantage']=advantage;record['ordinal']=index
    return index,rows,record


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['train','evaluate']);p.add_argument('--output',type=Path,required=True);p.add_argument('--episodes',type=int,default=126);p.add_argument('--batch',type=int,default=21);p.add_argument('--workers',type=int,default=8);p.add_argument('--weights',type=Path);p.add_argument('--warm-start',type=Path);p.add_argument('--cohort',required=True);p.add_argument('--checkpoint',type=Path,default=Path('ai/releases/crew6-abilities-2026-10-28-v1/best.pt'));args=p.parse_args()
    torch.set_num_threads(1);torch.manual_seed(282026);rng=random.Random(args.cohort)
    if args.output.exists():raise ValueError('Use a fresh output path.')
    cases=[c for c in sorted(catalogue_cases(),key=case_key) if c['airport'].startswith('LOG_')]
    routes=sorted({c['airport'] for c in cases});byroute={r:[c for c in cases if c['airport']==r] for r in routes}
    model,payload=load_checkpoint(args.checkpoint);summary=dict(format=7,potential_shaping='Phi(next)-Phi(now), terminal Phi=0; gamma=1; critic target outcome-Phi(now); paired TD plus paired terminal outcome',exploration='paired whole-game control; one goal in one round varied; only sampled actions enter PPO, all other rows are critic-only',mode=args.mode,cohort=args.cohort,complete=False,base_terminal_reward_only=True,clock_model='engine_wall_clock' if args.mode=='evaluate' else 'frozen_training_clock',public_features=list(FEATURES),low_level_sha256=execution_fingerprint(),baseline_low_level_sha256=policy_fingerprint(),execution_policy="briefing-v2",blueprint_sha256=weight_fingerprint(model),episodes=[],updates=[])
    if args.mode=='train':
        if not args.cohort.startswith('training:'):raise ValueError('Training namespace required.')
        actor=RoundActor()
        if args.warm_start:
            load_actor_weights(actor,json.loads(args.warm_start.read_text()))
            summary['warm_start']={'path':str(args.warm_start),'sha256':hashlib.sha256(args.warm_start.read_bytes()).hexdigest(),'actor_transfer':'full actor' if json.loads(args.warm_start.read_text()).get('format')==FORMAT else 'public encoder only; new actor head reset to expert option','critic':'reset to zero','optimizer':'new Adam state'}
        summary['exploration']='Greedy control first; uniformly select one actually reached round and a head with alternatives. Only that sampled head enters PPO; deterministic rows are critic-only.'
        optimizer=torch.optim.Adam(actor.parameters(),lr=.002);route_order=list(routes)
        atomic(args.output.with_name(args.output.stem+'-0000-weights.json'),actor.portable())
        if not 1<=args.workers<=8:raise ValueError('Use 1..8 worker processes.')
        with ProcessPoolExecutor(max_workers=args.workers,mp_context=multiprocessing.get_context('spawn'),initializer=initialize_worker,initargs=(str(args.checkpoint),)) as pool:
            for start in range(0,args.episodes,args.batch):
                state={name:t.detach().tolist() for name,t in actor.state_dict().items()};tasks=[];completed={};previous=list(summary['episodes'])
                for i in range(start,min(start+args.batch,args.episodes)):
                    if i%len(routes)==0:rng.shuffle(route_order)
                    case=rng.choice(byroute[route_order[i%len(routes)]]);seed=f'{args.cohort}:{case_key(case)}:{i}'
                    tasks.append((i,case,seed,state))
                futures=[pool.submit(collect_pair,task) for task in tasks]
                for future in as_completed(futures):
                    i,rows,record=future.result();completed[i]=(rows,record)
                    summary['episodes']=previous+[completed[k][1] for k in sorted(completed)];atomic(args.output,summary)
                    print(json.dumps({'episode':i+1,'case':record['case'],'won':record['won'],'greedy_won':record['greedy_control']['won'],'paired_advantage':record['paired_advantage'],'learning_signal':record['sampled_learning_advantages'],'seconds':record['seconds']+record['greedy_control']['seconds']}),flush=True)
                batch=[row for i in sorted(completed) for row in completed[i][0]]
                stats=update(actor,optimizer,batch);stats['episodes']=len(summary['episodes']);summary['updates'].append(stats)
                target=args.output.with_name(args.output.stem+f'-{len(summary["episodes"]):04d}-weights.json');atomic(target,actor.portable());summary['latest_weights']=str(target);atomic(args.output,summary)

    else:
        if not args.cohort.startswith(('development:','confirmation:')) or args.weights is None:raise ValueError('Independent evaluation namespace and fixed weights required.')
        weights=json.loads(args.weights.read_text());summary['weights_sha256']=hashlib.sha256(args.weights.read_bytes()).hexdigest();summary['qualification_rule']='Learned beats default by at least 3 wins, does not lose to autonomous; no illegal actions, avoidable immediate losses or step truncations. No tuning on confirmation.'
        for i in range(args.episodes):
            options=byroute[routes[i%len(routes)]];preferred=sorted(options,key=lambda c:('synchronisation' not in c['abilities'],'control' not in c['abilities'],case_key(c)));case=preferred[(i//len(routes))%len(preferred)]
            seed=f'{args.cohort}:{case_key(case)}:{i}'
            for mode in ('default','learned','autonomous'):
                _,record=play(model,case,seed,weights=weights if mode=='learned' else None,mode=mode,wall_clock=True);record['mode']=mode;summary['episodes'].append(record);atomic(args.output,summary);print(json.dumps(record),flush=True)
        totals={mode:sum(r['won'] for r in summary['episodes'] if r['mode']==mode) for mode in ('default','learned','autonomous')};summary['wins']=totals;summary['qualification_granted']=totals['learned']>=totals['default']+3 and totals['learned']>=totals['autonomous'] and all(not r['truncated'] and not r['avoidable_immediate_losses'] for r in summary['episodes'])
    summary['complete']=True;atomic(args.output,summary)


if __name__=='__main__':main()
