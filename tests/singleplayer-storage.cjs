/* Production persistence against an asynchronous transactional IndexedDB stand-in. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const rows=new Map();let abortNext=false,abortRevision=null;
const clone=value=>JSON.parse(JSON.stringify(value));
const database={transaction(){
 const pending=[],tx={error:null};
 tx.objectStore=()=>({put(row){pending.push(clone(row));},getAll(){const request={};queueMicrotask(()=>{request.result=[...rows.values()].map(clone);request.onsuccess?.();});return request;}});
 queueMicrotask(()=>{
  if(pending.length&&(abortNext||pending.some(row=>row.id===abortRevision?.id&&row.data_revision===abortRevision.revision))){abortNext=false;tx.error=Error('quota');tx.onabort?.();return;}
  pending.forEach(row=>rows.set(row.id,row));tx.oncomplete?.();
 });return tx;
}};
const indexedDB={open(){const request={result:database};queueMicrotask(()=>request.onsuccess?.());return request;}};
const elements=new Map(),element=id=>{if(!elements.has(id))elements.set(id,{});return elements.get(id);};
const context={indexedDB,document:{addEventListener(){},getElementById:element},addEventListener(){},LearningCloud:{enabled:()=>false},setTimeout:()=>0,clearTimeout(){}};
context.window=context;vm.createContext(context);
for(const file of ['ai-models','landing-catalog','best-ai'])vm.runInContext(fs.readFileSync(`frontend/web/js/${file}.js`,'utf8'),context);
const source=fs.readFileSync('frontend/web/js/singleplayer.js','utf8').replace('connect(adapter) { api = adapter; }',
 'test:{setSession(row){session=row;},persist,storedSessions,flush:()=>saveQueue,retained:()=>memory.size,problem:()=>storageError}, connect(adapter) { api = adapter; }');
vm.runInContext(source,context);const api=context.Singleplayer.test;
const record=id=>({id,mode:'play',events:[],status:'active'});
(async()=>{
 for(let n=0;n<20;n++){api.setSession(record(`saved-${n}`));api.persist();await api.flush();}
 assert.equal(rows.size,20);assert.equal(api.retained(),0,'Successfully saved full sessions accumulate in RAM');
 assert.equal((await api.storedSessions()).length,20,'Releasing RAM lost exportable records');
 const failed=record('failed');abortNext=true;api.setSession(failed);api.persist();await api.flush();
 assert(!rows.has('failed'));assert.equal(api.retained(),1);assert(api.problem());
 assert((await api.storedSessions()).some(row=>row.id==='failed'),'A failed transaction lost its export fallback');
 api.setSession(record('later-success'));api.persist();await api.flush();assert.equal(api.retained(),1,'Unrelated successful write discarded a failed record');
 assert(api.problem(),'An unrelated successful save hid another unsaved session');
 await assert.rejects(context.Singleplayer.flushForUpdate(),'App update would discard the unsaved export fallback');
 // Queue two revisions before either transaction finishes. The older write
 // must never release a newer unsaved snapshot under the same session ID.
 failed.events.push({id:0});api.setSession(failed);api.persist();failed.events.push({id:1});api.persist();
 await api.flush();assert.equal(rows.get('failed').events.length,2);assert.equal(api.retained(),0);assert.equal(api.problem(),'');await context.Singleplayer.flushForUpdate();
 assert.equal((await api.storedSessions()).find(row=>row.id==='failed').events.length,2);
 const overlap=record('overlap');abortRevision={id:'overlap',revision:2};api.setSession(overlap);api.persist();overlap.events.push({id:0});api.persist();
 await api.flush();assert.equal(rows.get('overlap').data_revision,1);assert.equal(api.retained(),1,'Older commit released a newer aborted revision');
 assert.equal((await api.storedSessions()).find(row=>row.id==='overlap').events.length,1);
 abortRevision=null;api.persist();await api.flush();assert.equal(api.retained(),0);
 console.log('✓ Completed transactions release full-session RAM copies; aborted writes stay exportable, unrelated writes preserve them and newest queued revisions survive');
})().catch(error=>{console.error(error);process.exitCode=1;});
