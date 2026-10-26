/* Run with Playwright available via NODE_PATH and a local server on port 8000.
 * Real Pyodide is used. PeerJS is replaced by a controllable transport fixture. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {leaveGame}=require('./singleplayer-setup.cjs');
const os = require('node:os');
const path = require('node:path');
const base = process.env.COCKPIT_TEST_URL || 'http://127.0.0.1:8000';
const shotDir = process.env.COCKPIT_SCREENSHOTS || path.join(os.tmpdir(), 'flyteam-ui');
fs.mkdirSync(shotDir, {recursive: true});
const peerFixture = `
window.fixtureConn = () => ({open:true, handlers:{}, sent:[], on(event,fn){this.handlers[event]=fn;}, send(value){this.sent.push(JSON.parse(value));}});
window.Peer = class { constructor(){this.handlers={}; window.fixturePeer=this;} on(event,fn){this.handlers[event]=fn; if(event==='open') setTimeout(fn,0);} connect(){window.fixtureClient=window.fixtureConn(); setTimeout(()=>window.fixtureClient.handlers.open(),0);return window.fixtureClient;} destroy(){} };
`;
(async () => {
  const browser = await chromium.launch({headless:true, ...(process.env.COCKPIT_CHROME ? {executablePath:process.env.COCKPIT_CHROME} : {})});
  try {
    const context = await browser.newContext({viewport:{width:1360,height:1000}, serviceWorkers:'block'});
    const page = await context.newPage(); const errors=[];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(`${base}/frontend/web/`);
    assert.equal(await page.locator('select').count(), 0);
    await page.getByRole('button',{name:/Pass & Play/}).click();
    assert.equal(await page.locator('.landing-card').count(),21);
    assert.equal(await page.locator('[data-filter="custom"]').count(),0);
    assert.equal(await page.locator('[data-scenario^="custom-"]').count(),0);
    await page.locator('[data-filter="green"]').click(); assert.equal(await page.locator('.landing-card').count(),6);
    await page.locator('[data-filter="yellow"]').click(); assert.equal(await page.locator('.landing-card').count(),7);
    await page.locator('[data-filter="red"]').click(); assert.equal(await page.locator('.landing-card').count(),5);
    await page.locator('[data-filter="black"]').click(); assert.equal(await page.locator('.landing-card').count(),3);
    await page.locator('[data-filter="all"]').click();
    await page.getByRole('searchbox').fill('montreal'); assert.equal(await page.locator('.landing-card').count(),1);
    await page.getByRole('searchbox').fill('unbekannt'); assert.equal(await page.locator('.landing-empty').count(),1);
    await page.getByRole('searchbox').fill('');
    await page.waitForFunction(() => [...document.querySelectorAll('.landing-card img')].slice(0,3).every(i=>i.complete && i.naturalWidth));
    await page.screenshot({path:path.join(shotDir,'desktop.png')});
    console.log('✓ All 21 variants, difficulty filters, accented search, empty results and local images');
    await page.locator('[data-scenario="PRG-green"]').click();
    assert.equal(await page.locator('.landing-ability').count(),6);
    await page.locator('[data-ability="control"]').click(); await page.locator('[data-ability="adaptation"]').click();
    assert.equal(await page.locator('.landing-ability[aria-pressed="true"]').count(),2);
    assert.equal(await page.locator('.landing-ability:disabled').count(),4);
    await page.reload(); await page.getByRole('button',{name:/Pass & Play/}).click(); await page.locator('[data-scenario="PRG-green"]').click();
    assert.equal(await page.locator('.landing-ability[aria-pressed="true"]').count(),2);
    console.log('✓ Loadout limit and persistence, active gameplay effects');
    await page.locator('[data-action="start"]').click();
    await page.locator('#spiel-ui').waitFor({state:'visible',timeout:90000});
    let state = await page.evaluate(() => pyToJs(bridge.zustand()));
    assert.equal(state.szenario_id,'PRG-green'); assert.equal(state.mock,false); assert.equal(state.uebung,false);
    assert.deepEqual(state.geplante_module,['kerosene']);
    assert.match(await page.locator('#flight-summary').getAttribute('aria-label'),/Kerosin/);
    assert.equal(await page.evaluate(() => pyToJs(bridge.zustand()).verkehrswuerfel_offen),1);
    await page.locator('.traffic-roll-button').click();
    await page.waitForFunction(() => pyToJs(bridge.zustand()).phase === 'platzieren');
    await page.locator('#verkehr-dialog').waitFor({state:'hidden'});
    await page.evaluate(() => {
      const spiel = bridge._spiel; spiel.neuwurf_plaettchen = 2; spiel.destroy();
      // This seed rolls 6 and 1: both selected dice keep their old values.
      pyodide.runPython('import random\nimport backend.bridge as b\nrandom.seed(42)\nb._spiel.pilot_wuerfel[1].augenzahl = 6\nb._spiel.kopilot_wuerfel[1].augenzahl = 1');
      const z = pyToJs(bridge.zustand());
      nachAktion(pyToJs(bridge.platziere(z.am_zug,0,'ruder')));
    });
    const beforeReroll = await page.evaluate(() => pyToJs(bridge.zustand()));
    await page.locator('#s-neuwurf button').click();
    assert.equal(await page.locator('#neuwurf-dialog[open] .wuerfel').count(),8);
    assert.equal(await page.locator('#neuwurf-dialog .wuerfel.platziert:disabled').count(),1);
    assert.equal(await page.locator('#rundenende-btn').isDisabled(),true);
    await page.locator('#neuwurf-dialog .pilot [data-index="1"]').click();
    await page.locator('#neuwurf-dialog .kopilot [data-index="1"]').click();
    assert.equal(await page.locator('#neuwurf-dialog [aria-pressed="true"]').count(),2);
    await page.screenshot({path:path.join(shotDir,'reroll-desktop-selection.png')});
    await page.setViewportSize({width:320,height:700});
    assert.ok(await page.locator('#neuwurf-dialog').evaluate(el => el.scrollWidth <= el.clientWidth));
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:path.join(shotDir,'reroll-mobile-selection.png')});
    await page.locator('#neuwurf-dialog .pilot .neuwurf-bestaetigen').click();
    assert.equal(await page.evaluate(() => pyToJs(bridge.zustand()).neuwurf_plaettchen),2);
    assert.equal(await page.locator('#neuwurf-dialog .pilot [data-index="1"]').isDisabled(),true);
    await page.locator('#neuwurf-dialog .kopilot .neuwurf-bestaetigen').click();
    assert.equal(await page.locator('#neuwurf-dialog .neu-gewuerfelt').count(),2);
    const afterReroll = await page.evaluate(() => pyToJs(bridge.zustand()));
    assert.equal(afterReroll.pilot_wuerfel[1],beforeReroll.pilot_wuerfel[1],'Same-value reroll fixture');
    assert.equal(afterReroll.kopilot_wuerfel[1],beforeReroll.kopilot_wuerfel[1],'Same-value reroll fixture');
    assert.equal(afterReroll.neuwurf_plaettchen,1);
    assert.equal(afterReroll.am_zug,beforeReroll.am_zug);
    for (const role of ['pilot','kopilot']) for (const index of [0,2,3]) {
      assert.equal(afterReroll[`${role}_wuerfel`][index],beforeReroll[`${role}_wuerfel`][index]);
    }
    await page.screenshot({path:path.join(shotDir,'reroll-mobile-result.png')});
    await page.locator('#neuwurf-dialog').waitFor({state:'hidden'});
    assert.equal(await page.locator('body.neuwurf-dialog-offen').count(),0);
    await page.locator('#s-neuwurf button').click();
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('#neuwurf-dialog').isVisible(),false);
    assert.equal(await page.evaluate(() => pyToJs(bridge.zustand()).neuwurf_plaettchen),1);
    await page.setViewportSize({width:1360,height:1000});
    console.log('✓ Real-engine shared reroll popup, both dice pools, placed dice locked, two confirmations, one token, highlighted results, automatic close, Escape and 320px layout');
    await page.locator('#menue-btn').click();
    await page.getByRole('button',{name:'Hauptmenü',exact:true}).click();
    await page.getByRole('button',{name:'Zum Hauptmenü',exact:true}).click();
    await page.getByRole('button',{name:/Pass & Play/}).click();
    await page.locator('[data-action="gallery"]').click();
    assert.equal(await page.locator('.landing-card').count(),21);
    assert.equal(await page.locator('[data-filter="custom"]').count(),0);
    assert.equal(await page.locator('[data-scenario^="custom-"]').count(),0);
    await page.locator('[data-scenario="LHR-green"]').click(); await page.locator('[data-action="start"]').click();
    await page.locator('#spiel-ui').waitFor({state:'visible'});
    state = await page.evaluate(() => pyToJs(bridge.zustand()));
    assert.equal(state.szenario_id,'LHR-green'); assert.equal(state.mock,false); assert.equal(state.laenge,6);
    if(await page.locator('#verkehr-dialog[open]').count()) await page.locator('.traffic-peek-button').click();
    await leaveGame(page); await page.getByRole('button',{name:/Pass & Play/}).click();
    await page.locator('[data-action="gallery"]').click(); await page.locator('[data-filter="all"]').click();
    await page.locator('[data-scenario="PRG-green"]').click();
    await page.evaluate(() => Landings.updateFlight({...pyToJs(bridge.zustand()),szenario_id:'PRG-green',mock:false,uebung:false,status:'gewonnen'}));
    await page.locator('[data-action="gallery"]').click();
    assert.match(await page.locator('[data-scenario="PRG-green"]').innerText(),/Gelandet/);
    assert.equal(await page.locator('[data-scenario="LHR-green"] .landing-completed').count(),0);
    console.log('✓ Real Pyodide start, traffic action, official route switching/progress; custom routes and filter absent');
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:path.join(shotDir,'mobile.png')});
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
    await page.locator('[data-scenario="GIG-yellow"]').click();
    assert.equal(await page.locator('.landing-ability').count(),6);
    await page.locator('[data-ability="control"]').click(); assert.equal(await page.locator('.landing-ability:disabled').count(),5);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
    await page.screenshot({path:path.join(shotDir,'mobile-detail.png'),fullPage:true});
    await page.setViewportSize({width:320,height:700});
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
    console.log('✓ Mobile gallery/details at 390px and narrow 320px, one-card limit');

    await context.route('**/peerjs@*/**', route => route.fulfill({contentType:'application/javascript', body:peerFixture}));
    const host = await context.newPage(); host.on('pageerror', e=>errors.push(e.message));
    await host.goto(`${base}/frontend/web/multiplayer.html`);
    await host.locator('#btn-host').click(); assert.equal(await host.locator('.landing-card').count(),21);
    assert.equal(await host.locator('[data-filter="custom"]').count(),0);
    assert.equal(await host.locator('[data-scenario^="custom-"]').count(),0);
    assert.equal(await host.locator('select').count(),0);
    await host.locator('[data-scenario="HND-red"]').click(); await host.locator('[data-ability="control"]').click(); await host.locator('[data-action="start"]').click();
    await host.waitForFunction(()=>pyodideReady,{},{timeout:90000});
    assert.match(await host.locator('#host-landing').innerText(),/HND/);
    await host.evaluate(()=>{ window.fixtureHost=window.fixtureConn(); window.fixturePeer.handlers.connection(window.fixtureHost); window.fixtureHost.handlers.open(); });
    await host.locator('#spiel-ui').waitFor({state:'visible'});
    for (let remaining=await host.evaluate(()=>pyToJs(bridge.zustand()).verkehrswuerfel_offen); remaining>0; remaining--) {
      await host.locator('.traffic-roll-button').click();
      await host.waitForFunction(count=>pyToJs(bridge.zustand()).verkehrswuerfel_offen<count,remaining);
    }
    await host.locator('#verkehr-dialog').waitFor({state:'hidden'});
    assert.ok(await host.evaluate(()=>pyToJs(bridge.zustand()).pilot_wuerfel.every(v=>Number.isInteger(v))));
    const multiplayerStart=await host.evaluate(()=>({dice:[pyToJs(bridge.zustand()).pilot_wuerfel,pyToJs(bridge.zustand()).kopilot_wuerfel],rng:JSON.parse(String(bridge.spiel_speichern())).root.items[2]}));
    let msg=await host.evaluate(()=>window.fixtureHost.sent.filter(m=>m.typ==='zustand').at(-1));
    assert.equal(msg.zustand.szenario_id,'HND-red'); assert.ok(msg.zustand.pilot_wuerfel.every(v=>v===null));
    const join = await context.newPage(); join.on('pageerror', e=>errors.push(e.message));
    await join.goto(`${base}/frontend/web/multiplayer.html?join=ABCDEF`);
    await join.waitForFunction(()=>Boolean(window.fixtureClient?.handlers.data));
    await join.evaluate(m=>window.fixtureClient.handlers.data(JSON.stringify(m)), msg);
    await join.locator('#spiel-ui').waitFor({state:'visible'});
    assert.match(await join.locator('#flight-summary').innerText(),/HND/);
    assert.equal(await join.locator('#neues-spiel-btn').isVisible(),false);
    const syncJoin = async () => {
      const snapshot = await host.evaluate(()=>window.fixtureHost.sent.filter(m=>m.typ==='zustand').at(-1));
      await join.evaluate(m=>window.fixtureClient.handlers.data(JSON.stringify(m)),snapshot);
      return snapshot;
    };
    const deliverJoinAction = async () => {
      const action = await join.evaluate(()=>window.fixtureClient.sent.at(-1));
      await host.evaluate(m=>window.fixtureHost.handlers.data(JSON.stringify(m)),action);
      return syncJoin();
    };
    await host.evaluate(() => {
      const spiel = bridge._spiel; spiel.neuwurf_plaettchen = 2; spiel.destroy();
      sendState();
    });
    const rerollStart = await syncJoin();
    if (rerollStart.zustand.am_zug === 'pilot') {
      await host.locator('#s-neuwurf button').click(); await syncJoin();
    } else {
      await join.locator('#s-neuwurf button').click(); await deliverJoinAction();
    }
    for (const device of [host,join]) {
      assert.equal(await device.locator('#neuwurf-dialog[open] .wuerfel').count(),8);
      assert.equal(await device.locator('#neuwurf-dialog .wuerfel').evaluateAll(els=>els.some(el=>el.textContent==='?')),false);
    }
    assert.equal(await host.locator('#neuwurf-dialog .kopilot [data-index="1"]').isDisabled(),true);
    assert.equal(await join.locator('#neuwurf-dialog .pilot [data-index="1"]').isDisabled(),true);
    await join.locator('#neuwurf-dialog .kopilot [data-index="1"]').click(); await deliverJoinAction();
    await host.locator('#neuwurf-dialog .pilot [data-index="1"]').click(); await syncJoin();
    await host.locator('#neuwurf-dialog .pilot .neuwurf-bestaetigen').click(); await syncJoin();
    assert.equal(await host.evaluate(()=>pyToJs(bridge.zustand()).neuwurf_plaettchen),2);
    await join.locator('#neuwurf-dialog .kopilot .neuwurf-bestaetigen').click();
    const rerollResult = await deliverJoinAction();
    assert.equal(rerollResult.zustand.neuwurf_plaettchen,1);
    assert.equal(rerollResult.zustand.am_zug,rerollStart.zustand.am_zug);
    for (const device of [host,join]) assert.equal(await device.locator('#neuwurf-dialog .neu-gewuerfelt').count(),2);
    assert.ok(rerollResult.zustand.pilot_wuerfel.every(v=>v===null),'Partner tray exposes values during reroll');
    await host.screenshot({path:path.join(shotDir,'reroll-multiplayer-result.png')});
    await host.locator('#neuwurf-dialog').waitFor({state:'hidden'});
    const rerollClosed = await syncJoin();
    assert.equal(await join.locator('#neuwurf-dialog').isVisible(),false);
    assert.equal(rerollClosed.neuwurf.wuerfel,null);
    console.log('✓ Both multiplayer popups, independent own-dice selection, synchronized confirmations/results, one token, automatic close and hidden partner trays (real engine, transport fixture)');
    await host.locator('#menue-btn').click();
    await host.getByRole('button',{name:'Neustart',exact:true}).click();
    await host.getByRole('button',{name:'Abbrechen',exact:true}).click();
    await host.getByRole('button',{name:'Fortsetzen',exact:true}).click();
    await join.locator('#menue-btn').click();
    assert.equal(await join.getByRole('button',{name:'Neustart',exact:true}).isDisabled(),true);
    await join.getByRole('button',{name:'Fortsetzen',exact:true}).click();
    await host.locator('#menue-btn').click();
    await host.getByRole('button',{name:'Neustart',exact:true}).click();
    assert.equal(await host.locator('#restart-same-seed').isChecked(),false);
    await host.locator('#restart-same-seed').check();
    await host.getByRole('button',{name:'Neu starten',exact:true}).click();
    for(let remaining=await host.evaluate(()=>pyToJs(bridge.zustand()).verkehrswuerfel_offen);remaining>0;remaining--){
      await host.locator('.traffic-roll-button').click();
      await host.waitForFunction(count=>pyToJs(bridge.zustand()).verkehrswuerfel_offen<count,remaining);
    }
    await host.locator('#verkehr-dialog').waitFor({state:'hidden'});
    assert.deepEqual(await host.evaluate(()=>({dice:[pyToJs(bridge.zustand()).pilot_wuerfel,pyToJs(bridge.zustand()).kopilot_wuerfel],rng:JSON.parse(String(bridge.spiel_speichern())).root.items[2]})),multiplayerStart);
    assert.ok(await host.evaluate(()=>window.fixtureHost.sent.every(m=>!JSON.stringify(m).includes('initialEngine'))),'Private host restart state must never enter transport');
    await host.locator('#menue-btn').click();await host.getByRole('button',{name:'Neustart',exact:true}).click();
    assert.equal(await host.locator('#restart-same-seed').isChecked(),false);
    await host.getByRole('button',{name:'Neu starten',exact:true}).click();
    msg=await syncJoin();
    assert.equal(msg.zustand.szenario_id,'HND-red');
    assert.equal(msg.zustand.runde,1);
    assert.equal(msg.zustand.neuwurf_plaettchen,0);

    if (await host.locator('#verkehr-dialog[open]').count()) await host.locator('.traffic-peek-button').click();
    await host.evaluate(()=>waehleLandung()); await host.locator('[data-action="gallery"]').click();
    await host.locator('[data-scenario="KEF-black"]').click(); await host.locator('[data-ability="control"]').click(); await host.locator('[data-ability="adaptation"]').click(); await host.locator('[data-action="start"]').click();
    msg=await host.evaluate(()=>window.fixtureHost.sent.filter(m=>m.typ==='zustand').at(-1));
    await join.evaluate(m=>window.fixtureClient.handlers.data(JSON.stringify(m)), msg);
    assert.equal(msg.zustand.szenario_id,'KEF-black'); assert.match(await join.locator('#flight-summary').innerText(),/KEF/);
    assert.equal(await join.locator('#screen-wait').isVisible(),false);
    console.log('✓ Host preflight, hidden partner dice, matching scenario on both devices, waiting/cancel/new landing (transport fixture)');
    const offline = await context.newPage();
    await offline.route('https://**/*', route=>route.abort());
    await offline.addInitScript(()=>{
      localStorage.setItem('flyteam-loadout-drafts-v1','invalid json');
      localStorage.setItem('flyteam-selection-v1',JSON.stringify({id:'custom-LHR'}));
    });
    await offline.goto(`${base}/frontend/web/?view=landings`);
    assert.equal(await offline.locator('.landing-card').count(),21);
    assert.equal(await offline.locator('[data-scenario^="custom-"]').count(),0);
    console.log('✓ Catalogue works with external CDNs unavailable and invalid saved drafts');
    assert.deepEqual(errors,[]);
    console.log(`All browser checks passed. Screenshots: ${shotDir}`);
  } finally { await browser.close(); }
})().catch(e=>{ console.error(e); process.exitCode=1; });
