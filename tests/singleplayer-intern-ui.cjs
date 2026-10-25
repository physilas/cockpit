/* Isolated technical fixture: actual Crew-2 weights + public profile 10.
 * Its explicit unqualified preview is not release evidence or a production change. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const {chooseModel,chooseRoute} = require('./singleplayer-setup.cjs');
const fs=require('node:fs');
const pageUrl=process.env.COCKPIT_TEST_PAGE_URL || `${process.env.COCKPIT_TEST_URL || 'http://127.0.0.1:8000'}/frontend/web/`;
const source=fs.readFileSync(new URL('../frontend/web/js/ai-models.js',`file://${__filename}`),'utf8');
const sessions=page=>page.evaluate(async()=>{
  const db=await new Promise(resolve=>{const r=indexedDB.open('flyteam-learning-v1',2);r.onsuccess=()=>resolve(r.result);});
  return new Promise(resolve=>{const r=db.transaction('sessions').objectStore('sessions').getAll();r.onsuccess=()=>resolve(r.result);});
});
const waitForAIBonus=async(page,previous)=>{
  let finished=false;
  for(let attempt=0;attempt<50;attempt++) {
    await page.waitForTimeout(100);
    if(await page.locator('#ai-resume').count()) throw new Error(await page.locator('.ai-paused').innerText());
    const stored=await sessions(page);
    if(stored[0]?.events.filter(e=>e.actor==='ai' && e.action.kind==='bonus_place').length>previous
       && await page.evaluate(()=>!aktuellerZustand.zusatzaktion)) {finished=true;break;}
  }
  assert.ok(finished,'AI must finish its pending intern token');
  assert.equal(await page.locator('#ai-resume').count(),0);
  assert.equal(await page.evaluate(()=>Boolean(aktuellerZustand.zusatzaktion)),false);
};
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.COCKPIT_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  try {
    const context=await browser.newContext({viewport:{width:390,height:844},serviceWorkers:'block'}), errors=[];
    await context.route('**/js/ai-models.js',route=>route.fulfill({contentType:'application/javascript',body:source+`
      {const source=window.COCKPIT_AI_CATALOG.models.find(m=>m.name==='Crew 2');
       if(!source) throw new Error('Crew 2 fixture source missing');
       window.COCKPIT_AI_CATALOG.models.unshift({...source,id:'fixture-intern/best.pt',name:'Intern runtime fixture (Test)',
         assistance_version:10,supported_airports:['LOG_ATL_GREEN','LOG_LHR_YELLOW'],quality:{approved:false},
         preview:{enabled:true,evaluation_kind:'development',route_results:{LOG_ATL_GREEN:{win_rate:.05}}}});}
    `}));
    await context.route('**/js/cloud-config.js',route=>route.fulfill({contentType:'application/javascript',body:'window.COCKPIT_LEARNING_CLOUD={};'}));
    const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
    await page.goto(pageUrl);
    await page.getByRole('button',{name:/Singleplayer/}).click();
    await page.locator('[data-mode="feedback"]').click();
    await chooseModel(page,'fixture-intern/best.pt');
    await chooseRoute(page,'ATL-green');
    assert.equal(await page.locator('#solo-route option[value="ATL-green"]').evaluate(option=>option.disabled),false);
    assert.match(await page.locator('#solo-description').innerText(),/Entwicklungsstand, noch nicht unabhängig qualifiziert/);
    assert.match(await page.locator('#solo-description').innerText(),/Entwicklungstest im KI-Selbstspiel: 5 %/);
    await page.locator('#solo-consent').check();await page.locator('#solo-start').click();
    await page.locator('#spiel-ui').waitFor({state:'visible',timeout:90000});
    // Training changes regular am_zug, but the AI still owns its pending token.
    const pending=await page.evaluate(()=>{
      pyodide.runPython('import backend.bridge as b\nwhile b._spiel.phase == "verkehr": b._spiel.wirf_verkehrswuerfel()\nb._spiel.zusatz.praktikant = [1,2,3,4,5,6]\nb._spiel.am_zug = "kopilot"\nfor die in b._spiel.pilot_wuerfel + b._spiel.kopilot_wuerfel: die.augenzahl = 3');
      resetVerkehrUi();render(pyToJs(bridge.zustand()));
      const answer=spielAktion({kind:'place',role:'kopilot',die:0,target:'training'},'ai');
      if(!answer.ergebnis.erfolg) throw new Error(JSON.stringify(answer.ergebnis));
      nachAktion(answer);
      const target=aktuellerZustand.zusatzaktion.ziele[0];
      const blocked=spielModulAktion('kopilot','zusatz_platzieren',target);
      const before=pyToJs(aiBridge.decision('kopilot','null',1,256,10,3));
      pyodide.runPython('for die in b._spiel.pilot_wuerfel:\n if die.ist_verfuegbar(): die.augenzahl = 7 - die.augenzahl');
      const after=pyToJs(aiBridge.decision('kopilot','null',1,256,10,3));
      return {turn:aktuellerZustand.am_zug,role:aktuellerZustand.zusatzaktion.rolle,blocked:blocked.ergebnis.erfolg,
        clickTargets:document.querySelectorAll('.bonus-target').length,privateInvariant:JSON.stringify(before)===JSON.stringify(after)};
    });
    assert.deepEqual(pending,{turn:'pilot',role:'kopilot',blocked:false,clickTargets:0,privateInvariant:true});
    await waitForAIBonus(page,0);
    let data=(await sessions(page))[0],bonus=data.events.find(e=>e.actor==='ai' && e.action.kind==='bonus_place');
    assert.ok(bonus.training_compatible);
    assert.equal(bonus.decision.observation.length,489);
    assert.equal(bonus.decision.action_mask.length,217);
    assert.ok(bonus.decision.reference_action_mask.some(Boolean));
    assert.ok(await page.locator('#wuerfel-kopilot .wuerfel:not(.platziert)').evaluateAll(dice=>dice.every(die=>die.textContent==='?')));
    // Even the last regular die may issue a token after both regular hands empty.
    const empty=await page.evaluate(()=>{
      pyToJs(bridge.neues_spiel('LOG_ATL_GREEN','[]'));
      pyodide.runPython('while b._spiel.phase == "verkehr": b._spiel.wirf_verkehrswuerfel()\nb._spiel.zusatz.praktikant = [1,2,3,4,5,6]\nb._spiel.am_zug = "kopilot"\nfor die in b._spiel.pilot_wuerfel + b._spiel.kopilot_wuerfel:\n die.augenzahl = 3\n die.platziert = True\nb._spiel.kopilot_wuerfel[0].platziert = False');
      resetVerkehrUi();render(pyToJs(bridge.zustand()));
      const answer=spielAktion({kind:'place',role:'kopilot',die:0,target:'training'},'ai');
      if(!answer.ergebnis.erfolg) throw new Error(JSON.stringify(answer.ergebnis));
      nachAktion(answer);
      return {role:aktuellerZustand.zusatzaktion.rolle,allEmpty:['pilot','kopilot'].every(r=>aktuellerZustand[`${r}_wuerfel_frei`].every(free=>!free))};
    });
    assert.deepEqual(empty,{role:'kopilot',allEmpty:true});
    await waitForAIBonus(page,1);
    // Fixture a human pending token while an AI rating is still uncommitted.
    await page.evaluate(()=>{
      pyToJs(bridge.neues_spiel('LOG_ATL_GREEN','[]'));
      pyodide.runPython('while b._spiel.phase == "verkehr": b._spiel.wirf_verkehrswuerfel()\nb._spiel.zusatz.praktikant = [1,2,3,4,5,6]\nfor die in b._spiel.pilot_wuerfel + b._spiel.kopilot_wuerfel: die.augenzahl = 3');
      const answer=pyToJs(bridge.platziere('pilot',0,'training'));
      if(!answer.ergebnis.erfolg) throw new Error(JSON.stringify(answer.ergebnis));
      resetVerkehrUi();render(answer.zustand);
    });
    const before=(await sessions(page))[0].events.length;
    await page.waitForTimeout(800);
    assert.equal((await sessions(page))[0].events.length,before,'AI must wait for the human pending token');
    await page.locator('#ai-rating-up').click();
    assert.ok(await page.locator('.bonus-target').count()>0);
    await page.locator('.bonus-target').first().click();
    await page.waitForTimeout(80);
    await page.locator('#menue-btn').click();
    data=(await sessions(page))[0];
    const human=data.events.filter(e=>e.actor==='human' && e.action.kind==='bonus_place');
    assert.equal(human.length,1);
    assert.ok(human[0].training_compatible && Number.isInteger(human[0].action_id));
    assert.equal(human[0].decision.role,'pilot');
    assert.equal(human[0].decision.observation.length,489);
    assert.ok(data.events.some(e=>e.actor==='ai' && e.feedback?.value===1 && e.feedback.committed && e.feedback.explicit && e.feedback.trigger==='thumb'));
    assert.ok(data.events.every(e=>!e.decision?.public_state || !('own_dice' in e.decision.public_state)));
    assert.deepEqual(errors,[]);
    console.log('✓ Intern profile-10 runtime: real NN bonus actions, pending role, empty regular hands, blocked human AI-token clicks, private partner invariance, one recorded human bonus and committed thumbs');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
