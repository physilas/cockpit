const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('frontend/web/js/modules.js','utf8');
class El {
 constructor(tag){this.tag=tag;this.children=[];this.dataset={};this.open=false;this.attrs={};}
 appendChild(x){this.children.push(x);return x;} setAttribute(k,v){this.attrs[k]=v;}
 addEventListener(k,fn){this[k]=fn;} showModal(){this.open=true;} close(){this.open=false;}
 focus(){} contains(){return false;} querySelectorAll(){return [];}
 set innerHTML(v){this.html=v;this.children=[];} get innerHTML(){return this.html;}
}
const actions=[],document={activeElement:null,body:new El('body'),createElement:t=>new El(t)};
const z={status:'laeuft',phase:'platzieren',am_zug:'pilot',voraussicht_verfuegbar:true,anpassung_verfuegbar:{pilot:true,kopilot:true},kooperation_verfuegbar:true,pilot_wuerfel:[1,2,5,6],kopilot_wuerfel:[2,3,4,5],pilot_wuerfel_frei:[true,true,false,true],kopilot_wuerfel_frei:[true,true,true,true]};
const box={document,clearBoardPeek(){},peekBoard(){},boardPeek:null,current:{z,options:{role:'pilot',conceal(){}}},choice:null,revealed:null,pickerDialog:null,
 name:r=>r,allowed:r=>!box.current.options.role||box.current.options.role===r,closeDetail(){},act:(...a)=>actions.push(a),
 button(parent,label,cb,disabled=false,cls=''){const b=new El('button');Object.assign(b,{textContent:label,click:cb,disabled,className:cls});parent.appendChild(b);return b;}};
vm.createContext(box);vm.runInContext(source.slice(source.indexOf('  function abilityAvailable('),source.indexOf('  function render(z, options)')),box);
const all=(node)=>[node,...node.children.flatMap(all)];
const buttons=()=>all(box.pickerDialog).filter(n=>n.tag==='button');
box.openPicker('kopilot','anticipation');assert.equal(box.choice,null,'Never open the partner hand');
box.openPicker('pilot','anticipation');box.renderPicker(z,box.current.options);
buttons().find(b=>b.textContent==='Nicht neu würfeln').click();assert.equal(actions.length,0);assert(z.voraussicht_verfuegbar);assert(!box.pickerDialog.open);
box.openPicker('pilot','anticipation');box.renderPicker(z,box.current.options);
buttons().find(b=>b.dataset.focus==='die-0').click();buttons().find(b=>b.dataset.focus==='die-3').click();
assert.equal(box.choice.index,3,'Only a single die may be selected');assert(buttons().find(b=>b.dataset.focus==='die-2').disabled);
buttons().find(b=>b.textContent==='Würfel neu werfen').click();assert.deepEqual(JSON.parse(JSON.stringify(actions.pop())),['pilot','anticipation',{wuerfel_index:3}]);
box.current.options.role=null;box.openPicker('pilot','adaptation');box.renderPicker(z,box.current.options);
assert(buttons().filter(b=>b.dataset.focus?.startsWith('die-')).every(b=>b.disabled&&b.textContent==='?'),'Pass & Play hands stay concealed');
buttons().find(b=>b.textContent==='Würfel ansehen').click();assert(buttons().some(b=>b.textContent===1));
assert(all(box.pickerDialog).some(e=>e.textContent==='1 → 6'));buttons().find(b=>b.dataset.focus==='die-0').click();buttons().find(b=>b.textContent==='Würfel umdrehen').click();assert.deepEqual(JSON.parse(JSON.stringify(actions.pop())),['pilot','adaptation',{wuerfel_index:0}]);
box.openPicker('pilot','anticipation');z.voraussicht_verfuegbar=false;box.renderPicker(z,box.current.options);assert.equal(box.choice,null);assert(!box.pickerDialog.open);
for(const blocker of ['zusatzaktion','kooperation']){z[blocker]={};assert(!box.abilityAvailable(z,box.current.options,'pilot','adaptation'));z[blocker]=null;}
assert(!box.abilityAvailable(z,{reroll:true},'pilot','adaptation'));
console.log('✓ Single ability die, retain without mutation, private partner hand, Pass & Play reveal, flip preview, expired ability and pending-action guards.');

vm.runInContext(source.slice(source.indexOf('  function cardState('),source.indexOf('  function renderCards(')),box);
z.felder={ruder:{pilot:{wert:4},kopilot:{wert:4}},triebwerk:{pilot:{wert:3},kopilot:{wert:5}}};
assert.equal(box.cardState('control',z),'✓ Gleiche Würfel');assert.equal(box.cardState('mastery',z),'Werte verschieden');
z.felder.ruder.kopilot=null;assert.equal(box.cardState('control',z),'Ruder gleich → ☕');assert.equal(box.cardState('synchronisation',z),'Automatisch');
console.log('✓ Passive card progress uses public placed dice; no claim of a reward when the resource pool is full.');

box.boardReturn=null;box.boardPeek=null;box.render=(z,o)=>box.renderPicker(z,o);box.tradeUi={revealed:null};
vm.runInContext(source.slice(source.indexOf('  function clearBoardPeek('),source.indexOf('  let current =')),box);
z.voraussicht_verfuegbar=true;box.current.options.role='pilot';box.openPicker('pilot','anticipation');box.renderPicker(z,box.current.options);
buttons().find(b=>b.dataset.focus==='die-1').click();box.peekBoard('picker',box.pickerDialog);
assert(!box.pickerDialog.open&&!box.boardReturn.hidden);assert.equal(box.choice.index,1);
box.renderPicker(z,box.current.options);assert(!box.pickerDialog.open);
box.boardReturn.click();assert(box.pickerDialog.open&&box.boardReturn.hidden);assert.equal(box.choice.index,1);
box.closePicker();assert(box.boardReturn.hidden);
console.log('✓ Ability board peek preserves the selected die and returns to the same selection.');
