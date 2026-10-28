/* Exercise production undo bookkeeping without a browser, dice RNG or model updates. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const elements=new Map();
const element=id=>{
 if(!elements.has(id))elements.set(id,{classList:{toggle(){},remove(){}},replaceChildren(){}});
 return elements.get(id);
};
const context={document:{addEventListener(){},getElementById:element},addEventListener(){},
 LearningCloud:{enabled:()=>false},setTimeout:()=>0,clearTimeout(){}};
context.window=context;vm.createContext(context);
for(const file of ['ai-models','landing-catalog','best-ai','round-planning'])
 vm.runInContext(fs.readFileSync(`frontend/web/js/${file}.js`,'utf8'),context);
let source=fs.readFileSync('frontend/web/js/singleplayer.js','utf8');
source=source.replace('connect(adapter) { api = adapter; }',
 'test:{load(record,config){session=record;setup=config;},record:()=>session,currentRoundEntry,renderRoundPlan}, connect(adapter) { api = adapter; }');
vm.runInContext(source,context);
const player=context.Singleplayer,model=context.COCKPIT_AI_CATALOG.models.find(m=>m.crew_number===6);
const start={szenario_id:'LOG_YUL_GREEN',entfernung:5,fahrwerk_ausgefahren:[false,false,false],landeklappen_ausgefahren:[false,false,false,false],
 bremsen_aktiviert:[false,false,false],flugzeuge:[1,0],kaffeetassen:1,kerosin:null,eis_fortschritt:0};
const plan=round=>({round,plan:{movement_preference:1,focus:'tasks'},proposal:{public_state:start,goals:[]},synchronisation:true,result:'Stale old result',outcome:{stale:true}});
const record={id:'undo-fixture',mode:'play',status:'verloren',finished_at:'2026-10-28T00:00:00Z',round_planning_enabled:true,
 round_plans:[plan(1),plan(2)],briefing_draft:{round:2,proposal:{old:true}},events:[{id:0,action_id:0}],engine_stack:[0]};
let state={...start,runde:1,status:'laeuft',phase:'platzieren',faehigkeitskarten:['synchronisation'],felder:{fahrwerk:[{wert:1},null,null],landeklappen:[null,null,null,null]}};
player.connect({state:()=>state,canBrief:()=>false});player.test.load(record,{mode:'play',humanRole:'pilot',model});
const before=JSON.stringify(record);player.undo({ergebnis:{erfolg:false},zustand:state});assert.equal(JSON.stringify(record),before);
player.undo({ergebnis:{erfolg:true},zustand:state});
assert.equal(record.status,'active','Undoing a terminal move left the training record finished');
assert(!Object.hasOwn(record,'finished_at'));
assert.equal(record.events[0].voided,true);
assert(!Object.hasOwn(record.round_plans[0],'result'),'Old round result survived a changed move');
assert(!Object.hasOwn(record.round_plans[0],'outcome'));
assert.equal(record.round_plans[0].synchronisation,false,'An undone synchronization still counted as achieved');
assert.equal(record.round_plans[1].voided,true,'An agreement in the undone future remains active');
assert.equal(record.briefing_draft,null,'Future proposal still uses its old public state');
assert.equal(player.test.currentRoundEntry(),record.round_plans[0],'The current accepted agreement must stay in force');
state={...state,runde:2,phase:'vorbereitung',entfernung:3};
assert.equal(player.test.currentRoundEntry(),undefined,'Returning to that round resurrected its voided agreement');
player.test.renderRoundPlan(state);
assert.equal(record.round_plans[0].outcome.movement,2,'Replayed round failed to recompute its outcome');
assert(record.round_plans[0].result.includes('2 Felder weiter'));
assert.equal(record.round_plans[1].result,'Stale old result','Voided history should remain historical');
console.log('✓ Undo reopens finished learning records, recomputes round outcomes, restores synchronization and retires future agreements/drafts');
// Undoing an unrelated move after synchronization must keep the real reward.
state={...state,runde:1,phase:'platzieren',felder:{fahrwerk:[{wert:1}],landeklappen:[{wert:2}]}};
player.undo({ergebnis:{erfolg:true},zustand:state});
assert.equal(record.round_plans[0].synchronisation,true);
// Rewinding past the public preparation invalidates that round's old proposal.
state={...state,phase:'verkehr'};record.briefing_draft={round:1,proposal:{stale:true}};
player.undo({ergebnis:{erfolg:true},zustand:state});
assert.equal(record.round_plans[0].voided,true);
assert.equal(record.briefing_draft,null);
assert.equal(player.test.currentRoundEntry(),undefined);
console.log('✓ Real synchronization survives unrelated undo; rewinding traffic retires plans based on the superseded public state');
