/* Explicit mixed zero-card/card preview fixture, no release or win evidence. */
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs');
const {chooseMode,chooseModel,chooseRoute,chooseAbilities,leaveGame} = require('./singleplayer-setup.cjs');
const pageUrl=process.env.COCKPIT_TEST_PAGE_URL || `${process.env.COCKPIT_TEST_URL || 'http://127.0.0.1:8000'}/frontend/web/`;
const source=fs.readFileSync(new URL('../frontend/web/js/ai-models.js',`file://${__filename}`),'utf8');
const fixtureId='fixture-mixed-preview/best.pt';
const rows=page=>page.evaluate(async()=>{
  const db=await new Promise(resolve=>{const request=indexedDB.open('flyteam-learning-v1',2);request.onsuccess=()=>resolve(request.result);});
  return new Promise(resolve=>{const request=db.transaction('sessions').objectStore('sessions').getAll();request.onsuccess=()=>resolve(request.result);});
});
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.COCKPIT_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  try {
    const context=await browser.newContext({viewport:{width:390,height:844},serviceWorkers:'block'}),errors=[];
    await context.route('**/js/ai-models.js',route=>route.fulfill({contentType:'application/javascript',body:source+`
      {const base=window.COCKPIT_AI_CATALOG.models.find(model=>model.id==='crew3-intern-preview-v1/best.pt');
       window.__priorMixedCatalog=JSON.stringify(window.COCKPIT_AI_CATALOG.models);
       window.COCKPIT_AI_CATALOG.models.unshift({...base,id:'${fixtureId}',name:'Mixed cases fixture (Test)',
         recommended:true,supported_airports:['LOG_YUL_GREEN','LOG_HND_GREEN','LOG_GIG_YELLOW','LOG_ATL_GREEN'],quality:{approved:false},
         preview:{enabled:true,positive_only:true,evaluation_kind:'development',
           route_results:{LOG_YUL_GREEN:{games:20,win_rate:.99}},
           supported_cases:[{airport:'LOG_YUL_GREEN',abilities:[]},{airport:'LOG_HND_GREEN',abilities:[]},
             {airport:'LOG_GIG_YELLOW',abilities:['control']},{airport:'LOG_GIG_YELLOW',abilities:['adaptation']}],
           case_results:{'LOG_YUL_GREEN|':{games:20,wins:1,win_rate:.05},'LOG_HND_GREEN|':{games:20,wins:0,win_rate:0},
             'LOG_GIG_YELLOW|control':{games:20,wins:2,win_rate:.1},'LOG_GIG_YELLOW|adaptation':{games:20,wins:0,win_rate:0}}}});}
    `}));
    await context.route('**/js/cloud-config.js',route=>route.fulfill({contentType:'application/javascript',body:'window.COCKPIT_LEARNING_CLOUD={};'}));
    const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
    await page.goto(pageUrl);await page.getByRole('button',{name:/Singleplayer/}).click();
    assert.equal(await page.locator('#solo-model').inputValue(),'crew-basegame-v1/best.pt','An approved crew stays selected despite recommended test metadata');
    assert.equal(await page.evaluate(()=>JSON.stringify(COCKPIT_AI_CATALOG.models.filter(model=>model.id!=='fixture-mixed-preview/best.pt'))===window.__priorMixedCatalog),true);
    const currentId=process.env.COCKPIT_CURRENT_PREVIEW_ID || 'crew3-current-preview-v2/best.pt';
    const current=await page.evaluate(id=>COCKPIT_AI_CATALOG.models.find(model=>model.id===id),currentId);
    if(process.env.COCKPIT_MIXED_FIXTURE_ONLY!=='1') assert.ok(current,'The actual published current Crew 3 preview must exist');
    if(current) {
      assert.equal(current.quality.approved,false);assert.equal(current.preview.enabled,true);
      assert.equal(current.preview.positive_only,true);assert.equal(current.assistance_version,10);
      assert.equal(current.url,await page.evaluate(()=>COCKPIT_AI_CATALOG.models.find(model=>model.id==='crew3-intern-preview-v1/best.pt').url),
        'The actual current release must reuse the unchanged original Crew-3 model asset');
      assert.ok(Object.values(current.preview.case_results).every(result=>result.games>0 && result.wins>0 && result.win_rate>0));
      const actualRoutes=await page.evaluate(()=>LANDING_CATALOG.scenarios);
      const score=row=>{
        const route=actualRoutes.find(route=>route.engine_code===row.airport);
        return (row.abilities.length===2 && route.modules.includes('realtime')?100:0)
          + (row.abilities.length===2?20:0) + row.abilities.filter(card=>['control','mastery'].includes(card)).length;
      };
      const noCards=current.preview.supported_cases.find(row=>row.airport==='LOG_YUL_GREEN' && !row.abilities.length)
        || current.preview.supported_cases.find(row=>!row.abilities.length);
      const withCards=current.preview.supported_cases.filter(row=>row.abilities.length).sort((a,b)=>score(b)-score(a))[0];
      assert.ok(noCards && withCards,'The published release needs both tested runtime paths');
      const realCases=[];
      await page.locator('[data-mode="feedback"]').click();
      for(const selected of [noCards,withCards]) {
        const actualRoute=actualRoutes.find(route=>route.engine_code===selected.airport);
        await chooseModel(page,currentId);
        await chooseRoute(page,actualRoute.id);
        if(selected.abilities.length) {
          const expected=current.preview.supported_cases.filter(row=>row.airport===selected.airport)
            .map(row=>row.airport+'|'+[...row.abilities].sort().join(',')).sort();
          assert.deepEqual(await page.locator('#solo-abilities option').evaluateAll(options=>options.map(option=>option.value).sort()),expected);
          await chooseAbilities(page,selected.airport+'|'+[...selected.abilities].sort().join(','));
        }
        assert.match(await page.locator('#solo-description').innerText(),/Entwicklungstest im KI-Selbstspiel/);
        await page.locator('#solo-consent').check();
        assert.equal(await page.locator('#solo-start').isDisabled(),false);
        await page.locator('#solo-start').click();
        await page.locator('#spiel-ui').waitFor({state:'visible',timeout:90000});
        const actualCards=await page.evaluate(()=>{
          pyodide.runPython('import backend.bridge as b\nwhile b._spiel.phase == "verkehr": b._spiel.wirf_verkehrswuerfel()\nfor die in b._spiel.pilot_wuerfel + b._spiel.kopilot_wuerfel: die.augenzahl=3');
          resetVerkehrUi();render(pyToJs(bridge.zustand()));
          const answer=spielAktion({kind:'place',role:'pilot',die:0,target:'ruder'});
          if(!answer.ergebnis.erfolg) throw new Error(JSON.stringify(answer.ergebnis));
          nachAktion(answer);return [...aktuellerZustand.faehigkeitskarten];
        });
        assert.deepEqual([...actualCards].sort(),[...selected.abilities].sort());
        const key=selected.airport+'|'+[...selected.abilities].sort().join(',');
        let recording;
        for(let attempt=0;attempt<60;attempt++) {
          await page.waitForTimeout(100);
          if(await page.locator('#ai-resume').count()) throw new Error(await page.locator('.ai-paused').innerText());
          recording=(await rows(page)).find(session=>session.model.id===currentId && session.scenario.case_key===key);
          if(recording?.events.some(event=>event.actor==='ai')) break;
        }
        assert.equal(recording?.scenario.engine_code,selected.airport);
        assert.equal(recording.scenario.case_key,key);
        assert.deepEqual(recording.scenario.ability_ids,[...selected.abilities].sort());
        assert.ok(recording.events.some(event=>event.actor==='ai' && event.training_compatible
          && event.decision.observation.length===489 && event.decision.action_mask.length===217
          && event.decision.reference_action_mask.length===217));
        // Exercise the registered feedback handlers even when a card/roll
        // dialog currently owns focus. Physical thumb access is separately
        // covered by the mobile/keyboard regression.
        await page.evaluate(()=>{
          const up=document.getElementById('ai-rating-up');
          if(!up || up.disabled) throw new Error('The actual model action has no pending feedback');
          up.click();
        });
        let rated=false;
        for(let attempt=0;attempt<40;attempt++) {
          recording=(await rows(page)).find(session=>session.model.id===currentId && session.scenario.case_key===key);
          rated=recording?.events.some(event=>event.actor==='ai' && event.feedback?.value===1 && event.feedback.committed);
          if(rated) break;
          await page.waitForTimeout(100);
        }
        assert.equal(rated,true,'Feedback must persist on a real release model action');
        realCases.push({case:key,modules:actualRoute.modules,ai:recording.events.filter(event=>event.actor==='ai').map(event=>event.action.kind)});
        await page.evaluate(()=>Singleplayer.showMenu());
        await page.locator('[data-mode="feedback"]').click();
      }
      console.log('Actual current Crew 3 runtime cases:',JSON.stringify(realCases));
      await chooseMode(page,'play');
    }
    await chooseMode(page,'play');
    await chooseModel(page,fixtureId);
    await chooseRoute(page,'YUL-green');
    for(const route of ['HND-green','ATL-green']) {
      assert.equal(await page.locator(`#solo-route option[value="${route}"]`).count(),0,
        'Zero-result and unlisted no-card cases stay hidden despite route hints');
    }
    await chooseMode(page,'feedback');
    for(const [route,cards,rate] of [['YUL-green',[],5],['GIG-yellow',['control'],10]]) {
      await chooseModel(page,fixtureId);
      await chooseRoute(page,route);
      assert.match(await page.locator('#solo-description').innerText(),new RegExp(`Entwicklungstest im KI-Selbstspiel: ${rate} %`));
      assert.doesNotMatch(await page.locator('#solo-description').innerText(),/99 %/);
      assert.match(await page.locator('#solo-description').innerText(),/noch nicht unabhängig qualifiziert/);
      if(!cards.length) assert.equal(await page.locator('#solo-abilities-label').isVisible(),false);
      else {
        assert.equal(await page.locator('#solo-abilities option').count(),1);
        assert.equal(await page.locator('#solo-abilities').inputValue(),'LOG_GIG_YELLOW|control');
      }
      await page.locator('#solo-consent').check();
      if(cards.length) {
        await page.evaluate(()=>{const select=document.getElementById('solo-abilities'),bad=new Option('zero-case','LOG_GIG_YELLOW|adaptation');select.add(bad);select.value=bad.value;});
        await page.locator('#solo-start').click();
        assert.equal(await page.locator('#spiel-ui').isVisible(),false,'DOM injection cannot launch a zero-win card case');
        await chooseAbilities(page,'LOG_GIG_YELLOW|control');
      }
      assert.equal(await page.locator('#solo-start').isDisabled(),false);
      await page.locator('#solo-start').click();
      await page.locator('#spiel-ui').waitFor({state:'visible',timeout:90000});
      await page.evaluate(()=>{
        pyodide.runPython('import backend.bridge as b\nwhile b._spiel.phase == "verkehr": b._spiel.wirf_verkehrswuerfel()\nfor die in b._spiel.pilot_wuerfel + b._spiel.kopilot_wuerfel: die.augenzahl=3');
        resetVerkehrUi();render(pyToJs(bridge.zustand()));
        const answer=spielAktion({kind:'place',role:'pilot',die:0,target:'ruder'});
        if(!answer.ergebnis.erfolg) throw new Error(JSON.stringify(answer.ergebnis));
        nachAktion(answer);
      });
      let recording;
      const key=(route==='YUL-green'?'LOG_YUL_GREEN':'LOG_GIG_YELLOW')+'|'+cards.join(',');
      for(let attempt=0;attempt<50;attempt++) {
        await page.waitForTimeout(100);
        if(await page.locator('#ai-resume').count()) throw new Error(await page.locator('.ai-paused').innerText());
        recording=(await rows(page)).find(session=>session.model.id===fixtureId && session.scenario.case_key===key);
        if(recording?.events.some(event=>event.actor==='ai')) break;
      }
      assert.deepEqual(recording?.scenario.ability_ids,cards);
      assert.equal(recording.scenario.case_key,key);
      assert.ok(recording.events.some(event=>event.actor==='ai' && event.training_compatible
        && event.decision.observation.length===489 && event.decision.action_mask.length===217));
      assert.ok(recording.events.every(event=>!event.decision?.public_state || !('own_dice' in event.decision.public_state)));
      await page.evaluate(()=>Singleplayer.showMenu());
      await page.locator('[data-mode="feedback"]').click();
    }
    assert.deepEqual(errors,[]);
    console.log('✓ Mixed exact positive cases: standard base-game and wind-card launches, case-specific quotes/records, zero/unlisted cases hidden, strict launch revalidation, original Crew3 tensors and approved defaults preserved; actual current release '+(current?'checked':'not present (fixture-only opt-in)'));
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
