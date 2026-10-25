import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {DatabaseSync} from 'node:sqlite';
import worker from '../cloud/worker.mjs';
const context={window:{}};vm.runInNewContext(fs.readFileSync(new URL('../frontend/web/js/ai-models.js',import.meta.url),'utf8'),context);
const catalog=context.window.COCKPIT_AI_CATALOG,schema=catalog.schema;
const db=new DatabaseSync(':memory:');db.exec(fs.readFileSync(new URL('../cloud/schema.sql',import.meta.url),'utf8'));
let allowed=true, storageFailure=false;
const count=()=>db.prepare('SELECT count(*) AS n FROM training_sessions').get().n;
const env={ALLOWED_ORIGINS:'https://pilot.github.io',UPLOAD_LIMIT:{limit:async()=>({success:allowed})},TRAINING_DB:{
  prepare:sql=>({bind:(...parameters)=>({run:async()=>{
    if(storageFailure) throw new Error('Database quota exceeded');
    db.prepare(sql).run(...parameters);return {success:true};
  }})})
}};
const data={format:'flyteam-learning-session',version:1,schema,session:{id:crypto.randomUUID(),data_revision:1,mode:'examples',status:'active',consent:{version:'2026-10-18',accepted_at:new Date().toISOString()},events:[{actor:'human',action_id:0,decision:{role:'pilot',observation:Array(349).fill(0),action_mask:Array(121).fill(true)}}]}};
const request=(body=data,extra={})=>new Request('https://logs.workers.dev/logs',{method:'POST',headers:{Origin:'https://pilot.github.io','Content-Type':'application/json','X-Upload-Token':'a'.repeat(64),...extra},body:typeof body==='string'?body:JSON.stringify(body)});
assert.equal((await worker.fetch(request(),env)).status,200);assert.equal(count(),1);
data.session.data_revision=3;assert.equal((await worker.fetch(request(),env)).status,200);
data.session.data_revision=2;assert.equal((await worker.fetch(request(),env)).status,200);
assert.equal(JSON.parse(db.prepare('SELECT payload FROM training_sessions').get().payload).session.data_revision,3);
assert.equal((await worker.fetch(request(data,{'X-Upload-Token':'b'.repeat(64)}),env)).status,200);assert.equal(count(),2);
assert.deepEqual(db.prepare('SELECT revision FROM training_sessions ORDER BY revision').all().map(r=>r.revision),[2,3]);
// Use the actual published Crew-2 schema, including its guided-policy mask.
const crew2=catalog.models.find(model=>model.quality?.approved && model.schema?.version===3);
assert.ok(crew2,'Published Crew 2 must supply its schema');
const moduleSchema=JSON.parse(JSON.stringify(crew2.schema));
const feedbackData=selectedSchema=>({format:'flyteam-learning-session',version:1,schema:selectedSchema,session:{
  id:crypto.randomUUID(),data_revision:1,mode:'feedback',status:'active',schema_version:selectedSchema.version,schema:selectedSchema,
  consent:{version:'2026-10-18',accepted_at:new Date().toISOString()},events:[-1,0,1,-2,2].map(value=>({
    actor:'ai',action_id:selectedSchema.actions.length-1,feedback:{value,explicit:value!==0,committed:true},
    decision:{role:'kopilot',observation:Array(selectedSchema.features.length).fill(0),
      action_mask:Array(selectedSchema.actions.length).fill(true),reference_action_mask:Array(selectedSchema.actions.length).fill(false),
      public_state:{board:[{value:3,owner:'pilot'}],partner_remaining:3}},
    public_after:{board:[{value:3,owner:'pilot'}]},
  }))}});
const moduleData=feedbackData(moduleSchema);
assert.equal((await worker.fetch(request(moduleData),env)).status,200);
const storedModule=JSON.parse(db.prepare('SELECT payload FROM training_sessions WHERE session_id=?').get(moduleData.session.id).payload);
assert.deepEqual(storedModule.session.events.map(event=>event.feedback.value),[-1,0,1,-2,2]);
assert.equal(storedModule.schema.version,3);
assert.equal(storedModule.session.events[0].decision.observation.length,489);
assert.equal(storedModule.session.events[0].decision.reference_action_mask.length,217);
// Schema 2 is the registered base+kerosene prefix; legacy schema 1 still works.
const fuelSchema={...moduleSchema,version:2,features:moduleSchema.features.slice(0,352),actions:moduleSchema.actions.slice(0,125)};
assert.equal((await worker.fetch(request(feedbackData(fuelSchema)),env)).status,200);
assert.equal((await worker.fetch(request(feedbackData(JSON.parse(JSON.stringify(schema)))),env)).status,200);
const rejectModule=async mutate=>{
  const invalid=structuredClone(moduleData);mutate(invalid);
  const before=count();assert.equal((await worker.fetch(request(invalid),env)).status,400);assert.equal(count(),before);
};
await rejectModule(input=>{input.schema.version=4;});
await rejectModule(input=>{input.schema.version='3';});
await rejectModule(input=>{input.schema.features=input.schema.features.slice(0,349);});
await rejectModule(input=>{input.schema.actions=input.schema.actions.slice(0,121);});
await rejectModule(input=>{input.schema.features[0]=null;});
await rejectModule(input=>{input.schema.actions[0]={kind:'place',nested:{private:1}};});
await rejectModule(input=>{input.session.schema_version=1;});
await rejectModule(input=>{input.session.schema={...input.schema,features:[...input.schema.features]};input.session.schema.features[0]='other';});
await rejectModule(input=>{input.session.events[0].action_id=217;});
await rejectModule(input=>{input.session.events[0].decision.observation.pop();});
await rejectModule(input=>{input.session.events[0].decision.observation[0]=null;});
await rejectModule(input=>{input.session.events[0].decision.action_mask[0]=1;});
await rejectModule(input=>{input.session.events[0].decision.reference_action_mask.pop();});
await rejectModule(input=>{input.session.events[0].decision.reference_action_mask[0]=1;});
await rejectModule(input=>{input.session.events[0].decision.reference_action_mask[0]=true;input.session.events[0].decision.action_mask[0]=false;});
await rejectModule(input=>{input.session.events[0].decision.public_state.own_dice=[1,2,3,4];});
await rejectModule(input=>{input.session.events[0].public_after.extra={kopilot_wuerfel:[1,2,3,4]};});
assert.equal((await worker.fetch(request(data,{Origin:'https://other.invalid'}),env)).status,403);
assert.equal((await worker.fetch(request(data,{'X-Upload-Token':''}),env)).status,401);
assert.equal((await worker.fetch(request({...data,session:{...data.session,consent:null}}),env)).status,400);
assert.equal((await worker.fetch(request({...data,session:{...data.session,events:[{...data.session.events[0],feedback:{value:3,committed:true}}]}}),env)).status,400);
assert.equal((await worker.fetch(request('not json'),env)).status,400);
assert.equal((await worker.fetch(request('x'.repeat(2*1024*1024+1)),env)).status,413);
assert.equal((await worker.fetch(new Request('https://logs.workers.dev/logs',{headers:{Origin:'https://pilot.github.io'}}),env)).status,405);
allowed=false;assert.equal((await worker.fetch(request(),env)).status,429);
allowed=true;storageFailure=true;assert.equal((await worker.fetch(request(),env)).status,503);
db.close();
console.log('✓ Worker + real SQLite: schemas 1/2/3 and actual Crew-2 thumbs, reference masks, public-hand rejection, private namespaces, atomic revisions, no public read API, consent/schema/size validation, CORS, rate limit and quota errors');
