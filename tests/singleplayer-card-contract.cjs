/* Lightweight production-helper tests: no browser, model updates or game RNG. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const read=path=>fs.readFileSync(new URL(`../${path}`,`file://${__filename}`),'utf8');
const context={window:{addEventListener(){}},document:{addEventListener(){}},LearningCloud:{enabled:()=>false},setTimeout:()=>0,clearTimeout(){}};
vm.runInNewContext(read('frontend/web/js/ai-models.js'),context);
vm.runInNewContext(read('frontend/web/js/landing-catalog.js'),context);
const catalog=context.window.COCKPIT_AI_CATALOG,routes=context.window.LANDING_CATALOG.scenarios;
const moduleSchema=catalog.models.find(model=>model.schema?.version===3).schema;
// Expose only pure helpers in this in-memory test copy; production API stays private.
const instrumented=read('frontend/web/js/singleplayer.js').replace('connect(adapter) { api = adapter; }',
  'test: {supportedCases,supportsRoute,supportsCase,supportsFeedback,actionId,setSetup(value){setup=value;}}, connect(adapter) { api = adapter; }');
vm.runInNewContext(instrumented,context);
const api=context.window.Singleplayer.test,route=routes.find(row=>row.engine_code==='LOG_ATL_YELLOW');
const model={schema:moduleSchema,supported_airports:['LOG_ATL_YELLOW'],preview:{enabled:true,supported_cases:[
  {airport:route.engine_code,abilities:['control']},{airport:route.engine_code,abilities:['control']},
  {airport:route.engine_code,abilities:['working-together']},{airport:route.engine_code,abilities:['unknown']},
  {airport:route.engine_code,abilities:['control','mastery']},{airport:'LOG_GIG_YELLOW',abilities:['adaptation']},
],case_results:{'LOG_ATL_YELLOW|control':{games:10,win_rate:0},'LOG_ATL_YELLOW|working-together':{games:10,win_rate:.2}}}};
assert.equal(api.supportedCases(model,route).length,2);
assert.equal(api.supportsCase(model,route,['control']),true);
assert.equal(api.supportsFeedback(model,route,['control']),true);
for(const cards of [[],['mastery'],['control','mastery'],['control','control'],['unknown']])
  assert.equal(api.supportsCase(model,route,cards),false);
assert.equal(api.supportsRoute({...model,preview:undefined},route),false);
assert.equal(api.supportsRoute({...model,preview:{...model.preview,enabled:'true'}},route),false);
assert.equal(api.supportsRoute({...model,schema:{version:2}},route),false);
assert.equal(api.supportsRoute({...model,supported_airports:['MUC']},route),false);
assert.equal(api.supportsRoute({...model,preview:{...model.preview,case_results:{}}},route),false);
assert.equal(api.supportsRoute(null,route),false);
const base=routes.find(row=>row.engine_code==='MUC');
assert.equal(api.supportsCase({supported_airports:['MUC']},base,[]),true);
assert.equal(api.supportsCase({supported_airports:['MUC']},base,['control']),false);
api.setSetup({mode:'play',model:{schema:moduleSchema}});
for(let die=0;die<4;die++) for(const kind of ['adaptation','anticipation','swap_choose'])
  assert.equal(api.actionId({kind,role:'pilot',die}),moduleSchema.actions.findIndex(action=>action.kind===kind && action.die===die));
const calls=[],events=[];
let active=true,controlled='kopilot';
const runtime={aktuellerZustand:{am_zug:'pilot',kooperation:{id:7,wartet_auf:'kopilot',auswahl:{pilot:1,kopilot:3}}},
  pyToJs:value=>value,Singleplayer:{active:()=>active,canControl:role=>!active || role===controlled,
    beforeAction:action=>action,afterAction:action=>events.push(action)},
  bridge:{kooperation_waehlen_bestaetigen(...args){calls.push(['atomic',...args]);return {ergebnis:{erfolg:true}};},
    modul_aktion(...args){calls.push(['module',...args]);return {ergebnis:{erfolg:true}};}}};
const app=read('frontend/web/js/app.js');
vm.runInNewContext(app.slice(app.indexOf('function spielAktion('),app.indexOf('function grundText(')),runtime);
runtime.spielAktion({kind:'swap_choose',role:'kopilot',die:3,cooperation_id:7},'ai');
assert.deepEqual(calls.pop(),['atomic','kopilot',3,7]);
runtime.spielModulAktion('kopilot','kooperation_bestaetigen',{kooperation_id:7});
assert.equal(events.at(-1).kind,'swap_choose');assert.equal(events.at(-1).die,3);
runtime.aktuellerZustand.kooperation=null;
runtime.spielModulAktion('kopilot','adaptation',{wuerfel_index:2});
assert.equal(events.at(-1).kind,'module_action','Legal offturn card changes must not invent a policy observation');
active=false;
runtime.spielModulAktion('kopilot','adaptation',{wuerfel_index:2});
assert.equal(events.at(-1).kind,'adaptation','Pass & Play keeps its ordinary card operation');
active=true;controlled='pilot';
const count=events.length;
assert.equal(runtime.spielModulAktion('kopilot','adaptation',{wuerfel_index:2}).ergebnis.erfolg,false);
assert.equal(events.length,count);
console.log('✓ Exact explicit card cases, legacy no-card support, all swap die IDs, atomic dispatch, offturn administrative recording and unchanged Pass & Play');
