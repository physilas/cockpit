/* Isolated schema-3 card fixtures; no release evidence and no real uploads. */
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs');
const pageUrl=process.env.COCKPIT_TEST_PAGE_URL || `${process.env.COCKPIT_TEST_URL || 'http://127.0.0.1:8000'}/frontend/web/`;
const source=fs.readFileSync(new URL('../frontend/web/js/ai-models.js',`file://${__filename}`),'utf8');
const cards=['control','mastery','synchronisation','adaptation','anticipation','working-together'];
const rows=page=>page.evaluate(async()=>{
  const db=await new Promise(resolve=>{const r=indexedDB.open('flyteam-learning-v1',2);r.onsuccess=()=>resolve(r.result);});
  return new Promise(resolve=>{const r=db.transaction('sessions').objectStore('sessions').getAll();r.onsuccess=()=>resolve(r.result);});
});
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.COCKPIT_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  try {
    const context=await browser.newContext({viewport:{width:390,height:844},serviceWorkers:'block'}),errors=[];
    await context.route('**/js/ai-models.js',route=>route.fulfill({contentType:'application/javascript',body:source+`
      {const base=window.COCKPIT_AI_CATALOG.models.find(m=>m.name==='Crew 2'), cards=${JSON.stringify(cards)};
       window.COCKPIT_AI_CATALOG.models.unshift({...base,id:'fixture-cards/best.pt',name:'Card runtime fixture (Test)',
         assistance_version:11,supported_airports:['LOG_ATL_YELLOW','LOG_PRG_GREEN'],quality:{approved:false},
         preview:{enabled:true,evaluation_kind:'development',route_results:{LOG_ATL_YELLOW:{win_rate:.99}},
           supported_cases:[...cards.map(card=>({airport:'LOG_ATL_YELLOW',abilities:[card]})),
             {airport:'LOG_ATL_YELLOW',abilities:['control','mastery']},{airport:'LOG_ATL_YELLOW',abilities:['unknown']},
             {airport:'LOG_PRG_GREEN',abilities:['control']}],
           case_results:Object.fromEntries(cards.map((card,i)=>['LOG_ATL_YELLOW|'+card,{games:10,wins:i+1,win_rate:(i+1)/10}]))}});}
    `}));
    await context.route('**/js/cloud-config.js',route=>route.fulfill({contentType:'application/javascript',body:'window.COCKPIT_LEARNING_CLOUD={};'}));
    const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
    await page.goto(pageUrl);await page.getByRole('button',{name:/Singleplayer/}).click();
    assert.equal(await page.locator('#solo-model').inputValue(),'crew-basegame-v1/best.pt');
    if(await page.locator('#solo-route option[value="PRG-green"]').count()) {
      // Another explicit release may now legitimately expose PRG. The invalid
      // one-card fixture must remain unavailable on this two-card route.
      await page.locator('#solo-route').selectOption('PRG-green');
      assert.equal(await page.locator('#solo-model option[value="fixture-cards/best.pt"]').count(),0,
        'A route-level hint cannot enable an invalid card count');
      await page.locator('#solo-route').selectOption('custom-MUC');
    }
    await page.locator('[data-mode="feedback"]').click();
    // The actual exported weak specialist is visible without a fake approval.
    const actual=await page.evaluate(()=>COCKPIT_AI_CATALOG.models.find(model=>model.id==='crew4-leak-preview-v1/best.pt'));
    assert.ok(actual?.preview.enabled && actual.quality.approved===false);
    assert.equal(actual.assistance_version,11);
    assert.equal(actual.preview.supported_cases.length,6);
    await page.locator('#solo-route').selectOption('ATL-yellow');
    await page.locator('#solo-model').selectOption(actual.id);
    await page.locator('#solo-consent').check();
    for(const card of cards) {
      await page.locator('#solo-abilities').selectOption('LOG_ATL_YELLOW|'+card);
      const rate=actual.preview.case_results['LOG_ATL_YELLOW|'+card].win_rate;
      assert.match(await page.locator('#solo-description').innerText(),new RegExp(`Entwicklungstest im KI-Selbstspiel: ${rate*100} %`));
      assert.match(await page.locator('#solo-description').innerText(),/noch nicht unabhängig qualifiziert/);
      assert.equal(await page.locator('#solo-start').isDisabled(),false,'Zero-win previews remain intentionally playable');
    }
    await page.locator('#solo-abilities').selectOption('LOG_ATL_YELLOW|adaptation');
    await page.screenshot({path:'/tmp/cockpit-crew4-menu.png',fullPage:true});
    await page.locator('#solo-start').click();
    await page.locator('#spiel-ui').waitFor({state:'visible',timeout:90000});
    await page.evaluate(()=>{
      pyodide.runPython('import backend.bridge as b\nwhile b._spiel.phase == "verkehr": b._spiel.wirf_verkehrswuerfel()\nfor die in b._spiel.pilot_wuerfel + b._spiel.kopilot_wuerfel: die.augenzahl=3');
      resetVerkehrUi();render(pyToJs(bridge.zustand()));
      const answer=spielAktion({kind:'place',role:'pilot',die:0,target:'ruder'});
      if(!answer.ergebnis.erfolg) throw new Error(JSON.stringify(answer.ergebnis));
      nachAktion(answer);
    });
    let actualSession;
    for(let attempt=0;attempt<40;attempt++) {
      await page.waitForTimeout(100);
      if(await page.locator('#ai-resume').count()) throw new Error(await page.locator('.ai-paused').innerText());
      actualSession=(await rows(page)).find(session=>session.model.id===actual.id);
      if(actualSession?.events.some(event=>event.actor==='ai')) break;
    }
    assert.ok(actualSession?.events.some(event=>event.actor==='ai' && event.training_compatible && event.decision.observation.length===489));
    assert.deepEqual(actualSession.scenario.ability_ids,['adaptation']);
    assert.equal(actualSession.scenario.case_key,'LOG_ATL_YELLOW|adaptation');
    await page.evaluate(()=>Singleplayer.showMenu());
    await page.locator('[data-mode="feedback"]').click();
    for(const card of cards) {
      await page.locator('#solo-route').selectOption('ATL-yellow');
      await page.locator('#solo-model').selectOption('fixture-cards/best.pt');
      assert.match(await page.locator('#solo-route option:checked').innerText(),/Kerosinleck.*1 Karte/);
      assert.equal(await page.locator('#solo-abilities option').count(),6);
      await page.locator('#solo-abilities').selectOption('LOG_ATL_YELLOW|'+card);
      assert.doesNotMatch(await page.locator('#solo-description').innerText(),/99 %/);
      await page.locator('#solo-consent').check();
      if(card==='control') {
        await page.evaluate(()=>{const option=new Option('unlisted','LOG_ATL_YELLOW|unknown');document.getElementById('solo-abilities').add(option);document.getElementById('solo-abilities').value=option.value;});
        await page.locator('#solo-start').click();
        assert.equal(await page.locator('#spiel-ui').isVisible(),false,'Launch must revalidate the selected case');
        await page.locator('#solo-abilities').selectOption('LOG_ATL_YELLOW|control');
      }
      await page.locator('#solo-start').click();
      await page.locator('#spiel-ui').waitFor({state:'visible',timeout:90000});
      const result=await page.evaluate(async card=>{
        pyodide.runPython('import backend.bridge as b\nwhile b._spiel.phase == "verkehr": b._spiel.wirf_verkehrswuerfel()\nfor die in b._spiel.pilot_wuerfel + b._spiel.kopilot_wuerfel: die.augenzahl = 3');
        resetVerkehrUi();render(pyToJs(bridge.zustand()));
        const execute=(action,actor='human')=>{const answer=spielAktion(action,actor);if(!answer.ergebnis.erfolg) throw new Error(JSON.stringify(answer.ergebnis));nachAktion(answer);return answer;};
        let extra={};
        if(card==='adaptation') {
          pyodide.runPython('b._spiel.am_zug="kopilot"');render(pyToJs(bridge.zustand()));
          const answer=spielModulAktion('pilot','adaptation',{wuerfel_index:2});
          if(!answer.ergebnis.erfolg) throw new Error(JSON.stringify(answer.ergebnis));
          nachAktion(answer);extra.face=aktuellerZustand.pilot_wuerfel[2];
        } else if(card==='anticipation') {
          const answer=spielModulAktion('pilot','anticipation',{wuerfel_index:2});
          if(!answer.ergebnis.erfolg) throw new Error(JSON.stringify(answer.ergebnis));
          nachAktion(answer);
        } else if(card==='working-together') {
          nachAktion(spielModulAktion('pilot','kooperation_start'));
          nachAktion(spielModulAktion('pilot','kooperation_wahl',{wuerfel_index:2}));
          nachAktion(spielModulAktion('pilot','kooperation_bestaetigen'));
          nachAktion(spielModulAktion('pilot','kooperation_abbrechen',{kooperation_id:aktuellerZustand.kooperation.id}));
          await new Promise(resolve=>setTimeout(resolve,800));
          if(document.getElementById('ai-resume') || aktuellerZustand.kooperation) throw new Error('Cancelled swap left a stale AI action');
          nachAktion(spielModulAktion('pilot','kooperation_start'));
          nachAktion(spielModulAktion('pilot','kooperation_wahl',{wuerfel_index:2}));
          nachAktion(spielModulAktion('pilot','kooperation_bestaetigen'));
          const revision=aktuellerZustand.rueckgaengig_version;
          execute({kind:'swap_choose',role:'kopilot',die:3,cooperation_id:aktuellerZustand.kooperation.id},'ai');
          extra.revisions=aktuellerZustand.rueckgaengig_version-revision;
          extra.swapped=Boolean(aktuellerZustand.kooperation_ergebnis);
        } else if(card==='synchronisation') {
          pyodide.runPython('b._spiel.am_zug="kopilot"\nb._spiel.cockpit.kaffeetassen=2\nb._spiel.pilot_wuerfel[0].augenzahl=1\nb._spiel.kopilot_wuerfel[0].augenzahl=1');
          render(pyToJs(bridge.zustand()));
          execute({kind:'place',role:'kopilot',die:0,target:'landeklappe',index:0},'ai');
          execute({kind:'place',role:'pilot',die:0,target:'fahrwerk',index:0});
          // Synchronisation gives the shared die to the partner of the player
          // placing the second coloured die; that is the AI in this fixture.
          if(aktuellerZustand.zusatzaktion.rolle!=='kopilot') throw new Error('Unexpected Synchronisation actor');
          execute({kind:'bonus_roll',role:'kopilot'},'ai');
          execute({kind:'bonus_coffee',role:'kopilot',delta:aktuellerZustand.zusatzaktion.wert>1 ? -1 : 1},'ai');
          const t=aktuellerZustand.zusatzaktion.ziele[0];
          execute({kind:'bonus_place',role:'kopilot',target:t.ziel,index:t.index ?? null,radio_index:t.funk_feld,target_owner:t.ziel_besitzer},'ai');
          extra.pending=Boolean(aktuellerZustand.zusatzaktion);
        }
        const enabled=[...aktuellerZustand.faehigkeitskarten];
        Singleplayer.stop('fixture_finished');
        return {enabled,...extra};
      },card);
      assert.deepEqual(result.enabled,[card]);
      if(card==='adaptation') assert.equal(result.face,4);
      if(card==='working-together') {assert.equal(result.revisions,1);assert.equal(result.swapped,true);}
      if(card==='synchronisation') assert.equal(result.pending,false);
      // Persistence is intentionally queued. Wait for the stopped snapshot,
      // rather than accidentally asserting an intermediate action revision.
      let session;
      for(let attempt=0;attempt<50;attempt++) {
        session=(await rows(page)).filter(s=>s.model.id==='fixture-cards/best.pt' && s.scenario.case_key==='LOG_ATL_YELLOW|'+card)
          .sort((a,b)=>b.created_at.localeCompare(a.created_at))[0];
        if(session?.status==='aborted') break;
        await page.waitForTimeout(100);
      }
      assert.equal(session?.status,'aborted','The final recording revision must be persisted');
      assert.deepEqual(session.scenario.ability_ids,[card]);
      assert.equal(session.scenario.case_key,'LOG_ATL_YELLOW|'+card);
      if(card==='adaptation') assert.ok(session.events.some(e=>e.action.kind==='module_action' && e.action_id===null && e.decision===null));
      if(card==='working-together') {
        const event=session.events.find(e=>e.actor==='ai' && e.action.kind==='swap_choose');
        assert.equal(event.action.die,3);assert.ok(event.training_compatible);
      }
      assert.ok(session.events.every(e=>!e.decision?.public_state || !('own_dice' in e.decision.public_state)));
      if(await page.locator('#trade-dialog[open] .trade-continue').count())
        await page.locator('#trade-dialog .trade-continue').click();
      await page.getByRole('button',{name:/☰ Menü/}).click();
      await page.getByRole('button',{name:/Singleplayer/}).click();
      await page.locator('[data-mode="feedback"]').click();
    }
    assert.deepEqual(errors,[]);
    console.log('✓ Explicit preview card sets/launch/session identity, all six engine cards, atomic typed swap, offturn adaptation, shared bonus actions and unchanged default');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
