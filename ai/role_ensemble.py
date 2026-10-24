"""Build a resumable candidate from independently trained role specialists."""
import argparse
from pathlib import Path

import torch

from .checkpoints import load_checkpoint,save_checkpoint,weight_fingerprint,planner_fingerprint
from .nn_model import RoleActorCritic


def combine(pilot,kopilot,output):
    models,payloads,sources={},{},{}
    for role,path,profile in [('pilot',pilot,4),('kopilot',kopilot,3)]:
        model,payload=load_checkpoint(path)
        if payload['train_config'].get('assistance_version',0)!=profile:
            raise ValueError(f'{role} requires assistance profile {profile}.')
        models[role],payloads[role]=model,payload
        sources[role]={'checkpoint':str(path),'weights_sha256':weight_fingerprint(model),
                       'steps':payload['total_steps'],'assistance_version':profile}
    model=RoleActorCritic(models['pilot'],models['kopilot'])
    original=payloads['pilot']
    config={k:v for k,v in original['train_config'].items() if k not in
            ('quality','display_name','recommended','supported_airports')}
    config.update(assistance_version=6,role_sources=sources,planner_sha256=planner_fingerprint(),
                  run_dir=str(Path(output).parent),training_kind='role_ensemble')
    optimizer=torch.optim.Adam(model.parameters(),lr=config.get('lr',3e-4),eps=1e-5)
    # Fresh optimizer: buffers of one source cannot be assigned to two heads.
    save_checkpoint(output,model,optimizer_state=optimizer.state_dict(),train_config=config,
        total_steps=max(p['total_steps'] for p in payloads.values()),episodes=original['episodes'],
        update=original['update'],best_score=[-1.0]*5,best_score_version=2,
        torch_rng_state=original['torch_rng_state'].cpu())
    return model


def main():
    torch.set_num_threads(1)
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pilot',type=Path,required=True)
    p.add_argument('--kopilot',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    combine(args.pilot,args.kopilot,args.output)
    print(args.output)


if __name__=='__main__':
    main()
