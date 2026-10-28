"""Native/WASM parity for public goals and synthetic agent-own action inputs."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import torch
from ai.briefing import PUBLIC_KEYS
from ai.modules import ModuleEnv
from ai.preview_matrix_eval import catalogue_cases
from ai.module_training_eval import case_key
from ai.round_strategy import choose,logits,encode,OUTPUTS
from ai.round_strategy_training import RoundActor,sample,load_actor_weights

PUBLIC_INPUT_KEYS=PUBLIC_KEYS+('status','aerodynamik_blau','aerodynamik_orange',
    'neuwurf_plaettchen','flugzeugwuerfel','kurven_min','kurven_max','praktikant')


def action_rollouts(weights):
    from backend import bridge
    from ai.briefing_browser_v2 import decision
    from ai.checkpoints import load_checkpoint
    from ai.agents import ModelAgent
    from ai.public_contract import arbitrate_contract
    model,_=load_checkpoint('ai/releases/crew6-abilities-2026-10-28-v1/best.pt')
    agent=ModelAgent(model);cases=[]
    for airport,cards in [('LOG_YUL_GREEN',[]),('LOG_KUL_YELLOW',['synchronisation']),('LOG_GIG_YELLOW',['control'])]:
        seed='wasm-action-parity:'+airport+':'+','.join(cards)
        env=ModuleEnv(airport,abilities=cards,clock=lambda:0.)
        env.reset(seed=seed);steps=[];round_id=None;plan=None
        try:
            for _ in range(12):
                if env.done:break
                if round_id!=env.game.aktuelle_runde:
                    round_id=env.game.aktuelle_runde;plan=choose(env.game.zustand(),weights)
                bridge._spiel=env.game
                d=decision(reroll_json=json.dumps(env.reroll),steps=env.steps,assistance_version=15,schema_version=3,plan_json=json.dumps(plan))
                baseline=agent.select(env.view(),d['public_plan']['baseline_mask'],reference_mask=d.get('reference_action_mask'))
                selected=arbitrate_contract(baseline,d['action_mask'],d['public_plan'])
                steps.append({'expected':selected,'observation':d['observation'],'action_mask':d['action_mask'],
                              'reference_action_mask':d['reference_action_mask'],'baseline_mask':d['public_plan']['baseline_mask']})
                env.step(selected)
        finally:bridge._spiel=None
        cases.append({'airport':airport,'cards':cards,'seed':seed,'steps':steps})
    return cases


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--weights',type=Path,required=True)
    parser.add_argument('--development',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    raw=args.weights.read_bytes();weights=json.loads(raw)
    torch.set_num_threads(1);actor=RoundActor();load_actor_weights(actor,weights)
    states=[];maximum_torch_error=0.

    def compare_logits(x):
        nonlocal maximum_torch_error
        with torch.no_grad():native=actor(torch.tensor(x)).tolist()[:OUTPUTS]
        portable=logits(x,weights)
        maximum_torch_error=max(maximum_torch_error,max(abs(a-b) for a,b in zip(native,portable)))
        return portable

    def add(case,state,kind):
        public={key:copy.deepcopy(state[key]) for key in PUBLIC_INPUT_KEYS}
        assert 'pilot_wuerfel' not in public and 'kopilot_wuerfel' not in public
        expected=choose(public,weights)
        with torch.no_grad():assert sample(actor,public,False)[0]==expected,case
        compare_logits(encode(public))
        states.append({'case':case,'kind':kind,'state':public,'expected':expected})
        return expected

    for case in sorted(catalogue_cases(),key=case_key):
        env=ModuleEnv(case['airport'],abilities=case['abilities'],clock=lambda:0.)
        env.reset(seed='parity:public-round:'+case_key(case))
        add(case_key(case),env.game.zustand(),'native-initial')

    yul=next(row['state'] for row in states if row['case']=='LOG_YUL_GREEN|')
    for distance,height in [(2,1000),(4,2000),(6,3000)]:
        state={**copy.deepcopy(yul),'entfernung':distance,'hoehe':height,
               'runde':7-height//1000,'letzte_runde':False,'warteschleife':False,
               'flugzeuge':[0]*len(yul['flugzeuge'])}
        plan=add(f'necessary-pace-{distance}-{height}',state,'public-constraint-scenario')
        assert plan['movement_preference'] in (2,None)
    state={**copy.deepcopy(yul),'entfernung':2,'hoehe':2000,'runde':5,
           'fahrwerk_ausgefahren':[True]*3,'landeklappen_ausgefahren':[True]*4,
           'aerodynamik_blau':7.5,'aerodynamik_orange':12.5,
           'flugzeuge':[0]*len(yul['flugzeuge'])}
    assert add('irreversible-one-field-limit',state,'public-constraint-scenario')['movement_preference'] in (1,None)
    source=next(row['state'] for row in states if 'synchronisation' in row['state']['faehigkeitskarten'])
    state={**copy.deepcopy(source),'fahrwerk_ausgefahren':[True]*3,
           'landeklappen_ausgefahren':[True]*3+[False],'aerodynamik_blau':7.5,
           'aerodynamik_orange':11.5}
    assert add('extra-copilot-flap',state,'public-constraint-scenario')['coordination']!='synchronisation'

    report=json.loads(args.development.read_text())
    vectors=[row['public_features'] for record in report['records'] for row in record['round_plans']]
    vectors=vectors[::max(1,len(vectors)//400)][:400]
    numeric=[{'x':x,'expected':compare_logits(x)} for x in vectors]
    assert maximum_torch_error<1e-6,maximum_torch_error
    catalog=json.loads(Path('frontend/web/js/ai-models.js').read_text().split(' = ',1)[1].rstrip(';\n'))
    browser_model=next(m for m in catalog['models'] if m.get('assistance_version')==15 and not m.get('ui_hidden'))
    browser_bytes=(Path('frontend/web')/browser_model['url']).read_bytes()
    actions=action_rollouts(weights)
    data={'action_cases':actions,'browser_weights_url':browser_model['url'],
          'browser_weights_sha256':hashlib.sha256(browser_bytes).hexdigest(),'browser_schema':browser_model['schema'],
          'maximum_torch_error':maximum_torch_error,
          'weights_sha256':hashlib.sha256(raw).hexdigest(),'states':states,'vectors':numeric}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(data,separators=(',',':'))+'\n')
    print(json.dumps({'native_states':sum(row['kind']=='native-initial' for row in states),
                      'public_constraint_scenarios':sum(row['kind']=='public-constraint-scenario' for row in states),
                      'vectors':len(vectors),'bytes':args.output.stat().st_size,
                      'maximum_torch_error':maximum_torch_error,'native_action_decisions':sum(len(case['steps']) for case in actions)}))


if __name__=='__main__':main()
