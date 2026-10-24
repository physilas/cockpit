/* Real engine + exported model; optional cloud endpoint is intercepted. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const base = process.env.COCKPIT_TEST_URL || 'http://127.0.0.1:8000';
const rows = page => page.evaluate(async () => {
  const db = await new Promise((resolve,reject) => { const r=indexedDB.open('flyteam-learning-v1',2); r.onsuccess=()=>resolve(r.result); r.onerror=()=>reject(r.error); });
  return new Promise(resolve => { const r=db.transaction('sessions').objectStore('sessions').getAll();r.onsuccess=()=>resolve(r.result); });
});
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.COCKPIT_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  try {
    const context = await browser.newContext({viewport:{width:390,height:844},serviceWorkers:'block'});
    let uploads=[], fail=true; const errors=[];
    await context.route('**/js/cloud-config.js',route=>route.fulfill({contentType:'application/javascript',body:'window.COCKPIT_LEARNING_CLOUD={endpoint:"https://collector.invalid/logs"};'}));
    await context.route('https://collector.invalid/logs',async route=>{
      if(route.request().method()==='OPTIONS') { await route.fulfill({status:204,headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'Content-Type,X-Upload-Token','Access-Control-Allow-Methods':'POST'}});return; }
      uploads.push({data:route.request().postDataJSON(),token:route.request().headers()['x-upload-token']});
      await route.fulfill({status:fail?503:200,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'*'},body:'{}'});
    });
    const page=await context.newPage(); page.on('pageerror',e=>errors.push(e.message));
    await page.goto(`${base}/frontend/web/`);
    await page.getByRole('button',{name:/Singleplayer/}).click();
    assert.ok(await page.locator('#solo-model option').count()>=1);
    const goodModel = await page.locator('#solo-model').inputValue();
    assert.ok(await page.evaluate(() => [...document.querySelectorAll('#solo-model option')].every(o =>
      COCKPIT_AI_CATALOG.models.find(m => m.id === o.value)?.quality?.approved === true)));
    const availableRoutes = await page.locator('#solo-route option').evaluateAll(options => options.map(o => o.value).sort());
    const expectedRoutes = await page.evaluate(() => LANDING_CATALOG.scenarios.filter(s => !s.modules.length && !s.ability_count).map(s => s.id).sort());
    assert.deepEqual(availableRoutes, expectedRoutes);
    await page.locator('[data-mode="feedback"]').click();
    assert.equal(await page.locator('#solo-start').isDisabled(),true);
    assert.equal(uploads.length,0);
    await page.screenshot({path:'/tmp/flyteam-singleplayer-menu.png',fullPage:true});
    await page.locator('#solo-consent').check();
    await page.locator('#solo-route').selectOption('HND-green');
    assert.ok(await page.locator('#solo-model option').count()>=1);
    await page.locator('#solo-route').selectOption('custom-MUC');
    await page.locator('#solo-model').selectOption(goodModel);
    await page.locator('#solo-start').click();
    await page.locator('#spiel-ui').waitFor({state:'visible',timeout:90000});
    await page.evaluate(()=>{
      pyodide.runPython('import backend.bridge as b\nfor d in b._spiel.pilot_wuerfel + b._spiel.kopilot_wuerfel: d.augenzahl = 3');
      render(pyToJs(bridge.zustand()));
      nachAktion(spielAktion({kind:'place',role:'pilot',die:0,target:'ruder',index:null}));
    });
    for (let attempt=0;attempt<12;attempt++) {
      await page.waitForTimeout(1000);
      if(await page.locator('#ai-resume').count()) throw new Error(await page.locator('.ai-paused').innerText());
      if(await page.evaluate(()=>aktuellerZustand.am_zug==='pilot' || aktuellerZustand.status!=='laeuft')) break;
      if(await page.locator('#neuwurf-dialog .pilot .neuwurf-bestaetigen').isVisible().catch(()=>false)) {
        const die=page.locator('#neuwurf-dialog .pilot .wuerfel:not(:disabled)').first();
        if(await die.count()) await die.click();
        await page.locator('#neuwurf-dialog .pilot .neuwurf-bestaetigen').click();
      }
    }
    await page.waitForFunction(()=>!document.getElementById('ai-feedback').classList.contains('versteckt') && (aktuellerZustand.am_zug==='pilot' || aktuellerZustand.status!=='laeuft'),{},{timeout:5000});
    assert.equal(await page.locator('#ai-rating').inputValue(),'0');
    await page.locator('#ai-rating').fill('2');
    await page.screenshot({path:'/tmp/flyteam-singleplayer-feedback.png',fullPage:true});
    if(await page.evaluate(()=>aktuellerZustand.status==='laeuft')) {
      assert.equal(await page.evaluate(()=>spielAktion({kind:'place',role:'pilot',die:0,target:'ruder',index:null}).ergebnis.erfolg),false);
      assert.equal(await page.locator('#ai-rating').inputValue(),'2');
      await page.evaluate(()=>{
        const d=pyToJs(aiBridge.decision('pilot','null',0,256));
        const i=d.action_mask.findIndex((ok,i)=>ok && COCKPIT_AI_CATALOG.schema.actions[i].kind==='place');
        const a=COCKPIT_AI_CATALOG.schema.actions[i],s=COCKPIT_AI_CATALOG.schema.slots[a.slot];
        const answer=spielAktion({kind:'place',role:'pilot',die:a.die,target:s.target,index:s.index,radio_index:s.radio_index});
        if(!answer.ergebnis.erfolg) throw new Error('Human fixture action failed');
        nachAktion(answer);
      });
    } else await page.locator('#ai-feedback-save').click();
    await page.waitForTimeout(100);
    let data=await rows(page), feedback=data.find(r=>r.mode==='feedback');
    assert.ok(feedback.consent.accepted_at);
    assert.ok(feedback.events.some(e=>e.feedback?.value===2 && e.feedback.committed && e.feedback.explicit));
    assert.ok(feedback.events.every(e=>!e.decision || (!('own_dice' in e.decision.public_state) && !('pilot_wuerfel' in e.decision.public_state))));
    assert.ok(feedback.events.every(e=>!e.public_after || !('own_dice' in e.public_after)));
    assert.ok(feedback.events.filter(e=>e.decision).every(e=>e.decision.observation.length===349 && e.decision.action_mask.length===121));
    await page.locator('#menue-btn').click();
    await page.getByRole('button',{name:/Singleplayer/}).click();
    await page.locator('[data-mode="examples"]').click();
    await page.locator('#solo-consent').check();
    await page.locator('#solo-route').selectOption('custom-MUC');
    await page.locator('#solo-start').click();
    await page.locator('#spiel-ui').waitFor({state:'visible'});
    await page.evaluate(()=>{
      pyodide.runPython('for d in b._spiel.pilot_wuerfel + b._spiel.kopilot_wuerfel: d.augenzahl = 3');
      nachAktion(spielAktion({kind:'place',role:'pilot',die:0,target:'ruder'}));
      nachAktion(spielAktion({kind:'place',role:'kopilot',die:0,target:'ruder'}));
    });
    await page.waitForTimeout(100);
    data=await rows(page);const examples=data.find(r=>r.mode==='examples');
    assert.deepEqual(examples.events.map(e=>e.decision.role),['pilot','kopilot']);
    assert.ok(examples.events.every(e=>e.training_compatible));
    assert.equal(await page.locator('#ai-feedback').isVisible(),false);
    await page.locator('#s-neuwurf button').click();
    assert.equal(await page.locator('#neuwurf-dialog').isVisible(),true);
    await page.locator('#neuwurf-dialog .pilot [data-index="1"]').click();
    await page.locator('#neuwurf-dialog .pilot .neuwurf-bestaetigen').click();
    await page.locator('#neuwurf-dialog .kopilot .neuwurf-bestaetigen').click();
    await page.locator('#neuwurf-dialog').waitFor({state:'hidden'});
    await page.locator('#rueckgaengig-btn').click();
    await page.waitForTimeout(100);
    data=await rows(page);
    assert.ok(data.find(r=>r.mode==='examples').events.some(e=>e.action.kind==='reroll_select' && e.voided));
    fail=false;
    await page.waitForFunction(async()=>{
      const db=await new Promise(resolve=>{const r=indexedDB.open('flyteam-learning-v1',2);r.onsuccess=()=>resolve(r.result)});
      return new Promise(resolve=>{const r=db.transaction('outbox').objectStore('outbox').count();r.onsuccess=()=>resolve(r.result===0)});
    },{},{timeout:30000});
    assert.ok(uploads.length>0);
    assert.ok(uploads.every(r=>/^[a-f0-9]{64}$/.test(r.token)));
    assert.ok(uploads.every(r=>r.data.session.consent && r.data.format==='flyteam-learning-session'));
    assert.equal(await page.locator('#ai-session-bar').innerText().then(t=>/Cloud|Supabase|verbinden/.test(t)),false);
    await page.reload();
    data=await rows(page); assert.equal(data.length,2);
    await page.getByRole('button',{name:/Singleplayer/}).click();
    await page.locator('[data-mode="feedback"]').click();
    await page.locator('#solo-model').selectOption(goodModel);
    await page.locator('#solo-role').selectOption('kopilot');
    await page.locator('#solo-consent').check(); await page.locator('#solo-start').click();
    await page.locator('#spiel-ui').waitFor({state:'visible',timeout:90000});
    await page.evaluate(()=>{
      pyodide.runPython('import backend.bridge as b\nb._spiel.pilot_wuerfel[0].augenzahl = 6\nb._spiel.kopilot_wuerfel[0].augenzahl = 1\nb._spiel.cockpit.ruder_kopilot.platziere(b._spiel.kopilot_wuerfel[0])');
      nachAktion(spielAktion({kind:'place',role:'pilot',die:0,target:'ruder'},'ai'));
    });
    assert.equal(await page.evaluate(()=>aktuellerZustand.status),'verloren');
    assert.equal(await page.locator('#ai-rating').inputValue(),'0');
    assert.ok(await page.locator('#wuerfel-pilot .wuerfel:not(.platziert)').evaluateAll(els=>els.every(e=>e.textContent==='?')));
    await page.locator('#ai-feedback-save').click();
    await page.waitForTimeout(100);
    data=await rows(page);
    assert.ok(data.some(r=>r.human_role==='kopilot' && r.events.some(e=>e.feedback?.committed && !e.feedback.explicit && e.feedback.value===0)));
    assert.equal(await page.locator('#ai-resume').count(),0);
    assert.deepEqual(errors,[]);
    console.log('✓ Model selector, mobile menu, consent, real model turns, feedback/invalid-move/default-zero/terminal commit, both roles and privacy, examples, reroll/undo, IndexedDB persistence, cloud retry and quiet upload');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
