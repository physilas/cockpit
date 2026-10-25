"""Learn public rule representations from engine-checked synthetic exercises.

Only the new residual encoder and a temporary legality head learn here. The
policy/value correction heads remain zero, preserving the inherited player.
Legality accuracy is NOT a win rate. PPO must still learn successful play.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import math
import hashlib
import multiprocessing
from pathlib import Path
import random

import torch
from torch import nn

from .checkpoints import load_checkpoint,save_checkpoint,weight_fingerprint,planner_fingerprint
from .fuel import fuel_encode
from .modules import ModuleEnv,MODULE_FEATURES,MODULE_ACTIONS
from .nn_model import ResidualActorCritic
from .throttle import CpuBudget

ROOT=Path(__file__).resolve().parents[1]


EFFECTS=('attitude','wind','wind_sin','wind_cos','fuel','ice','intern','gear','flaps','brakes','coffee','distance','height','speed','outcome')


def public_effect(env):
    view=env.view();state=view['modules_state'];board=view['board']
    speed=(board[2]['value']+board[3]['value']+state['wind_value'])/15 if board[2] and board[3] else 0
    angle=2*math.pi*state['wind_position']/18
    return [view['attitude']/3,state['wind_value']/3,math.sin(angle),math.cos(angle),view['fuel']['remaining']/20,
            state['ice_progress']/4,len(state['intern'])/6,sum(view['gear'])/3,sum(view['flaps'])/4,
            view['brakes']/6,view['coffee']/3,view['distance']/32,view['height']/6000,speed,
            1. if env.game.status=='gewonnen' else -1. if env.game.status=='verloren' else 0.]


def public_exercises(task):
    cases,fixtures,namespace,schema_version,duty=task
    torch.set_num_threads(1)
    budget=CpuBudget(duty)
    observations=[];masks=[];actions=[];effects=[]
    for case in cases:
        key=case['airport']+':'+','.join(case['abilities'])
        for index in range(fixtures):
            rng=random.Random(f'{namespace}:{key}:{index}')
            env=ModuleEnv(case['airport'],abilities=case['abilities'],clock=lambda:0)
            env.reset(seed=f'{namespace}:{key}:{index}')
            c,z=env.game.cockpit,env.game.zusatz
            # Explicit rule exercises, not claimed winning trajectories. Marker
            # combinations vary to teach sequential fields and module effects.
            gears=rng.randrange(4);flaps=rng.randrange(5);brakes=rng.randrange(4)
            c.fahrwerk_ausgefahren=[i<gears for i in range(3)]
            c.landeklappen_ausgefahren=[i<flaps for i in range(4)]
            c.bremsen_aktiviert=[i<brakes for i in range(3)]
            c.aerodynamik_blau+=gears;c.aerodynamik_orange+=flaps
            if c.kerosin is not None:c.kerosin=rng.randrange(1,21)
            c.wind_position=rng.randrange(18) if 'wind' in c.module else 0
            c.eis_fortschritt=rng.randrange(5) if 'ice' in c.module else 0
            if z.praktikant:z.praktikant=z.praktikant[rng.randrange(7):]
            modes=['random','rudder','thrust']
            if 'kerosene' in c.module and 'leak' not in c.module:modes.append('fuel')
            if 'ice' in c.module:modes.append('ice')
            if 'intern' in c.module:modes.append('intern')
            mode=modes[index%len(modes)]
            forced=None
            if mode in ('rudder','thrust'):
                target='ruder' if mode=='rudder' else 'triebwerk'
                own=env.game.pilot_wuerfel[0].augenzahl
                other=rng.choice(list(range(max(1,own-2),min(6,own+2)+1))) if mode=='rudder' else rng.randrange(1,7)
                env.game.am_zug='kopilot';env.game.kopilot_wuerfel[0].augenzahl=other
                result=env.game.platziere('kopilot',0,target)
                if not result.erfolg:raise RuntimeError(result.grund)
                forced=next(i for i,a in enumerate(MODULE_ACTIONS) if a.kind=='place' and a.die==0
                            and env.slots[a.slot].target==target and env.slots[a.slot].owner=='pilot')
            elif mode=='fuel':
                forced=121
            elif mode=='ice':
                c.eis_fortschritt=rng.randrange(4)
                col=c.eis_fortschritt;face=col+2
                env.game.am_zug='pilot';env.game.pilot_wuerfel[0].augenzahl=face
                result=env.game.platziere('pilot',0,'eisbremse',index=col*2)
                if not result.erfolg:raise RuntimeError(result.grund)
                env.game.kopilot_wuerfel[0].augenzahl=face
                forced=next(i for i,a in enumerate(MODULE_ACTIONS) if a.kind=='place' and a.die==0
                            and env.slots[a.slot].target=='eisbremse' and env.slots[a.slot].index==col*2+1)
            elif mode=='intern':
                if not z.praktikant:z.praktikant=[rng.randrange(1,7)]
                env.game.pilot_wuerfel[0].augenzahl=z.praktikant[0]%6+1
                forced=next(i for i,a in enumerate(MODULE_ACTIONS) if a.kind=='place' and a.die==0
                            and env.slots[a.slot].target=='training' and env.slots[a.slot].owner=='pilot')
            for step in range(12):
                if env.done:break
                view=env.view();mask=env.action_mask()
                observations.append(fuel_encode(view) if schema_version==2 else env.observation())
                masks.append(mask[:125] if schema_version==2 else mask)
                legal=[i for i,ok in enumerate(mask) if ok]
                placements=[i for i in legal if MODULE_ACTIONS[i].kind in ('place','bonus_place')]
                action=forced if step==0 and forced is not None and mask[forced] else rng.choice(placements if placements and rng.random()<.7 else legal)
                before=public_effect(env)
                env.step(action)
                actions.append(action);effects.append([a-b for a,b in zip(public_effect(env),before)])
                budget.pause()
    return observations,masks,actions,effects


def collect(cases,fixtures,namespace,schema_version,workers,duty):
    tasks=[(cases[i:i+8],fixtures,namespace,schema_version,duty) for i in range(0,len(cases),8)]
    with ProcessPoolExecutor(workers,mp_context=multiprocessing.get_context('spawn')) as pool:
        chunks=list(pool.map(public_exercises,tasks))
    observations=[v for chunk in chunks for v in chunk[0]]
    masks=[v for chunk in chunks for v in chunk[1]]
    actions=[v for chunk in chunks for v in chunk[2]]
    effects=[v for chunk in chunks for v in chunk[3]]
    return (torch.tensor(observations,dtype=torch.float32),torch.tensor(masks,dtype=torch.float32),
            torch.tensor(actions,dtype=torch.long),torch.tensor(effects,dtype=torch.float32))


def metrics(encoder,head,data,device):
    correct_positive=correct_negative=positive=negative=0
    with torch.no_grad():
        for start in range(0,len(data[0]),512):
            x,y=(v[start:start+512].to(device) for v in data[:2])
            prediction=head(encoder(x))>=0;target=y.bool()
            positive+=int(target.sum());negative+=int((~target).sum())
            correct_positive+=int((prediction&target).sum());correct_negative+=int((~prediction&~target).sum())
    recall=correct_positive/max(positive,1);specificity=correct_negative/max(negative,1)
    return {'examples':len(data[0]),'legal_recall':recall,'illegal_specificity':specificity,'balanced_accuracy':(recall+specificity)/2}



def effect_metrics(encoder,head,data,device,action_count):
    errors=[]
    with torch.no_grad():
        for start in range(0,len(data[0]),512):
            x=data[0][start:start+512].to(device)
            actions=nn.functional.one_hot(data[2][start:start+512].to(device),action_count).float()
            predicted=head(torch.cat((encoder(x),actions),dim=1)).cpu()
            errors.append((predicted-data[3][start:start+512]).square())
    mse=torch.cat(errors).mean(dim=0);baseline=data[3].square().mean(dim=0)
    return {'mse':float(mse.mean()),'zero_delta_baseline_mse':float(baseline.mean()),
            'per_public_effect':{name:{'mse':float(a),'zero_delta_baseline_mse':float(b)} for name,a,b in zip(EFFECTS,mse,baseline)}}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--run-dir',type=Path,required=True)
    p.add_argument('--schema',type=int,choices=(2,3),default=3)
    p.add_argument('--fixtures',type=int,default=8)
    p.add_argument('--validation-fixtures',type=int,default=2)
    p.add_argument('--epochs',type=int,default=10)
    p.add_argument('--workers',type=int,default=8)
    p.add_argument('--cpu-duty-cycle',type=float,default=.7)
    p.add_argument('--device',default='mps')
    args=p.parse_args()
    if not 1<=args.workers<=8 or not 0<args.cpu_duty_cycle<=.7 or min(args.fixtures,args.validation_fixtures,args.epochs)<1:p.error('Invalid resource/data budget.')
    if args.run_dir.exists():p.error('Use a new directory.')
    torch.set_num_threads(1);torch.manual_seed(251025)
    matrix=json.loads((ROOT/'ai/experiments/modules-50pct-2026-10-25/matrix.json').read_text())
    cases=matrix['cases'] if args.schema==3 else [c for c in matrix['cases'] if c['airport']=='LOG_OSL_GREEN']
    training=collect(cases,args.fixtures,'rule-train:251025',args.schema,args.workers,args.cpu_duty_cycle)
    validation=collect(cases,args.validation_fixtures,'rule-validation:251025',args.schema,args.workers,args.cpu_duty_cycle)
    source,payload=load_checkpoint(args.source)
    width,actions=(352,125) if args.schema==2 else (len(MODULE_FEATURES),len(MODULE_ACTIONS))
    model=ResidualActorCritic(source,width,actions,hidden_size=256).to(args.device)
    head=nn.Linear(256,actions).to(args.device)
    effect_head=nn.Sequential(nn.Linear(256+actions,256),nn.Tanh(),nn.Linear(256,len(EFFECTS))).to(args.device)
    optimizer=torch.optim.Adam([*model.residual.encoder.parameters(),*head.parameters(),*effect_head.parameters()],lr=1e-3)
    rate=training[1].mean(dim=0).clamp(.02,.98).to(args.device)
    loss_fn=nn.BCEWithLogitsLoss(pos_weight=(1-rate)/rate)
    effect_scale=training[3].std(dim=0).clamp_min(.05).to(args.device)
    initial_effects=effect_metrics(model.residual.encoder,effect_head,validation,args.device,actions)
    initial=metrics(model.residual.encoder,head,validation,args.device)
    for epoch in range(args.epochs):
        order=torch.randperm(len(training[0]))
        for indices in order.split(256):
            x,y=(v[indices].to(args.device) for v in training[:2])
            embedding=model.residual.encoder(x)
            action_inputs=nn.functional.one_hot(training[2][indices].to(args.device),actions).float()
            predicted=effect_head(torch.cat((embedding,action_inputs),dim=1))
            effect_loss=((predicted-training[3][indices].to(args.device))/effect_scale).square().mean()
            loss=loss_fn(head(embedding),y)+.2*effect_loss
            optimizer.zero_grad();loss.backward();optimizer.step()
        print(json.dumps({'epoch':epoch+1,**metrics(model.residual.encoder,head,validation,args.device)}),flush=True)
    report={'format':1,'date':'2026-10-25','schema':args.schema,'cases':len(cases),'training_examples':len(training[0]),
            'initial':initial,'validation':metrics(model.residual.encoder,head,validation,args.device),
            'meaning':'Rule legality and public action-consequence representations; not a win rate and not PPO training.',
            'initial_public_effects':initial_effects,'public_effects':effect_metrics(model.residual.encoder,effect_head,validation,args.device,actions),
            'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'source_weights_sha256':weight_fingerprint(source)}
    args.run_dir.mkdir(parents=True)
    (args.run_dir/'rule-training.json').write_text(json.dumps(report,indent=2)+'\n')
    config={**payload.get('train_config',{}),'schema_version':args.schema,'rule_pretraining':report,
            'supported_modules':['kerosene','leak','wind','ice','intern','realtime'] if args.schema==3 else ['kerosene'],
            'planner_sha256':planner_fingerprint(args.schema),'quality':None}
    save_checkpoint(args.run_dir/'rules.pt',model,train_config=config,total_steps=0,
        module_training_steps=payload.get('module_training_steps',0),rule_pretraining_examples=len(training[0]),
        rule_head_state=head.state_dict(),public_effect_head_state=effect_head.state_dict())
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
