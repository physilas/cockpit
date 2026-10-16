/* Host routing and privacy tests, without a browser or external signalling. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.join(__dirname,'..');
const elements = new Map(), events = new Map();
const element = id => {
  if (!elements.has(id)) elements.set(id, {classList:{toggle(){}},addEventListener(type,fn){this[type]=fn;}});
  return elements.get(id);
};
const state = {
  status:'laeuft', phase:'vorbereitung', am_zug:'kopilot', verkehrswuerfel_offen:0,
  verkehrswuerfe:[{wert:3,ziel_entfernung:4}], rueckgaengig_version:7,
  rueckgaengig_moeglich:true, rueckgaengig_id:1,
  pilot_wuerfel:[1,2,3,4], pilot_wuerfel_frei:[true,false,true,true],
  kopilot_wuerfel:[5,4,3,2], kopilot_wuerfel_frei:[true,true,true,true],
};
const calls = [], sent = [];
const py = value => ({toJs:() => value});
const context = vm.createContext({
  console, URLSearchParams, COCKPIT_SCHEMA:JSON.parse(fs.readFileSync(path.join(root,'backend/ui_schema.json'))),
  Landings:{mount:() => ({})},
  window:{location:{search:'?join=ABCDEF'},addEventListener:(event,fn) => events.set(event,fn)},
  document:{getElementById:element,addEventListener:(event,fn) => events.set(event,fn),dispatchEvent:event => events.get(event.type)?.()},
  Event:class {constructor(type){this.type=type;}},
  fixtureBridge:{
    tick:() => py({ergebnis:{erfolg:false}}), zustand:() => py(state),
    wuerfeln_fuer_runde:() => {calls.push(['start']); state.phase='platzieren'; return py(state);},
    rueckgaengig:(role,version) => {calls.push(['undo',role,version]); state.rueckgaengig_id++; return py({ergebnis:{erfolg:true},zustand:state});},
  },
  fixtureConn:{open:true,send:json => sent.push(JSON.parse(json))},
});
const run = code => vm.runInContext(code,context);
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
