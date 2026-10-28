import base64
import json
from pathlib import Path
import shutil
import struct
import subprocess
import unittest


@unittest.skipUnless(shutil.which('node'),'Node required for browser arbitration parity')
class PublicContractJsTests(unittest.TestCase):
    def test_browser_uses_the_same_explicit_plan_rule_and_keeps_it_first_in_rank(self):
        schema=dict(features=['test'],actions=[{}, {}, {}])
        encode=lambda values:base64.b64encode(struct.pack('<'+len(values)*'f',*values)).decode()
        model=dict(format=1,schema=schema,layers=[dict(input=1,output=3,weight=encode([0,0,0]),bias=encode([5,3,0]))])
        decision=dict(observation=[0],action_mask=[True]*3)
        plan=dict(version=1,baseline_mask=[True,True,False],scores={'0':1.,'1':5.},
                  best_action=1,forced_action=None,tolerance=1.)
        cases=[decision,{**decision,'public_plan':plan},
               {**decision,'public_plan':{**plan,'forced_action':2}},
               {**decision,'public_plan':{**plan,'scores':{'0':4.5,'1':5.}}}]
        code="""const fs=require('node:fs');global.window={};eval(fs.readFileSync(process.argv[1],'utf8'));
const f=JSON.parse(fs.readFileSync(0,'utf8')),p=window.CockpitPolicy.create(f.model,{schema:f.model.schema});
const result=f.cases.map(d=>({chosen:p.select(d),first:p.rank(d)[0]}));
const pyodideNone=p.select({...f.cases[1],public_plan:{...f.cases[1].public_plan,forced_action:undefined}});
let rejected=0;for(const patch of [{forced_action:99},{baseline_mask:[false,false,false]},{scores:5}]){
 try{p.select({...f.cases[1],public_plan:{...f.cases[1].public_plan,...patch}})}catch(e){rejected++}}
process.stdout.write(JSON.stringify({result,rejected,pyodideNone}));
"""
        script=Path(__file__).resolve().parents[1]/'frontend/web/js/ai-policy.js'
        result=subprocess.run(['node','-e',code,str(script)],input=json.dumps(dict(model=model,cases=cases)),
                              capture_output=True,text=True,check=True)
        actual=json.loads(result.stdout)
        self.assertEqual([0,1,2,0],[row['chosen'] for row in actual['result']])
        self.assertTrue(all(row['chosen']==row['first'] for row in actual['result']))
        self.assertEqual(3,actual['rejected'])
        self.assertEqual(1,actual['pyodideNone'])
