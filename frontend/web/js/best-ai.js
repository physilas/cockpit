/* Route/card-specific selection from measured, currently available crews. */
window.CockpitBestAI = (() => {
  const id='best-ai';
  const key=(airport,cards)=>`${airport}|${[...cards].sort().join(',')}`;
  function result(model,route,cards=[]) {
    if(!model||!route||!Array.isArray(cards))return null;
    const perCase=route.ability_count>0||Object.hasOwn(model.preview||{},'supported_cases');
    const row=perCase?model.preview?.case_results?.[key(route.engine_code,cards)]
      :(model.preview?.enabled?model.preview?.route_results:model.quality?.route_results)?.[route.engine_code];
    return row&&Number.isInteger(row.games)&&row.games>0&&Number.isInteger(row.wins)
      &&row.wins>=0&&row.wins<=row.games&&Number.isFinite(row.win_rate)
      &&row.win_rate===row.wins/row.games?row:null;
  }
  function choose(models,route,cards,canUse=()=>true) {
    if(!route||!Array.isArray(cards))return null;
    const candidates=models.filter(model=>model.id!==id&&canUse(model,route,cards))
      .map(model=>({model,result:result(model,route,cards),case_key:key(route.engine_code,cards)})).filter(row=>row.result);
    candidates.sort((a,b)=>b.result.win_rate-a.result.win_rate||b.result.games-a.result.games
      ||Number(b.model.quality?.approved===true)-Number(a.model.quality?.approved===true)
      ||(b.model.crew_number||0)-(a.model.crew_number||0)||(a.model.id<b.model.id?-1:a.model.id>b.model.id?1:0));
    return candidates[0]||null;
  }
  return {id,result,choose};
})();
