const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const context={window:{}};vm.createContext(context);
for(const file of ['ai-models','landing-catalog','best-ai'])vm.runInContext(fs.readFileSync(`frontend/web/js/${file}.js`,'utf8'),context);
const {CockpitBestAI:best,COCKPIT_AI_CATALOG:catalog,LANDING_CATALOG:routes}=context.window;
const models=catalog.models.filter(m=>!m.ui_hidden&&(m.quality?.approved||m.preview?.enabled));
const eligible=(m,r,c)=>(m.supported_airports||[m.airport]).includes(r.engine_code)&&m.preview.supported_cases.some(row=>row.airport===r.engine_code&&JSON.stringify([...row.abilities].sort())===JSON.stringify([...c].sort()));
let cases=0;const selected=new Set();
for(const route of routes.scenarios){
 const combinations=new Map(models.flatMap(m=>m.preview?.supported_cases||[]).filter(row=>row.airport===route.engine_code).map(row=>[[...row.abilities].sort().join(','),row.abilities]));
 for(const cards of combinations.values()){
  const chosen=best.choose(models,route,cards,eligible);assert(chosen);selected.add(chosen.model.crew_number);
  const measured=models.filter(m=>eligible(m,route,cards)).map(m=>best.result(m,route,cards)).filter(Boolean);
  assert.equal(chosen.result.win_rate,Math.max(...measured.map(row=>row.wins/row.games)));
  assert.equal(chosen.result.win_rate,chosen.result.wins/chosen.result.games);
  assert(eligible(chosen.model,route,cards));cases++;
 }
}
assert.equal(cases,186);assert(selected.size>1,'Different routes/cards must actually pick different crews');
const yul=routes.scenarios.find(r=>r.engine_code==='LOG_YUL_GREEN');
const yulWinner=best.choose(models,yul,[],eligible);assert.equal(yulWinner.model.crew_number,5);assert.equal(yulWinner.result.win_rate,.8);assert.equal(yulWinner.result.games,10);
const candidate=(id,wins,games,crew)=>({id,crew_number:crew,preview:{enabled:true,case_results:{'LOG_YUL_GREEN|':{wins,games,win_rate:wins/games}},supported_cases:[{airport:'LOG_YUL_GREEN',abilities:[]}]}});
assert.equal(best.choose([candidate('small',1,2,6),candidate('large',10,20,5)],yul,[]).model.id,'large');
const invalid=candidate('wrong',10,10,6);invalid.preview.case_results['LOG_YUL_GREEN|'].win_rate=.8;
assert.equal(best.choose([invalid],yul,[]),null);
assert.equal(best.choose(models,null,[],eligible),null);
assert.equal(best.choose(models,yul,['invalid-card'],eligible),null);
console.log(`✓ Beste KI selects the highest exact route/card result in all ${cases} cases, uses ${selected.size} different crews, rejects invalid data and breaks ties by sample size.`);
