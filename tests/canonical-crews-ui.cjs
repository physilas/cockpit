/* Six crews with Koordinator as default; 21 visible routes, all exact cases. */
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const {chooseMode,chooseModel,chooseRoute,chooseAbilities,leaveGame}=require('./singleplayer-setup.cjs');
const url=(process.env.COCKPIT_TEST_URL||'http://127.0.0.1:8036')+'/frontend/web/';
const records=page=>page.evaluate(async()=>{
 const db=await new Promise(resolve=>{const r=indexedDB.open('flyteam-learning-v1',2);r.onsuccess=()=>resolve(r.result);});
 return new Promise(resolve=>{const r=db.transaction('sessions').objectStore('sessions').getAll();r.onsuccess=()=>resolve(r.result);});
});
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.COCKPIT_CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 try{
  const context=await browser.newContext({viewport:{width:390,height:844},serviceWorkers:'block'}),errors=[];
  await context.route('**/js/cloud-config.js',r=>r.fulfill({contentType:'application/javascript',body:'window.COCKPIT_LEARNING_CLOUD={};'}));
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url);await page.getByRole('button',{name:/Singleplayer/}).click();await chooseMode(page,'feedback');
  const allModels=await page.locator('#solo-model option').evaluateAll(options=>options.map(o=>({id:o.value,text:o.textContent})));
  const models=allModels.filter(m=>/^crew[1-4]-allroutes-/.test(m.id));
  const navigator=allModels.find(m=>m.id==='crew5-planner-2026-10-28-v1/best.pt');
  const coordinator=allModels.find(m=>m.id==='crew6-abilities-2026-10-28-v1/best.pt');
  assert.ok(navigator);assert.ok(coordinator);assert.equal(allModels.length,6);
  assert.deepEqual(allModels.map(m=>m.text.split(' · ')[0]),['Crew 6','Crew 5','Crew 4','Crew 3','Crew 2','Crew 1']);
  assert.equal(models.length,4);assert.deepEqual(models.map(m=>m.text.split(' · ')[0]),['Crew 4','Crew 3','Crew 2','Crew 1']);
  assert.equal(await page.locator('#solo-model').inputValue(),coordinator.id);
  for(const model of allModels){
   const data=await page.evaluate(id=>COCKPIT_AI_CATALOG.models.find(m=>m.id===id),model.id);
   const isNavigator=model.id===navigator.id||model.id===coordinator.id;
   assert.equal(data.preview.supported_cases.length,isNavigator?192:186);assert.equal(data.supported_airports.length,isNavigator?27:21);
   assert.equal(data.quality.approved,false);assert.equal(data.preview.positive_only||false,false);
   for(const row of Object.values(data.preview.case_results))assert.equal(row.win_rate,row.wins/row.games);
   await chooseModel(page,model.id);await page.locator('#solo-next').click();
   assert.equal(await page.locator('#solo-landings .landing-card').count(),21);
  }
  const cases=[['KUL-yellow','LOG_KUL_YELLOW|synchronisation','kopilot'],['YUL-green',null,'pilot'],['PBH-black','LOG_PBH_BLACK|control,mastery','kopilot'],
    ['ATL-green',null,'pilot'],['ATL-yellow','LOG_ATL_YELLOW|working-together','pilot'],
    ['GIG-yellow','LOG_GIG_YELLOW|adaptation','kopilot']];
  const playingModels=allModels;
  for(let i=0;i<playingModels.length;i++){
   if(i){await page.getByRole('button',{name:/Singleplayer/}).click();await chooseMode(page,'feedback');}
   const [route,cards,role]=cases[i];await chooseModel(page,playingModels[i].id,role);await chooseRoute(page,route);
   if(cards)await chooseAbilities(page,cards);
   await page.locator('#solo-consent').check();await page.locator('#solo-start').click();
   await page.locator('#spiel-ui').waitFor({state:'visible',timeout:90000});
   await page.evaluate(()=>{
    pyodide.runPython('import backend.bridge as b\nwhile b._spiel.phase=="verkehr":b._spiel.wirf_verkehrswuerfel()');resetVerkehrUi();
    const human=Singleplayer.visibleRole(),ai=human==='pilot'?'kopilot':'pilot';
    pyodide.runPython(`b._spiel.am_zug=${JSON.stringify(ai)}`);
    render(pyToJs(bridge.zustand()));
   });
   // Canonical crew checks intentionally exercise the unchanged autonomous policy.
   const skipPlan=page.getByRole('button',{name:'Ohne Absprache würfeln',exact:true});
   if(await skipPlan.isVisible())await skipPlan.click();
   for(let j=0;j<80;j++){if((await records(page)).some(r=>r.model?.id===playingModels[i].id&&r.events.some(e=>e.actor==='ai')))break;await page.waitForTimeout(100);}
   const saved=(await records(page)).find(r=>r.model?.id===playingModels[i].id);
   assert.ok(saved?.events.some(e=>e.actor==='ai'&&e.decision.observation.length===489&&e.decision.reference_action_mask.some(Boolean)));
   if(route.endsWith('black'))assert.equal(await page.evaluate(()=>aktuellerZustand.neuwurf_plaettchen),0);
   await page.evaluate(()=>Singleplayer.suspend());
   if(i===3){
    for(const viewport of [{width:390,height:844},{width:320,height:740}]){
     await page.setViewportSize(viewport);await page.waitForTimeout(100);
     const box=await page.locator('#intern-strip').boundingBox();assert.ok(box&&box.y>=0&&box.y+box.height<=viewport.height);
     await page.evaluate(()=>{menuPausedAt=Date.now();document.querySelectorAll('dialog[open]').forEach(d=>d.close());});
     await page.screenshot({path:`/tmp/cockpit-canonical-intern-${viewport.width}.png`});
    }await page.setViewportSize({width:390,height:844});
   }
   await page.evaluate(()=>{document.querySelectorAll('dialog[open]').forEach(d=>d.close());GameDialogs.menu();});
   await page.getByRole('button',{name:'Hauptmenü',exact:true}).click();
   await page.getByRole('button',{name:'Zum Hauptmenü',exact:true}).click();
  }
  assert.deepEqual(errors,[]);await context.close();
  console.log('✓ Six crews with Koordinator as default; every exact route/card case including zero rates; real browser weights/decisions in both roles; intern fit; difficult-route zero start token');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
