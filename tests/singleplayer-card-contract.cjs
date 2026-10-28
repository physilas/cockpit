/* Lightweight production-helper tests: no browser, model updates or game RNG. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const read=path=>fs.readFileSync(new URL(`../${path}`,`file://${__filename}`),'utf8');
const context={window:{addEventListener(){}},document:{addEventListener(){}},LearningCloud:{enabled:()=>false},setTimeout:()=>0,clearTimeout(){}};
vm.runInNewContext(read('frontend/web/js/ai-models.js'),context);
vm.runInNewContext(read('frontend/web/js/landing-catalog.js'),context);
vm.runInNewContext(read('frontend/web/js/best-ai.js'),context);
context.CockpitBestAI=context.window.CockpitBestAI;
const catalog=context.window.COCKPIT_AI_CATALOG,routes=context.window.LANDING_CATALOG.scenarios;
const moduleSchema=catalog.models.find(model=>model.schema?.version===3).schema;
// Expose only pure helpers in this in-memory test copy; production API stays private.
const instrumented=read('frontend/web/js/singleplayer.js').replace('connect(adapter) { api = adapter; }',
  'test: {supportedCases,supportsRoute,supportsCase,supportsFeedback,bestChoice,routeRate,automaticModel,actionId,label,setSetup(value){setup=value;}}, connect(adapter) { api = adapter; }');
vm.runInNewContext(instrumented,context);
const api=context.window.Singleplayer.test,route=routes.find(row=>row.engine_code==='LOG_ATL_YELLOW');
const model={schema:moduleSchema,supported_airports:['LOG_ATL_YELLOW'],preview:{enabled:true,supported_cases:[
  {airport:route.engine_code,abilities:['control']},{airport:route.engine_code,abilities:['control']},
  {airport:route.engine_code,abilities:['working-together']},{airport:route.engine_code,abilities:['unknown']},
  {airport:route.engine_code,abilities:['control','mastery']},{airport:'LOG_GIG_YELLOW',abilities:['adaptation']},
],case_results:{'LOG_ATL_YELLOW|control':{games:10,wins:0,win_rate:0},'LOG_ATL_YELLOW|working-together':{games:10,wins:2,win_rate:.2}}}};
assert.equal(api.supportedCases(model,route).length,2);
assert.equal(api.supportsCase(model,route,['control']),true);
assert.equal(api.supportsFeedback(model,route,['control']),true);
for(const cards of [[],['mastery'],['control','mastery'],['control','control'],['unknown']])
  assert.equal(api.supportsCase(model,route,cards),false);
assert.equal(api.supportsRoute({...model,preview:undefined},route),false);
assert.equal(api.supportsRoute({...model,preview:{...model.preview,enabled:'true'}},route),false);
assert.equal(api.supportsRoute({...model,schema:{version:2}},route),false);
assert.equal(api.supportsRoute({...model,supported_airports:['LOG_YUL_GREEN']},route),false);
assert.equal(api.supportsRoute({...model,preview:{...model.preview,case_results:{}}},route),false);
assert.equal(api.supportsRoute(null,route),false);
const base=routes.find(row=>row.engine_code==='LOG_YUL_GREEN');
assert.equal(api.supportsCase({supported_airports:['LOG_YUL_GREEN']},base,[]),true);
assert.equal(api.supportsCase({supported_airports:['LOG_YUL_GREEN']},base,['control']),false);
const wind=routes.find(row=>row.engine_code==='LOG_GIG_YELLOW');
const zeroBase=routes.find(row=>row.engine_code==='LOG_HND_GREEN');
const unlisted=routes.find(row=>row.engine_code==='LOG_ATL_GREEN');
const mixed={schema:moduleSchema,supported_airports:['LOG_YUL_GREEN','LOG_GIG_YELLOW','LOG_HND_GREEN','LOG_ATL_GREEN'],
  preview:{enabled:true,positive_only:true,supported_cases:[{airport:'LOG_YUL_GREEN',abilities:[]},
    {airport:'LOG_GIG_YELLOW',abilities:['control']},{airport:'LOG_GIG_YELLOW',abilities:['adaptation']},
    {airport:'LOG_HND_GREEN',abilities:[]}],case_results:{'LOG_YUL_GREEN|':{games:20,wins:1,win_rate:.05},
      'LOG_GIG_YELLOW|control':{games:20,wins:2,win_rate:.1},'LOG_GIG_YELLOW|adaptation':{games:20,wins:0,win_rate:0},
      'LOG_HND_GREEN|':{games:20,wins:0,win_rate:0}}}};
assert.equal(api.supportsCase(mixed,base,[]),true);
assert.equal(api.supportsCase(mixed,base,['control']),false);
assert.equal(api.supportsFeedback(mixed,base,[]),true);
assert.equal(api.supportsFeedback(mixed,wind,['control']),true);
assert.equal(api.supportsCase(mixed,wind,['adaptation']),false);
assert.equal(api.supportsRoute(mixed,zeroBase),false);
assert.equal(api.supportsRoute(mixed,unlisted),false,'No-card route hints cannot bypass an explicit case manifest');
assert.equal(api.supportsRoute({...mixed,preview:{...mixed.preview,supported_cases:[]}},base),false);
assert.equal(api.supportsRoute({...mixed,preview:{...mixed.preview,supported_cases:null}},base),false);
assert.equal(api.supportsRoute({...mixed,preview:{...mixed.preview,positive_only:'true'}},base),false);
assert.equal(api.supportsRoute({...mixed,preview:{...mixed.preview,positive_only:false}},zeroBase),true,
  'Legacy explicit weak previews keep intentionally allowed zero-win cases');
for(const bad of [{games:20,wins:0,win_rate:.05},{games:20,wins:21,win_rate:1.05},
                  {games:20,wins:1.5,win_rate:.075},{games:20,win_rate:.05}])
  assert.equal(api.supportsCase({...mixed,preview:{...mixed.preview,
    case_results:{...mixed.preview.case_results,'LOG_YUL_GREEN|':bad}}},base,[]),false,
    'Corrupt counts cannot manufacture a positive case');
api.setSetup({mode:'play',model:{schema:moduleSchema}});
for(let die=0;die<4;die++) for(const kind of ['adaptation','anticipation','swap_choose'])
  assert.equal(api.actionId({kind,role:'pilot',die}),moduleSchema.actions.findIndex(action=>action.kind===kind && action.die===die));
// Exercise production eligibility and displayed exact rates, not just the ranking helper.
for(const mode of ['play','feedback']){
 api.setSetup({mode,model:api.automaticModel});
 for(const route of routes){
  assert.equal(api.supportsRoute(api.automaticModel,route),true);
  for(const row of api.supportedCases(api.automaticModel,route)){
   const winner=api.bestChoice(route,row.abilities),rate=api.routeRate(route,row.abilities);
   assert(winner);assert.equal(api.supportsCase(api.automaticModel,route,row.abilities),true);
   assert.equal(rate.value,`${(winner.result.win_rate*100).toLocaleString('de-DE',{maximumFractionDigits:1})} %`);
   assert(rate.title.includes(`${winner.result.wins}/${winner.result.games} Partien`));
  }
 }
}
for(const [kind,expected] of Object.entries({adaptation:'Anpassung: Würfel 3 umdrehen',anticipation:'Voraussicht: Würfel 3 neu werfen',
 swap_start:'Zusammenarbeit: Würfeltausch vorschlagen',swap_choose:'Zusammenarbeit: Würfel 3 tauschen',swap_cancel:'Zusammenarbeit: Würfeltausch abbrechen',
 bonus_roll:'Schwarzen Zusatzwürfel werfen',round_end:'Runde beenden',reroll_start:'Gemeinsamen Neuwurf starten',reroll_select:'Neuwurf: alle Würfel behalten'}))
 assert.equal(api.label({kind,die:2,subset:0}),expected);
console.log('✓ Every active ability has its own correct feedback label; keeping all dice is explicit');
const calls=[],events=[];
let active=true,controlled='kopilot';
const runtime={syncTeachingClock(){},aktuellerZustand:{am_zug:'pilot',kooperation:{id:7,wartet_auf:'kopilot',auswahl:{pilot:1,kopilot:3}}},
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
