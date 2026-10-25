/* Actual qualified OSL model. An unsupported ATL entry is injected only to test
 * the feedback gate. This never uploads technical fixture games to D1. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const pageUrl = process.env.COCKPIT_TEST_PAGE_URL || `${process.env.COCKPIT_TEST_URL || 'http://127.0.0.1:8000'}/frontend/web/`;
const catalogSource = fs.readFileSync(new URL('../frontend/web/js/ai-models.js', `file://${__filename}`), 'utf8');
const records = page => page.evaluate(async () => {
  const db = await new Promise((resolve,reject) => {const r=indexedDB.open('flyteam-learning-v1',2);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});
  return new Promise(resolve=>{const r=db.transaction('sessions').objectStore('sessions').getAll();r.onsuccess=()=>resolve(r.result);});
});
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.COCKPIT_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  try {
    const context=await browser.newContext({viewport:{width:390,height:844},serviceWorkers:'block'}), errors=[], uploads=[];
    await context.route('**/js/ai-models.js',route=>route.fulfill({contentType:'application/javascript',body:catalogSource+`
      {const model=window.COCKPIT_AI_CATALOG.models.find(m=>m.quality?.approved && m.schema?.version===3 && m.supported_airports?.includes('LOG_OSL_GREEN'));
       if(!model) throw new Error('Qualified Crew-2 OSL model missing');
       model.supported_airports=[...new Set([...model.supported_airports,'LOG_ATL_GREEN'])];}
    `}));
    await context.route('**/js/cloud-config.js',route=>route.fulfill({contentType:'application/javascript',body:'window.COCKPIT_LEARNING_CLOUD={endpoint:"https://collector.invalid/logs"};'}));
    await context.route('https://collector.invalid/logs',route=>{
      if(route.request().method()==='POST') uploads.push(route.request().postDataJSON());
      return route.fulfill({status:200,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'Content-Type,X-Upload-Token','Access-Control-Allow-Methods':'POST, OPTIONS'},body:'{}'});
    });
    const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
    await page.goto(pageUrl);
    await page.getByRole('button',{name:/Singleplayer/}).click();
    await page.locator('#solo-route').selectOption('OSL-green');
    const modelId=await page.evaluate(()=>COCKPIT_AI_CATALOG.models.find(m=>m.quality?.approved && m.schema?.version===3 && m.supported_airports?.includes('LOG_OSL_GREEN')).id);
    await page.locator('#solo-model').selectOption(modelId);
    await page.locator('[data-mode="feedback"]').click();
    assert.equal(await page.locator('#solo-route option[value="OSL-green"]').evaluate(option=>option.disabled),false);
    assert.equal(await page.locator('#solo-route option[value="ATL-green"]').evaluate(option=>option.disabled),true,
      await page.locator('#solo-route').innerHTML());
    assert.equal(await page.locator('#solo-model').inputValue(),modelId);
    await page.locator('[data-mode="examples"]').click();
    assert.equal(await page.locator('#solo-route option[value="OSL-green"]').evaluate(option=>option.disabled),true);
    await page.locator('[data-mode="feedback"]').click();
    await page.locator('#solo-route').selectOption('OSL-green');
    await page.locator('#solo-consent').check();
    await page.locator('#solo-start').click();
    await page.locator('#spiel-ui').waitFor({state:'visible',timeout:90000});
    assert.equal(await page.locator('#fuel-gauge').isVisible(),true);
    assert.equal(await page.locator('#fuel-gauge [role="meter"]').getAttribute('aria-valuenow'),'20');
    const first=await page.evaluate(()=>{
      pyodide.runPython('import backend.bridge as b\nwhile b._spiel.phase == "verkehr": b._spiel.wirf_verkehrswuerfel()\nfor die in b._spiel.pilot_wuerfel + b._spiel.kopilot_wuerfel: die.augenzahl = 3');
      resetVerkehrUi();
      render(pyToJs(bridge.zustand()));
      const answer=spielAktion({kind:'place',role:'pilot',die:0,target:'ruder'});
      nachAktion(answer);
      return {result:answer.ergebnis,phase:answer.zustand.phase,turn:answer.zustand.am_zug};
    });
    assert.equal(first.result.erfolg,true,JSON.stringify(first));
    for(let attempt=0;attempt<12;attempt++) {
      await page.waitForTimeout(750);
      if(await page.locator('#ai-resume').count()) throw new Error(await page.locator('.ai-paused').innerText());
      if(await page.evaluate(()=>aktuellerZustand.am_zug==='pilot' || aktuellerZustand.status!=='laeuft')) break;
      if(await page.locator('#neuwurf-dialog .pilot .neuwurf-bestaetigen').isVisible().catch(()=>false)) {
        const die=page.locator('#neuwurf-dialog .pilot .wuerfel:not(:disabled)').first();
        if(await die.count()) await die.click();
        await page.locator('#neuwurf-dialog .pilot .neuwurf-bestaetigen').click();
      }
    }
    assert.equal(await page.evaluate(()=>aktuellerZustand.status),'laeuft');
    assert.equal(await page.evaluate(()=>aktuellerZustand.am_zug),'pilot');
    await page.waitForFunction(()=>!document.getElementById('ai-rating-up').disabled);
    const before=(await records(page))[0];
    assert.ok(before.events.some(event=>event.actor==='ai' && event.decision?.observation.length===489 && event.decision.reference_action_mask.length===217));
    assert.ok(await page.locator('#wuerfel-kopilot .wuerfel:not(.platziert)').evaluateAll(dice=>dice.every(die=>die.textContent==='?')));
    // Keep the public fuel slot free even if the sampled model used it already.
    // This fixtures only the shared field and own hand; the real NN turn above is retained.
    await page.evaluate(()=>{
      pyodide.runPython('b._spiel.cockpit.kerosin_feld.leere()\nb._spiel.cockpit.kerosin = 20\nfor die in b._spiel.pilot_wuerfel:\n if not die.platziert: die.augenzahl = 3');
      render(pyToJs(bridge.zustand()));
    });
    await page.locator('#ai-rating-up').click();
    await page.locator('#wuerfel-pilot .wuerfel:not(.platziert)').first().click();
    await page.locator('#fuel-action .feld-zelle').click();
    assert.equal(await page.locator('#fuel-gauge [role="meter"]').getAttribute('aria-valuenow'),'17');
    await page.waitForFunction(async()=>{
      const db=await new Promise(resolve=>{const r=indexedDB.open('flyteam-learning-v1',2);r.onsuccess=()=>resolve(r.result);});
      return new Promise(resolve=>{const r=db.transaction('sessions').objectStore('sessions').getAll();r.onsuccess=()=>resolve(r.result.some(session=>session.events.some(event=>event.actor==='human' && event.action?.target==='kerosin')));});
    });
    await page.locator('#menue-btn').click();
    const data=(await records(page))[0],fuel=data.events.find(event=>event.actor==='human' && event.action?.target==='kerosin');
    assert.ok(fuel.training_compatible);
    assert.equal(fuel.decision.observation.length,489);
    assert.equal(fuel.decision.action_mask.length,217);
    assert.ok(data.events.some(event=>event.actor==='ai' && event.feedback?.value===1 && event.feedback.committed && event.feedback.trigger==='human_action'));
    assert.ok(data.events.every(event=>!event.decision?.public_state || !('own_dice' in event.decision.public_state)));
    assert.ok(data.events.every(event=>!event.public_after || !('kopilot_wuerfel' in event.public_after)));
    await page.waitForFunction(()=>LearningCloud.enabled());
    await page.waitForTimeout(2200);
    assert.ok(uploads.some(envelope=>envelope.schema.version===3 && envelope.session.events.some(event=>event.action?.target==='kerosin')));
    assert.deepEqual(errors,[]);
    console.log('✓ Actual Crew-2 OSL fixture: schema-3 inference/privacy, scoped feedback-route gate, real human kerosene UI dispatch and neutral/positive feedback commit, schema-3 upload envelope');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
