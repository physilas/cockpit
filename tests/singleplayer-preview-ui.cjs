/* Menu-only QA of the actual exported preview; no model updates or qualification. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const {chooseMode,chooseModel,chooseRoute} = require('./singleplayer-setup.cjs');
const fs=require('node:fs');
const pageUrl=process.env.COCKPIT_TEST_PAGE_URL || `${process.env.COCKPIT_TEST_URL || 'http://127.0.0.1:8000'}/frontend/web/`;
const source=fs.readFileSync(new URL('../frontend/web/js/ai-models.js',`file://${__filename}`),'utf8');
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.COCKPIT_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  try {
    const context=await browser.newContext({viewport:{width:390,height:844},serviceWorkers:'block'}), errors=[];
    await context.route('**/js/ai-models.js',route=>route.fulfill({contentType:'application/javascript',body:source+`
      {const candidate=window.COCKPIT_AI_CATALOG.models.find(m=>m.name==='Crew 3 · Praktikant (Test)' && m.preview?.enabled===true);
       if(!candidate) throw new Error('Actual Crew-3 preview missing');
       for(const [id,preview] of [['hidden-unqualified',undefined],['hidden-disabled',{enabled:false}],['hidden-truthy',{enabled:'true'}]])
         window.COCKPIT_AI_CATALOG.models.unshift({...candidate,id,quality:{approved:false},preview,
           supported_airports:['MUC','LOG_ATL_GREEN','LOG_LHR_YELLOW']});
       window.COCKPIT_AI_CATALOG.models.unshift({...candidate,id:'fixture-preview-muc',recommended:true,
         supported_airports:['MUC'],quality:{approved:false}});}
    `}));
    await context.route('**/js/cloud-config.js',route=>route.fulfill({contentType:'application/javascript',body:'window.COCKPIT_LEARNING_CLOUD={};'}));
    const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
    await page.goto(pageUrl);await page.getByRole('button',{name:/Singleplayer/}).click();
    assert.equal(await page.locator('#solo-model').inputValue(),'crew-basegame-v1/best.pt','Crew 1 remains the default');
    assert.equal(await page.locator('#solo-model option[value="fixture-preview-muc"]').count(),1);
    const actual=await page.evaluate(()=>COCKPIT_AI_CATALOG.models.find(m=>m.id==='crew3-intern-preview-v1/best.pt'));
    assert.equal(actual.quality?.approved,false);
    assert.equal(actual.preview.evaluation_kind,'development');
    assert.deepEqual([...actual.supported_airports].sort(),['LOG_ATL_GREEN','LOG_LHR_YELLOW']);
    for(const id of ['hidden-unqualified','hidden-disabled','hidden-truthy']) assert.equal(await page.locator(`#solo-model option[value="${id}"]`).count(),0);
    await chooseMode(page,'play');
    for(const route of ['ATL-green','LHR-yellow']) {
      await chooseModel(page,actual.id);
      await chooseRoute(page,route);
      assert.match(await page.locator('#solo-model').locator('option:checked').innerText(),/Crew 3 · Praktikant \(Test\).*Entwicklung/);
      const description=await page.locator('#solo-description').innerText();
      assert.match(description,/Testversion: Entwicklungsstand, noch nicht unabhängig qualifiziert/);
      assert.doesNotMatch(description,/Getestet im KI-Selbstspiel/);
      assert.equal(await page.locator('#solo-start').isDisabled(),false,'An explicitly selected weak preview remains playable');
      for(const id of ['hidden-unqualified','hidden-disabled','hidden-truthy']) assert.equal(await page.locator(`#solo-model option[value="${id}"]`).count(),0);
      await chooseMode(page,'feedback');
      await chooseModel(page,actual.id);
      await chooseRoute(page,route);
      assert.equal(await page.locator(`#solo-route option[value="${route}"]`).evaluate(option=>option.disabled),false);
      await page.locator('#solo-consent').check();
      assert.equal(await page.locator('#solo-start').isDisabled(),false);
      await chooseMode(page,'play');
    }
    await chooseMode(page,'examples');
    for(const route of ['ATL-green','LHR-yellow']) assert.equal(await page.locator(`#solo-route option[value="${route}"]`).count(),0);
    assert.ok(await page.evaluate(()=>[...document.querySelectorAll('#solo-model option')].every(option=>{
      const model=COCKPIT_AI_CATALOG.models.find(m=>m.id===option.value);
      return model.quality?.approved===true || model.preview?.enabled===true;
    })));
    assert.deepEqual(errors,[]);
    console.log('✓ Actual Crew-3 preview: both intern routes, honest development label, quality remains false, explicit opt-in only, weak preview playable/feedback enabled, hidden legacy models and Crew-1 default preserved');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
