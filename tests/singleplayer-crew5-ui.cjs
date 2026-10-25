/* Actual Crew-5 preview and immediate feedback QA. No policy overrides,
 * synthetic catalogue entries, uploads, training or qualification evidence. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const {chooseModel,chooseRoute} = require('./singleplayer-setup.cjs');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),crypto=require('node:crypto');

const web=path.resolve(__dirname,'../frontend/web');
const pageUrl=process.env.COCKPIT_TEST_PAGE_URL || `${process.env.COCKPIT_TEST_URL || 'http://127.0.0.1:8000'}/frontend/web/`;
const modelId='crew5-leak-preview-v1/best.pt';
const assetSha='19e7a04826a9fb327cae2e1c8ac6d8d760c9ad0d46604e7f28a902d1dc41168d';
const rates={adaptation:5,anticipation:15,control:15,mastery:10,synchronisation:20,'working-together':0};
const source=fs.readFileSync(path.join(web,'js/ai-models.js'),'utf8'),sandbox={window:{}};
vm.runInNewContext(source,sandbox);
const catalog=JSON.parse(JSON.stringify(sandbox.window.COCKPIT_AI_CATALOG));
const actual=catalog.models.find(model=>model.id===modelId);
assert.ok(actual,'The real Crew-5 release must already be exported');
assert.equal(catalog.models.filter(model=>model.id!==modelId).length,74,'All74 older model declarations must remain');
assert.equal(actual.assistance_version,12);
assert.equal(actual.fingerprint,assetSha);
assert.equal(actual.url,`models/${assetSha}.json`);
assert.equal(actual.quality.approved,false);
assert.equal(actual.preview.enabled,true);
assert.equal(actual.preview.user_requested,true);
assert.equal(actual.preview.evaluation_kind,'development');
assert.deepEqual(actual.supported_airports,['LOG_ATL_YELLOW']);
assert.equal(actual.preview.supported_cases.length,6);
const assetBytes=fs.readFileSync(path.join(web,actual.url));
assert.equal(crypto.createHash('sha256').update(assetBytes).digest('hex'),assetSha);
const asset=JSON.parse(assetBytes);
assert.equal(asset.format,4);
assert.equal(asset.guide_margin,12);
assert.equal(asset.model_config.guide_margin,12);
assert.equal(asset.schema.version,3);
assert.equal(asset.schema.features.length,489);
assert.equal(asset.schema.actions.length,217);
for(const [card,percent] of Object.entries(rates)) {
  const key=`LOG_ATL_YELLOW|${card}`, result=actual.preview.case_results[key];
  assert.deepEqual(result,{games:20,wins:percent/5,win_rate:percent/100});
  assert.ok(actual.preview.supported_cases.some(row=>row.airport==='LOG_ATL_YELLOW'
    && row.abilities.length===1 && row.abilities[0]===card));
}

const sessions=page=>page.evaluate(async()=>{
  const db=await new Promise((resolve,reject)=>{
    const request=indexedDB.open('flyteam-learning-v1',2);
    request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);
  });
  return new Promise((resolve,reject)=>{
    const request=db.transaction('sessions').objectStore('sessions').getAll();
    request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);
  });
});
const activeSession=async(page,humanRole)=>(await sessions(page))
  .filter(session=>session.model?.id===modelId && session.human_role===humanRole)
  .sort((a,b)=>b.created_at.localeCompare(a.created_at))[0];

async function waitForRealAIAndHumanInput(page,humanRole) {
  for(let attempt=0;attempt<150;attempt++) {
    await page.waitForTimeout(100);
    if(await page.locator('#ai-resume').count()) throw new Error(await page.locator('.ai-paused').innerText());
    const recording=await activeSession(page,humanRole);
    if(!recording?.events.some(event=>event.actor==='ai')) continue;
    const state=await page.evaluate(()=>({status:aktuellerZustand.status,
      role:aktuellerZustand.zusatzaktion?.rolle || aktuellerZustand.kooperation?.wartet_auf || aktuellerZustand.am_zug,
      reroll:Singleplayer.rerollPending()}));
    const humanReroll=await page.locator(`#neuwurf-dialog .${humanRole} .neuwurf-bestaetigen`).isVisible().catch(()=>false);
    if(humanReroll) {
      // Complete the native human choice before testing the global undo
      // control; that control is intentionally disabled in a reroll dialog.
      const available=page.locator(`#neuwurf-dialog .${humanRole} .wuerfel:not(:disabled)`);
      if(await available.count()) await available.first().click();
      await page.locator(`#neuwurf-dialog .${humanRole} .neuwurf-bestaetigen`).click();
      continue;
    }
    if(state.status!=='laeuft' || state.role===humanRole && !state.reroll) return recording;
  }
  throw new Error(`Crew5 did not return control or a reroll choice to human ${humanRole}`);
}

async function waitForRating(page,humanRole,predicate) {
  for(let attempt=0;attempt<40;attempt++) {
    const recording=await activeSession(page,humanRole);
    const event=recording?.events.find(predicate);
    if(event) return {recording,event};
    await page.waitForTimeout(50);
  }
  throw new Error('Immediate feedback was not persisted to IndexedDB');
}

(async()=>{
  const browser=await chromium.launch({headless:true,
    executablePath:process.env.COCKPIT_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  try {
    const context=await browser.newContext({viewport:{width:390,height:844},serviceWorkers:'block'}),errors=[];
    // Real catalogue and real model asset are deliberately not intercepted.
    await context.route('**/js/cloud-config.js',route=>route.fulfill({
      contentType:'application/javascript',body:'window.COCKPIT_LEARNING_CLOUD={};'}));
    const page=await context.newPage(),loadedAssets=[];
    page.on('pageerror',error=>errors.push(error.message));
    page.on('response',response=>{
      if(response.url().endsWith(actual.url)) loadedAssets.push(response.body().then(bytes=>
        crypto.createHash('sha256').update(bytes).digest('hex')));
    });
    await page.goto(pageUrl);
    await page.getByRole('button',{name:/Singleplayer/}).click();
    assert.equal(await page.locator('#solo-model').inputValue(),'crew-basegame-v1/best.pt');
    assert.deepEqual(await page.evaluate(()=>COCKPIT_AI_CATALOG.models),catalog.models,
      'Browser must retain the real full catalogue, including every older model');
    await page.locator('[data-mode="feedback"]').click();
    await chooseModel(page,modelId);
    await chooseRoute(page,'ATL-yellow');
    assert.match(await page.locator('#solo-model option:checked').innerText(),/Crew 3.*Entwicklung/);
    assert.equal(await page.locator('#solo-abilities option').count(),6);
    await page.locator('#solo-consent').check();
    for(const [card,percent] of Object.entries(rates)) {
      await page.locator('#solo-abilities').selectOption(`LOG_ATL_YELLOW|${card}`);
      const description=await page.locator('#solo-description').innerText();
      assert.match(description,new RegExp(`Entwicklungstest im KI-Selbstspiel: ${percent} %`));
      assert.match(description,/noch nicht unabhängig qualifiziert/);
      assert.doesNotMatch(description,/Getestet im KI-Selbstspiel/);
      assert.equal(await page.locator('#solo-start').isDisabled(),false,
        `Explicit ${card} preview must be playable, including0% working-together`);
    }
    await page.screenshot({path:'/tmp/cockpit-crew5-menu.png',fullPage:true});

    for(const humanRole of ['pilot','kopilot']) {
      await chooseModel(page,modelId,humanRole);
      await chooseRoute(page,'ATL-yellow');
      await page.locator('#solo-abilities').selectOption('LOG_ATL_YELLOW|adaptation');
      await page.locator('#solo-consent').check();
      await page.locator('#solo-start').click();
      await page.locator('#spiel-ui').waitFor({state:'visible',timeout:90000});
      const initial=await page.evaluate(role=>{
        // Explicit equal-face technical hands avoid a random immediate stall.
        // No model tensor, logit, action mask or reference is overridden.
        pyodide.runPython('import backend.bridge as b\nwhile b._spiel.phase == "verkehr": b._spiel.wirf_verkehrswuerfel()\nfor die in b._spiel.pilot_wuerfel + b._spiel.kopilot_wuerfel: die.augenzahl=3');
        resetVerkehrUi();render(pyToJs(bridge.zustand()));
        const card=spielModulAktion(role,'adaptation',{wuerfel_index:2});
        if(!card.ergebnis.erfolg) throw new Error(JSON.stringify(card.ergebnis));
        nachAktion(card);
        if(role==='pilot') {
          const answer=spielAktion({kind:'place',role,die:0,target:'ruder'});
          if(!answer.ergebnis.erfolg) throw new Error(JSON.stringify(answer.ergebnis));
          nachAktion(answer);
        }
        return {cards:aktuellerZustand.faehigkeitskarten,
          humanFace:aktuellerZustand[`${role}_wuerfel`][2],
          available:aktuellerZustand.anpassung_verfuegbar[role]};
      },humanRole);
      assert.deepEqual(initial.cards,['adaptation']);
      assert.equal(initial.humanFace,4);
      assert.equal(initial.available,false,'The actual native adaptation card must be consumed');
      const recording=await waitForRealAIAndHumanInput(page,humanRole);
      const aiRole=humanRole==='pilot'?'kopilot':'pilot';
      assert.equal(recording.model.id,modelId);
      assert.equal(recording.model.assistance_version,12);
      assert.equal(recording.model.fingerprint,assetSha);
      assert.deepEqual(recording.scenario.ability_ids,['adaptation']);
      assert.equal(recording.scenario.case_key,'LOG_ATL_YELLOW|adaptation');
      assert.equal(recording.schema_version,3);
      assert.ok(recording.consent.accepted_at);
      const adaptation=recording.events.find(event=>event.actor==='human' && event.action.role===humanRole
        && (event.action.kind==='adaptation' || event.action.kind==='module_action'
          && event.action.module_action==='adaptation'));
      assert.ok(adaptation,'Native human card use must be recorded, including a legal offturn use');
      assert.equal(adaptation.training_compatible,humanRole==='pilot',
        'A legal offturn card use must not invent an onturn policy label');
      if(humanRole==='kopilot') {
        assert.equal(adaptation.action_id,null);
        assert.equal(adaptation.decision,null);
      }
      const aiEvents=recording.events.filter(event=>event.actor==='ai');
      assert.ok(aiEvents.length>0);
      for(const event of aiEvents) {
        assert.equal(event.decision.role,aiRole);
        assert.equal(event.decision.observation.length,489);
        assert.equal(event.decision.action_mask.length,217);
        assert.equal(event.decision.reference_action_mask.length,217);
        assert.ok(event.decision.reference_action_mask.some(Boolean));
        assert.ok(event.decision.reference_action_mask.every((advised,index)=>!advised || event.decision.action_mask[index]));
        assert.ok(event.training_compatible && event.decision.action_mask[event.action_id]);
        assert.ok(!('own_dice' in event.decision.public_state));
        assert.ok(!('partner_dice' in event.decision.public_state));
        assert.ok(!('pilot_wuerfel' in event.decision.public_state));
        assert.ok(!('kopilot_wuerfel' in event.decision.public_state));
      }
      const recomputed=await page.evaluate(async({url,events})=>{
        const data=await (await fetch(url)).json();
        const policy=CockpitPolicy.create(data,{schema:data.schema});
        return events.map(event=>policy.select(event.decision));
      },{url:actual.url,events:aiEvents});
      assert.deepEqual(recomputed,aiEvents.map(event=>event.action_id),
        'Every recorded actual AI action must equal inference with the real Crew5 asset');
      const freeDice=page.locator(`#wuerfel-${aiRole} .wuerfel:not(.platziert)`);
      assert.ok(await freeDice.count()>0);
      assert.ok(await freeDice.evaluateAll(dice=>dice.every(die=>die.textContent==='?')));
      assert.equal(await page.locator('#ai-resume').count(),0);
      assert.equal(await page.locator('#ai-feedback-save').count(),0);
      const version=await page.evaluate(()=>aktuellerZustand.rueckgaengig_version);
      await page.locator('#ai-rating-up').click();
      const first=await waitForRating(page,humanRole,event=>event.feedback?.value===1
        && event.feedback.committed===true && event.feedback.explicit===true && event.feedback.trigger==='thumb');
      const ratedId=first.event.id,committedAt=first.event.feedback.committed_at;
      assert.ok(committedAt);
      await page.locator('#ai-rating-up').click();
      await page.waitForTimeout(60);
      let updated=(await activeSession(page,humanRole)).events.find(event=>event.id===ratedId);
      assert.equal(updated.feedback.value,1,'Repeated identical thumb is an idempotent choice');
      assert.equal(updated.feedback.committed_at,committedAt);
      await page.locator('#ai-rating-down').click();
      await waitForRating(page,humanRole,event=>event.id===ratedId && event.feedback?.value===-1
        && event.feedback.committed===true && event.feedback.trigger==='thumb');
      const countBeforeUndo=(await activeSession(page,humanRole)).events.length;
      await page.locator('#rueckgaengig-btn').click();
      await waitForRating(page,humanRole,event=>event.id===ratedId && event.feedback?.value===1
        && event.feedback.committed===true && event.feedback.explicit===true);
      await page.locator('#rueckgaengig-btn').click();
      const undone=await waitForRating(page,humanRole,event=>event.id===ratedId && event.feedback?.value===0
        && event.feedback.committed===false && event.feedback.explicit===false);
      assert.ok(!('committed_at' in undone.event.feedback));
      assert.ok(!('trigger' in undone.event.feedback));
      assert.equal(undone.recording.events.length,countBeforeUndo);
      assert.equal(undone.event.voided,false);
      assert.equal(await page.evaluate(()=>aktuellerZustand.rueckgaengig_version),version,
        'Feedback undo must never rewind the engine');
      assert.equal(await page.locator('#ai-rating-value').textContent(),'Neutral');
      assert.equal(await page.locator('#ai-resume').count(),0,'Feedback undo must not pause the AI');
      await page.locator('#ai-feedback-info-toggle').click();
      assert.equal(await page.locator('#ai-feedback-save').count(),0,'The info disclosure has no save button');
      await page.screenshot({path:`/tmp/cockpit-crew5-info-${humanRole}.png`,fullPage:true});
      await page.keyboard.press('Escape');
      await page.screenshot({path:`/tmp/cockpit-crew5-${humanRole}.png`,fullPage:true});
      await page.evaluate(()=>Singleplayer.showMenu());
      await page.locator('[data-mode="feedback"]').click();
    }
    assert.ok(loadedAssets.length>=2,'Both native role sessions must load the new real model');
    assert.ok((await Promise.all(loadedAssets)).every(sha=>sha===assetSha));
    assert.deepEqual(errors,[]);
    console.log('✓ Actual Crew5 profile12/guide12 asset: six honest rates including0%,74 older models/default preserved, native cards and both-role NN489/217 references/privacy, immediate persistent thumbs and feedback-only two-step undo; no quality/qualification claim');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
