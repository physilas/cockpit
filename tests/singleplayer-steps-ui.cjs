/* Real catalogue and browser: isolated steps, small screens and launch config. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const {chooseMode,chooseModel,chooseRoute} = require('./singleplayer-setup.cjs');
const base = process.env.COCKPIT_TEST_URL || 'http://127.0.0.1:8000';
const pageUrl = process.env.COCKPIT_TEST_PAGE_URL || `${base}/frontend/web/`;
const fits = async page => assert.ok(await page.evaluate(() => {
  const html=document.documentElement;
  return html.scrollHeight <= innerHeight + 1 && html.scrollWidth <= innerWidth;
}), 'Mode and AI steps must fit the viewport without scrolling or clipping');

(async () => {
  const browser=await chromium.launch({headless:true,executablePath:process.env.COCKPIT_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  try {
    const context=await browser.newContext({serviceWorkers:'block'}), errors=[];
    await context.route('**/js/cloud-config.js',route=>route.fulfill({contentType:'application/javascript',body:'window.COCKPIT_LEARNING_CLOUD={};'}));
    const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
    for (const viewport of [{width:1280,height:900},{width:390,height:844},{width:320,height:568},{width:568,height:320}]) {
      await page.setViewportSize(viewport);await page.goto(pageUrl);
      await page.getByRole('button',{name:/Singleplayer/}).click();
      assert.equal(await page.locator('#singleplayer-menu').getAttribute('data-step'),'mode');
      assert.equal(await page.locator('#solo-model').isVisible(),false);
      assert.equal(await page.locator('#solo-route').isVisible(),false);
      assert.equal(await page.locator('#solo-start').isVisible(),false);
      await fits(page);
      if(viewport.width===390) await page.screenshot({path:'/tmp/cockpit-solo-step1.png'});
      await chooseMode(page,'feedback');
      assert.equal(await page.locator('#singleplayer-menu').getAttribute('data-step'),'model');
      assert.equal(await page.locator('[data-mode="play"]').isVisible(),false);
      assert.equal(await page.locator('#solo-model').inputValue(),'crew-basegame-v1/best.pt');
      assert.equal(await page.locator('#solo-route').isVisible(),false);
      assert.equal(await page.locator('#solo-consent').isVisible(),false);
      assert.equal(await page.locator('#solo-heading').evaluate(el=>document.activeElement===el),true);
      await fits(page);
      const modelIds=await page.locator('#solo-model option').evaluateAll(options=>options.map(o=>o.value));
      assert.ok(modelIds.includes('crew5-leak-preview-v1/best.pt'),'Choose a module preview before its route');
      assert.equal(await page.evaluate(ids=>ids.every(id=>{
        const model=COCKPIT_AI_CATALOG.models.find(m=>m.id===id);
        return model.quality?.approved===true || model.preview?.enabled===true;
      }),modelIds),true);
      await chooseModel(page,'crew5-leak-preview-v1/best.pt','kopilot');await fits(page);
      if(viewport.width===390) await page.screenshot({path:'/tmp/cockpit-solo-step2.png'});
      await chooseRoute(page,'ATL-yellow');
      assert.equal(await page.locator('#solo-model').isVisible(),false);
      assert.deepEqual(await page.locator('#solo-route option').evaluateAll(options=>options.map(o=>o.value)),['ATL-yellow']);
      assert.equal(await page.locator('#solo-abilities option').count(),6);
      await page.locator('#solo-abilities').selectOption('LOG_ATL_YELLOW|working-together');
      assert.match(await page.locator('#solo-description').innerText(),/0 %/);
      assert.equal(await page.locator('#solo-start').isDisabled(),true);
      await page.locator('#solo-consent').check();
      assert.equal(await page.locator('#solo-start').isDisabled(),false);
      if(viewport.width===390) await page.screenshot({path:'/tmp/cockpit-solo-step3.png',fullPage:true});
      await page.locator('#solo-back').click();
      assert.equal(await page.locator('#solo-model').inputValue(),'crew5-leak-preview-v1/best.pt');
      assert.equal(await page.locator('#solo-role').inputValue(),'kopilot');
      await page.locator('#solo-next').click();
      assert.equal(await page.locator('#solo-abilities').inputValue(),'LOG_ATL_YELLOW|working-together');
      assert.equal(await page.locator('#solo-consent').isChecked(),true);
      await chooseMode(page,'play');
      assert.equal(await page.locator('#solo-consent').isChecked(),false,'Changing mode resets consent');
      await chooseModel(page,'crew-basegame-v1/best.pt');
      await chooseRoute(page,'custom-MUC');
      assert.equal(await page.locator('#solo-route option[value="ATL-yellow"]').count(),0);
      assert.equal(await page.locator('#solo-model').inputValue(),'crew-basegame-v1/best.pt','A landing never silently changes the chosen AI');
      await chooseMode(page,'examples');
      assert.equal(await page.locator('#singleplayer-menu').getAttribute('data-step'),'route');
      assert.match(await page.locator('#solo-step-count').innerText(),/2 VON 2/);
      assert.equal(await page.locator('#solo-role').isVisible(),false);
      assert.equal(await page.evaluate(()=>[...document.querySelectorAll('#solo-route option')].every(o=>{
        const route=LANDING_CATALOG.scenarios.find(s=>s.id===o.value);
        return !route.modules.length && !route.ability_count;
      })),true);
      await page.locator('#solo-back').click();
      assert.equal(await page.locator('#singleplayer-menu').getAttribute('data-step'),'mode');
    }
    // Fail a real model request once: preserve the last step and allow retry.
    await chooseMode(page,'play');await chooseModel(page,'crew5-leak-preview-v1/best.pt','pilot');
    await chooseRoute(page,'ATL-yellow');
    await page.locator('#solo-abilities').selectOption('LOG_ATL_YELLOW|adaptation');
    const url=await page.evaluate(()=>COCKPIT_AI_CATALOG.models.find(m=>m.id==='crew5-leak-preview-v1/best.pt').url);
    await page.route(`**/${url}`,route=>route.fulfill({status:503,body:'temporarily unavailable'}),{times:1});
    await page.locator('#solo-start').click();
    await page.waitForFunction(()=>document.getElementById('solo-error').textContent.includes('Modell konnte nicht geladen'));
    assert.equal(await page.locator('#singleplayer-menu').getAttribute('data-step'),'route');
    assert.equal(await page.locator('#solo-start').isDisabled(),false);
    await page.locator('#solo-start').click();
    await page.locator('#spiel-ui').waitFor({state:'visible',timeout:90000});
    assert.deepEqual(await page.evaluate(()=>[...aktuellerZustand.faehigkeitskarten]),['adaptation']);
    assert.equal(await page.evaluate(()=>Singleplayer.visibleRole()),'pilot');
    assert.match(await page.locator('#ai-session-bar').innerText(),/Crew 3/);
    assert.deepEqual(errors,[]);
    console.log('✓ Separate mode/AI/landing steps; desktop/mobile/landscape fit; back navigation; exact routes/cards; examples skip; failed-load retry; real Crew3 launch');
    await context.close();
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
