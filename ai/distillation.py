"""Distill observation-only TRAINING plans into the existing residual network.

Accept equivalent target actions rather than teaching arbitrary die indices.
Hold out whole training episodes. No development/qualification games become
labels, and held-out imitation accuracy is never called playing strength.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import time

import torch

from .checkpoints import load_checkpoint, save_checkpoint, weight_fingerprint
from .train_robust import load_teacher


def target_loss(logits,allowed,targets,weights):
    if (logits.ndim!=2 or allowed.shape!=logits.shape or targets.shape!=logits.shape
            or weights.shape!=(logits.shape[0],) or not allowed.any(-1).all()
            or not targets.any(-1).all() or (targets&~allowed).any()
            or not torch.isfinite(weights).all() or not (weights>0).all()):
        raise ValueError('Every row needs finite positive weight and nonempty legal target set.')
    logp=torch.log_softmax(logits.masked_fill(~allowed,-torch.inf),dim=-1)
    row_loss=-torch.logsumexp(logp.masked_fill(~targets,-torch.inf),dim=-1)
    return (row_loss*weights).sum()/weights.sum()


def episode_split(payload):
    episodes=payload['episodes']
    if len(episodes)<10:
        raise ValueError('At least ten complete training episodes are required.')
    train,validation=[],[]
    offset=0
    for episode in episodes:
        if not str(episode.get('seed','')).startswith('train:'):
            raise ValueError('Every episode must have its own explicit training namespace.')
        digest=int(hashlib.sha256(episode['seed'].encode()).hexdigest()[:8],16)
        target=validation if digest%5==0 else train
        target.extend(range(offset,offset+episode['decisions']))
        offset+=episode['decisions']
    if offset!=payload['decisions'] or not train or not validation:
        raise ValueError('Whole-episode split did not cover the recorded decisions.')
    return torch.tensor(train),torch.tensor(validation)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',default='ai/releases/crew4-allroutes-2026-10-26-v1/best.pt')
    p.add_argument('--demonstrations',type=Path,required=True)
    p.add_argument('--run-dir',type=Path,required=True)
    p.add_argument('--epochs',type=int,default=50)
    p.add_argument('--seconds',type=float,default=1200.)
    p.add_argument('--batch-size',type=int,default=256)
    p.add_argument('--learning-rate',type=float,default=1e-4)
    p.add_argument('--seed',type=int,default=281401)
    p.add_argument('--dice-augmentation',action='store_true')
    args=p.parse_args()
    if (args.run_dir.exists() or not 1<=args.epochs<=1000 or not 0<args.seconds<=7200
            or not 1<=args.batch_size<=4096 or not math.isfinite(args.learning_rate)
            or not 0<args.learning_rate<=.01):
        p.error('Use a new folder and bounded training parameters.')
    if Path('runs/STOP_AI_TRAINING').exists():
        p.error('Persistent training stop is active.')
    torch.set_num_threads(1);torch.manual_seed(args.seed)
    payload=load_teacher(args.demonstrations)
    data=payload['data'];targets=data['target_masks']
    if targets.dtype!=torch.bool or targets.shape!=data['masks'].shape:
        raise ValueError('Expected Boolean equivalent-action target masks.')
    target_loss(torch.zeros_like(data['masks'],dtype=torch.float),data['masks'],targets,data['weights'])
    train,validation=episode_split(payload)
    model,source_payload=load_checkpoint(args.source)
    initial_sha=weight_fingerprint(model)
    if initial_sha!=payload['source_weights_sha256']:
        raise ValueError('Teacher and student must start from the recorded same source.')
    frozen_sha=weight_fingerprint(model.source)
    optimizer=torch.optim.Adam((x for x in model.parameters() if x.requires_grad),lr=args.learning_rate,eps=1e-5)
    config=dict(phase_kind='observation_only_search_distillation',source_checkpoint=args.source,
        initial_weights_sha256=initial_sha,frozen_source_weights_sha256=frozen_sha,
        demonstrations=str(args.demonstrations),data_file_sha256=hashlib.sha256(args.demonstrations.read_bytes()).hexdigest(),
        collector_sha256=payload['collector_sha256'],training_seed_namespace=payload['training_seed_namespace'],
        training_rows=len(train),validation_rows=len(validation),validation_unit='whole_training_episode',
        seconds=args.seconds,epochs=args.epochs,learning_rate=args.learning_rate,batch_size=args.batch_size,
        seed=args.seed,policy='research_coherent_with_profile12_reference',release_evidence=False,
        dice_augmentation=args.dice_augmentation,
        new_environment_decisions=0,teacher_environment_decisions=payload['decisions'])
    args.run_dir.mkdir(parents=True)
    (args.run_dir/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    history=[];seen=0;best=math.inf;start=time.monotonic()

    def save(name,epoch):
        if weight_fingerprint(model.source)!=frozen_sha:
            raise RuntimeError('Frozen inherited source changed.')
        save_checkpoint(args.run_dir/name,model,train_config=config,
            total_steps=source_payload.get('total_steps',0),imitation_rows_seen=seen,imitation_epoch=epoch)

    def evaluate(indices):
        model.eval();loss_sum=mass=correct=0.
        with torch.no_grad():
            for chosen in indices.split(args.batch_size):
                logits,_=model.policy_output(data['observations'][chosen],reference_mask=data['reference_masks'][chosen])
                weight=data['weights'][chosen]
                loss=target_loss(logits,data['masks'][chosen],targets[chosen],weight)
                predicted=logits.masked_fill(~data['masks'][chosen],-torch.inf).argmax(-1)
                correct+=targets[chosen].gather(1,predicted[:,None]).sum().item()
                loss_sum+=loss.item()*weight.sum().item();mass+=weight.sum().item()
        return dict(loss=loss_sum/mass,target_accuracy=correct/len(indices))

    initial=evaluate(validation);save('initial.pt',0)
    history.append(dict(epoch=0,validation=initial,rows_seen=0,seconds=time.monotonic()-start))
    best=initial['loss'];save('best.pt',0)
    print(json.dumps(history[-1]),flush=True)
    for epoch in range(1,args.epochs+1):
        model.train()
        order=train[torch.randperm(len(train))]
        for chosen in order.split(args.batch_size):
            if time.monotonic()-start>=args.seconds or Path('runs/STOP_AI_TRAINING').exists():break
            batch={name:values[chosen] for name,values in data.items()}
            if args.dice_augmentation:
                from .dice_symmetry import permute_rows
                batch=permute_rows(batch,torch.randint(24,(len(chosen),)))
            logits,_=model.policy_output(batch['observations'],reference_mask=batch['reference_masks'])
            loss=target_loss(logits,batch['masks'],batch['target_masks'],batch['weights'])
            optimizer.zero_grad();loss.backward()
            torch.nn.utils.clip_grad_norm_((p for p in model.parameters() if p.requires_grad),1.)
            optimizer.step();seen+=len(chosen)
        row=dict(epoch=epoch,validation=evaluate(validation),rows_seen=seen,seconds=time.monotonic()-start)
        history.append(row)
        if row['validation']['loss']<best:
            best=row['validation']['loss'];save('best.pt',epoch)
        save('latest.pt',epoch)
        (args.run_dir/'history.json').write_text(json.dumps(history,indent=2)+'\n')
        print(json.dumps(row),flush=True)
        if time.monotonic()-start>=args.seconds or Path('runs/STOP_AI_TRAINING').exists():break
    (args.run_dir/'report.json').write_text(json.dumps(dict(complete=True,release_evidence=False,
        initial_weights_sha256=initial_sha,latest_weights_sha256=weight_fingerprint(model),
        rows_seen=seen,history=history,total_wall_seconds=time.monotonic()-start),indent=2)+'\n')


if __name__=='__main__':
    main()
