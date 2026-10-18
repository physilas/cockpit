import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {DatabaseSync} from 'node:sqlite';
import worker from '../cloud/worker.mjs';
const context={window:{}};vm.runInNewContext(fs.readFileSync(new URL('../frontend/web/js/ai-models.js',import.meta.url),'utf8'),context);
const schema=context.window.COCKPIT_AI_CATALOG.schema;
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
console.log('✓ Worker + real SQLite: private namespaces, atomic revisions, no public read API, consent/schema/size validation, CORS, rate limit and quota errors');
