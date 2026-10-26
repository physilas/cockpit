/* Host routing and privacy tests, without a browser or external signalling. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.join(__dirname,'..');
const elements = new Map(), events = new Map(), timers = new Map();
const element = id => {
  if (!elements.has(id)) elements.set(id, {classList:{toggle(){}},addEventListener(type,fn){this[type]=fn;}});
  return elements.get(id);
};
const state = {
  status:'laeuft', phase:'vorbereitung', am_zug:'kopilot', verkehrswuerfel_offen:0,
  neuwurf_plaettchen:2,
  verkehrswuerfe:[{wert:3,ziel_entfernung:4}], rueckgaengig_version:7,
  rueckgaengig_moeglich:true, rueckgaengig_id:1,
  pilot_wuerfel:[1,2,3,4], pilot_wuerfel_frei:[true,false,true,true],
  kopilot_wuerfel:[5,4,3,2], kopilot_wuerfel_frei:[true,true,true,true],
};
const calls = [], sent = [];
const py = value => ({toJs:() => value});
const context = vm.createContext({
  console, URLSearchParams, COCKPIT_SCHEMA:JSON.parse(fs.readFileSync(path.join(root,'backend/ui_schema.json'))),
  setTimeout:fn => {const id = Symbol(); timers.set(id,fn); return id;},
  clearTimeout:id => timers.delete(id),
  GameDialogs:{connect(){}, result(){}, menu(){}},
  Landings:{mount:() => ({})},
  window:{location:{search:'?join=ABCDEF'},addEventListener:(event,fn) => events.set(event,fn)},
  document:{body:{classList:{remove(){}}},getElementById:element,addEventListener:(event,fn) => events.set(event,fn),dispatchEvent:event => events.get(event.type)?.()},
  Event:class {constructor(type){this.type=type;}},
  fixtureBridge:{
    tick:() => py({ergebnis:{erfolg:false}}), zustand:() => py(state),
    wuerfeln_fuer_runde:() => {calls.push(['start']); state.phase='platzieren'; return py(state);},
    rueckgaengig:(role,version) => {calls.push(['undo',role,version]); state.rueckgaengig_id++; return py({ergebnis:{erfolg:true},zustand:state});},
    benutze_neuwurf:(pilot,kopilot) => {
      calls.push(['reroll',[...pilot],[...kopilot]]);
      if (state.rejectReroll) return py({ergebnis:{erfolg:false,grund:'kein_neuwurf_plaettchen'},zustand:state});
      for (const i of pilot) state.pilot_wuerfel[i] = 6;
      for (const i of kopilot) state.kopilot_wuerfel[i] = 1;
      state.neuwurf_plaettchen--;
      return py({ergebnis:{erfolg:true,meldung:'Neu gewürfelt'},zustand:state});
    },
  },
  fixtureConn:{open:true,send:json => sent.push(JSON.parse(json))},
});
const run = code => vm.runInContext(code,context);
run(fs.readFileSync(path.join(root,'frontend/web/js/reroll.js'),'utf8'));
run(fs.readFileSync(path.join(root,'frontend/web/js/multiplayer.js'),'utf8'));
run('bridge=fixtureBridge; pyodideReady=true; myRole="pilot"; conn=fixtureConn; render=()=>{}; starte_Beitreten=()=>{};');
events.get('DOMContentLoaded')();
assert.equal(typeof element('rueckgaengig-btn').click,'function','Join-link skips undo binding');
assert.equal(run('hostAktion({typ:"verkehr_start",version:7},"pilot")'),false);
assert.equal(run('hostAktion({typ:"verkehr_start",version:6},"kopilot")'),false);
assert.equal(calls.length,0,'Wrong role/stale state started the round');
run('hostAktion({typ:"verkehr_start",besitzer:"pilot",version:7},"kopilot")');
assert.deepEqual(calls,[['start']]);
assert.equal(run('hostAktion({typ:"verkehr_start",version:7},"kopilot")'),false);
assert.equal(calls.length,1,'Duplicate round start');
run('hostAktion({typ:"rueckgaengig",besitzer:"pilot",version:7},"kopilot")');
assert.deepEqual(calls.at(-1),['undo','kopilot',7],'Untrusted role overrides authenticated sender');
let snapshot = sent.at(-1).zustand;
assert.deepEqual(snapshot.pilot_wuerfel,[null,2,null,null],'Undo exposes partner free dice');
assert.deepEqual(snapshot.kopilot_wuerfel,[5,4,3,2]);
assert.equal(snapshot.rueckgaengig_id,2,'Undo not broadcast');
run('myRole="kopilot";');
element('rueckgaengig-btn').click();
assert.equal(sent.at(-1).typ,'rueckgaengig','Join device undo button sends no action');
assert.equal(sent.at(-1).version,7,'Undo sends no expected revision');
run('neuwurfUi.phase=1;');
const before = sent.length;
element('rueckgaengig-btn').click();
assert.equal(sent.length,before,'Undo during unfinished private reroll');
console.log('✓ Host role/revision guards, single automatic start, shared undo, privacy, join-link button and reroll guard');

run('neuwurfUiReset();');
const act = (msg,role='kopilot') => run(`hostAktion(${JSON.stringify(msg)},${JSON.stringify(role)})`);
const ui = () => JSON.parse(run('JSON.stringify(neuwurfUi)'));
const rerolls = () => calls.filter(c => c[0] === 'reroll');
const start = () => {act({typ:'neuwurf_start',version:7}); return ui().id;};
const toggle = (id,index,role) => act({typ:'neuwurf_toggle',id,index},role);
const confirm = (id,role,confirmed=true) => act({typ:'neuwurf_confirm',id,confirmed},role);
const closeResult = () => {assert.equal(timers.size,1); [...timers.values()][0]();};
assert.equal(act({typ:'neuwurf_start',version:7},'pilot'),false,'Inactive role started reroll');
assert.equal(act({typ:'neuwurf_start',version:6}),false,'Stale start accepted');
let id = start();
assert.deepEqual(ui().wuerfel.pilot,[1,2,3,4],'Popup lacks partner values');
assert.deepEqual(sent.at(-1).zustand.pilot_wuerfel,[null,2,null,null],'Dice tray reveals partner values');
for (const index of [-1,4,0.5,'0']) assert.equal(toggle(id,index,'pilot'),false,'Invalid index accepted');
assert.equal(toggle(id,1,'pilot'),false,'Placed die selected');
act({typ:'neuwurf_toggle',id,index:0,besitzer:'pilot'},'kopilot');
assert.deepEqual(ui().auswahl,{pilot:[],kopilot:[0]},'Sender changed partner selection');
toggle(id,2,'pilot');
confirm(id,'kopilot');
assert.equal(rerolls().length,0,'First confirmation rolled');
assert.equal(toggle(id,1,'kopilot'),false,'Confirmed selection can change');
confirm(id,'kopilot');
assert.equal(ui().bestaetigt.kopilot,true,'Duplicate confirmation toggled ready state');
confirm(id,'kopilot',false);
toggle(id,1,'kopilot');
confirm(id,'kopilot');
confirm(id,'pilot');
assert.deepEqual(rerolls(),[['reroll',[2],[0,1]]]);
assert.equal(ui().phase,2);
assert.equal(state.neuwurf_plaettchen,1);
assert.equal(state.am_zug,'kopilot','Reroll changed turn');
assert.deepEqual(state.pilot_wuerfel,[1,2,6,4],'Unselected/placed dice changed');
assert.equal(ui().vorher.pilot[2],3,'Original value lost');
assert.equal(ui().wuerfel.pilot[2],6,'New result missing');
assert.equal(confirm(id,'pilot'),false,'Duplicate confirmation rolled again');
assert.equal(act({typ:'neuwurf_cancel',id}),false,'Result dismissed before display');
closeResult();
assert.equal(ui().phase,0,'Popup did not automatically close');
assert.equal(ui().wuerfel,null,'Popup values retained after closing');
assert.deepEqual(sent.at(-1).zustand.pilot_wuerfel,[null,2,null,null]);

const oldId = id;
id = start();
assert.equal(toggle(oldId,0,'pilot'),false,'Old popup action accepted');
confirm(id,'pilot'); confirm(id,'kopilot');
assert.equal(state.neuwurf_plaettchen,1,'Empty selections consumed a token');
assert.deepEqual(ui().bestaetigt,{pilot:false,kopilot:false});
toggle(id,0,'pilot'); confirm(id,'pilot');
act({typ:'neuwurf_cancel',id});
assert.equal(ui().phase,0);
assert.equal(state.neuwurf_plaettchen,1,'Cancellation consumed a token');
id = start();
toggle(id,0,'pilot'); confirm(id,'pilot');
state.rejectReroll = true;
confirm(id,'kopilot');
assert.equal(ui().phase,1,'Failed reroll dismissed popup');
assert.deepEqual(ui().bestaetigt,{pilot:false,kopilot:false});
assert.equal(timers.size,0,'Failed reroll schedules auto-close');
delete state.rejectReroll;
confirm(id,'pilot'); confirm(id,'kopilot');
assert.equal(state.neuwurf_plaettchen,0,'One-sided selection not rolled');
closeResult();
assert.equal(act({typ:'neuwurf_start',version:7}),false,'Reroll without token');
console.log('✓ Independent selection, both confirmation orders, authenticated roles, duplicate/stale guards, one token, result, auto-close, cancellation, empty selection and engine failure');

state.neuwurf_plaettchen=1;
state.pilot_wuerfel_frei=[false,false,false,false];
id=start();
assert.equal(ui().bestaetigt.pilot,true,'Empty hand needs no confirmation');
toggle(id,0,'kopilot'); confirm(id,'kopilot');
assert.equal(ui().phase,2,'Only the nonempty hand confirms');
assert.deepEqual(rerolls().at(-1),['reroll',[],[0]]);
closeResult();
console.log('✓ Empty partner hand automatically confirms without spending or inventing dice');
