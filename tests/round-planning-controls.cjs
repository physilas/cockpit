const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const ui={window:{},console};vm.createContext(ui);vm.runInContext(fs.readFileSync('frontend/web/js/round-planning.js','utf8'),ui);
const p={round:2,goals:[{key:'movement_preference',selected:1,options:[{value:0},{value:1},{value:2}]},{key:'focus',selected:'tasks',options:[{value:'radio'},{value:'tasks'}]},{key:'coordination',selected:'level',options:[{value:'level'},{value:'brakes'}]}]};
const d=ui.window.RoundPlanning.draftFor(p,{version:1,round:2,values:{movement_preference:2,focus:'not a goal',coordination:'brakes'},accepted:[true,false,true],index:1,source:'human',mode:'summary'});
assert.equal(d.values.movement_preference,2);assert.equal(d.values.focus,'tasks');assert.equal(d.source,'human');assert.equal(d.mode,'summary');
assert.equal(ui.window.RoundPlanning.plan(p,d).coordination,'brakes');
assert.equal(ui.window.RoundPlanning.draftFor({...p,round:3},d).values.movement_preference,1);
let frame=0,frames=new Map(),rerenders=0,contentBottom=702;
const track={offsetHeight:240,querySelectorAll:()=>[{offsetHeight:240,querySelector:()=>({offsetHeight:220})}]};
const main={classList:{contains:()=>false},clientHeight:650,scrollTop:0,children:[{getBoundingClientRect:()=>({bottom:contentBottom})}],getBoundingClientRect:()=>({top:42}),querySelector:()=>track};
const layout={window:{visualViewport:{height:740,addEventListener(){}},addEventListener(){}},innerWidth:393,innerHeight:740,console,matchMedia:()=>({matches:true}),getComputedStyle:()=>({paddingBottom:'6'}),
 requestAnimationFrame:fn=>{frames.set(++frame,fn);return frame;},cancelAnimationFrame:id=>frames.delete(id),document:{documentElement:{style:{setProperty(){}}},getElementById:id=>id==='spiel-ui'?main:id==='tracks-leiste'?track:{offsetHeight:42}}};
vm.createContext(layout);vm.runInContext(fs.readFileSync('frontend/web/js/cockpit-layout.js','utf8'),layout);
const fit=layout.window.CockpitLayout,s={szenario_id:'YUL',runde:1,hoehe:6000,entfernung:6,module:[]};
const flush=()=>{const calls=[...frames.values()];frames.clear();calls.forEach(fn=>fn());};
fit.fit(s,()=>rerenders++);flush();const unit=fit.unit(s);assert(unit<36);assert.equal(rerenders,1);
contentBottom=850;for(let i=0;i<100;i++){fit.fit({...s,am_zug:i%2?'pilot':'kopilot'},()=>rerenders++);flush();}
assert(fit.unit(s)>=28,'Long routes must retain readable rows');assert.equal(fit.unit(s),unit);assert.equal(rerenders,1,'A move must not refit the strips');
contentBottom=650;fit.fit({...s,runde:2,hoehe:5000},()=>rerenders++);flush();assert(rerenders>1,'A new round may fit once');
console.log('✓ Own goals, saved draft validation, round isolation, and no mid-round refitting across 100 moves.');
const start={entfernung:4,fahrwerk_ausgefahren:[true,false,false],landeklappen_ausgefahren:[false,false,false,false],bremsen_aktiviert:[false,false,false],kaffeetassen:1,flugzeuge:[2,1],eis_fortschritt:0};
const end={...start,runde:3,status:'laeuft',entfernung:3,fahrwerk_ausgefahren:[true,true,false],landeklappen_ausgefahren:[true,false,false,false],flugzeuge:[1,0],kaffeetassen:0,fluglage:0,wind_wert:0};
const entry={round:2,plan:{movement_preference:1,focus:'tasks'},proposal:{public_state:start}};
const outcome=ui.window.RoundPlanning.outcome(entry,end);assert.equal(outcome.tasks_completed,2);assert.equal(outcome.planes_removed,2);assert.equal(outcome.movement,1);assert.equal(outcome.fuel_spent,null);assert(!Object.hasOwn(outcome.public_after,'pilot_wuerfel'));
assert(ui.window.RoundPlanning.result(entry,end).includes('2 Aufgaben an Fahrwerk & Klappen'));
