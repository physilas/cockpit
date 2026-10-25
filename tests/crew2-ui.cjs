/* Released weights, real Pyodide engine and both human roles. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const base = process.env.COCKPIT_TEST_URL || 'http://127.0.0.1:8013';

async function sessions(page) {
  return page.evaluate(async () => {
    const db = await new Promise((resolve, reject) => {
      const request = indexedDB.open('flyteam-learning-v1', 2);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    return new Promise(resolve => {
      const request = db.transaction('sessions').objectStore('sessions').getAll();
      request.onsuccess = () => resolve(request.result);
    });
  });
}

(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.COCKPIT_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  try {
    const context = await browser.newContext({viewport: {width: 390, height: 844}, serviceWorkers: 'block'});
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base);
    await page.getByRole('button', {name: /Singleplayer/}).click();
    const crew = await page.evaluate(() => COCKPIT_AI_CATALOG.models.find(m => m.name === 'Crew 2'));
    assert.ok(crew?.quality.approved);
    assert.equal(crew.schema.version, 3);
    assert.ok(crew.quality.minimum_win_rate >= .5);
    assert.ok(crew.supported_airports.length > 0);
    for (const code of crew.supported_airports) {
      const result = crew.quality.route_results[code];
      assert.ok(result.games >= 500 && result.win_ci_low >= .5);
    }
    const routes = await page.evaluate(() => LANDING_CATALOG.scenarios);
    for (const route of routes.filter(s => !s.modules.length && !s.ability_count)) {
      await page.locator('#solo-route').selectOption(route.id);
      const choices = await page.locator('#solo-model option').evaluateAll(options => options.map(o => o.value));
      assert.equal(choices.includes(crew.id), crew.supported_airports.includes(route.engine_code));
      assert.ok(choices.includes('crew-basegame-v1/best.pt'));
    }
    const route = routes.find(s => s.engine_code === 'MUC' && crew.supported_airports.includes(s.engine_code))
      || routes.find(s => crew.supported_airports.includes(s.engine_code));
    for (const humanRole of ['pilot', 'kopilot']) {
      await page.locator('#solo-route').selectOption(route.id);
      await page.locator('#solo-model').selectOption(crew.id);
      await page.locator('#solo-role').selectOption(humanRole);
      assert.match(await page.locator('#solo-description').innerText(), /KI-Selbstspiel/);
      if (humanRole === 'pilot') await page.screenshot({path: '/tmp/cockpit-crew2-menu.png', fullPage: true});
      await page.locator('#solo-start').click();
      await page.locator('#spiel-ui').waitFor({state: 'visible', timeout: 90000});
      if (humanRole === 'pilot') {
        await page.evaluate(() => {
          const answer = spielAktion({kind: 'place', role: 'pilot', die: 0, target: 'ruder'});
          if (!answer.ergebnis.erfolg) throw new Error('Human control placement failed');
          nachAktion(answer);
        });
      }
      let data;
      for (let attempt = 0; attempt < 150; attempt++) {
        await page.waitForTimeout(100);
        assert.equal(await page.locator('#ai-resume').count(), 0);
        const confirm = page.locator(`#neuwurf-dialog .${humanRole} .neuwurf-bestaetigen`);
        if (await confirm.isVisible().catch(() => false)) {
          const die = page.locator(`#neuwurf-dialog .${humanRole} .wuerfel:not(:disabled)`).first();
          if (await die.count()) await die.click();
          await confirm.click();
        }
        data = (await sessions(page)).find(s => s.human_role === humanRole);
        const humanTurn = await page.evaluate(role => aktuellerZustand.status !== 'laeuft'
          || aktuellerZustand.am_zug === role, humanRole);
        if (data?.events.some(e => e.actor === 'ai') && humanTurn
            && !(await page.locator('#neuwurf-dialog').isVisible())) break;
      }
      const actions = data?.events.filter(e => e.actor === 'ai') || [];
      assert.ok(actions.length > 0, `Crew 2 must act when the human is ${humanRole}`);
      assert.equal(data.model.id, crew.id);
      assert.equal(data.schema_version, 3);
      assert.ok(actions.every(e => e.decision.observation.length === 489 && e.decision.action_mask.length === 217));
      assert.ok(actions.every(e => e.training_compatible && e.decision.reference_action_mask.some(Boolean)));
      assert.ok(actions.every(e => !('own_dice' in e.decision.public_state) && !('pilot_wuerfel' in e.decision.public_state)));
      if (humanRole === 'pilot') await page.screenshot({path: '/tmp/cockpit-crew2-game.png', fullPage: true});
      await page.locator('#menue-btn').click();
      await page.getByRole('button', {name: /Singleplayer/}).click();
    }
    assert.deepEqual(errors, []);
    console.log(`Crew 2: ${crew.supported_airports.length} qualified routes, Crew 1 preserved, both roles, real guided actions and private partner dice.`);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
