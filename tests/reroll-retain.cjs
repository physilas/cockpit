const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const read=name=>fs.readFileSync(`frontend/web/js/${name}.js`,'utf8');
const fn=(name,start,end)=>{const s=read(name);return s.slice(s.indexOf(start),s.indexOf(end,s.indexOf(start)));};
const state={neuwurf_plaettchen:1,pilot_wuerfel:[1,2,3,4],kopilot_wuerfel:[6,5,4,3]};
function context(){return {console,neuwurfUi:{phase:1,id:7,auswahl:{pilot:[],kopilot:[]},bestaetigt:{pilot:false,kopilot:false}},aktuellerZustand:state,bridge:{tick:()=>({ergebnis:{erfolg:false}}),zustand:()=>state,benutze_neuwurf:()=>assert.fail('An empty reroll must not reach the engine')},pyToJs:x=>x};}
{
 const c=context();c.Singleplayer={confirmReroll:()=>false};c.neuwurfReset=()=>{c.neuwurfUi.phase=0;};c.setzeMeldung=()=>{};c.render=()=>{};
 vm.createContext(c);vm.runInContext(fn('app','function neuwurfBestaetigen(','function renderNeuwurfPanel('),c);
 c.neuwurfBestaetigen('pilot');assert.equal(c.neuwurfUi.phase,1);c.neuwurfBestaetigen('kopilot');assert.equal(c.neuwurfUi.phase,0);
}
{
 const c=context();c.pyodideReady=true;c.choosingLanding=false;c.neuwurfUiReset=()=>{c.neuwurfUi.phase=0;};let sent=0;c.sendState=()=>{sent++;};
 vm.createContext(c);vm.runInContext(fn('multiplayer','function hostAktion(','// ── Eigene Aktion'),c);
 c.hostAktion({typ:'neuwurf_confirm',id:7,confirmed:true},'pilot');c.hostAktion({typ:'neuwurf_confirm',id:7,confirmed:true},'kopilot');assert.equal(c.neuwurfUi.phase,0);assert.equal(sent,2);
}
{
 const c={console,reroll:{selections:{pilot:[],kopilot:null},event_ids:[0,1]},session:{events:[{},{}]},api:{state:()=>state,closeReroll:()=>{},refresh:()=>{},notify:()=>{}},nextRerollRole:()=> 'kopilot',hasAI:()=>false,feedbackUndoStack:[],persist:()=>{},renderFeedback:()=>{},decision:()=>assert.fail('No invalid empty-selection decision should be recorded')};
 vm.createContext(c);vm.runInContext(fn('singleplayer','  function confirmReroll(','  function undo('),c);
 c.confirmReroll('kopilot',0);assert.equal(c.reroll,null);assert(c.session.events.every(e=>e.voided));
}
assert.equal(state.neuwurf_plaettchen,1);assert.deepEqual(state.pilot_wuerfel,[1,2,3,4]);assert.deepEqual(state.kopilot_wuerfel,[6,5,4,3]);
console.log('✓ Both empty: Pass & Play, network host broadcasts, learning events voided, no dice/RNG/token mutation.');
