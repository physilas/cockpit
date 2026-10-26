/* Real engine + production catalogue: seed replay, rates, board motion and controls. */
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const {chooseMode,chooseModel,leaveGame}=require('./singleplayer-setup.cjs');
const url=(process.env.COCKPIT_TEST_URL||'http://127.0.0.1:8036')+'/frontend/web/';
const rateText=values=>{const f=n=>(n*100).toLocaleString('de-DE',{maximumFractionDigits:1});const lo=Math.min(...values),hi=Math.max(...values);return `${f(lo)}${lo===hi?'':`–${f(hi)}`} %`;};
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.COCKPIT_CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 try {
  const context=await browser.newContext({viewport:{width:390,height:844},serviceWorkers:'block'}),errors=[];
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url);await page.getByRole('button',{name:/Singleplayer/}).click();await chooseMode(page,'play');
  await page.locator('#solo-next').click();
  assert.equal(await page.locator('#solo-route').isVisible(),false);
  assert.equal(await page.locator('#solo-abilities').isVisible(),false);
  const expected=await page.evaluate(()=>{
   const model=COCKPIT_AI_CATALOG.models.find(m=>m.id===document.getElementById('solo-model').value);
   return LANDING_CATALOG.scenarios.map(s=>({id:s.id,rates:model.preview.supported_cases.filter(c=>c.airport===s.engine_code).map(c=>model.preview.case_results[`${c.airport}|${[...c.abilities].sort().join(',')}`].win_rate)}));
  });
  for(const row of expected)assert.equal(await page.locator(`[data-scenario="${row.id}"] .landing-win-rate b`).innerText(),rateText(row.rates));
  await page.locator('#solo-landings [data-scenario="PRG-green"]').click();
  assert.equal(await page.locator('.landing-ability-rate').count(),0,'No per-card values before choosing the first of two');
  await page.locator('[data-ability="control"]').click();
  assert.equal(await page.locator('.landing-ability-rate').count(),5);
  const exact=await page.evaluate(()=>{
   const model=COCKPIT_AI_CATALOG.models.find(m=>m.id===document.getElementById('solo-model').value);
   return LANDING_CATALOG.abilities.filter(a=>a.id!=='control').map(a=>({id:a.id,rate:model.preview.case_results[`LOG_PRG_GREEN|${['control',a.id].sort().join(',')}`].win_rate}));
  });
  for(const row of exact)assert.equal(await page.locator(`[data-ability="${row.id}"] .landing-ability-rate b`).innerText(),rateText([row.rate]));
  await page.screenshot({path:'/tmp/cockpit-rates-last-card.png',fullPage:true});
  await page.locator('[data-action="gallery"]').click();await page.locator('#solo-landings [data-scenario="ATL-yellow"]').click();
  assert.equal(await page.locator('.landing-ability-rate').count(),6,'Single-card route shows each exact case before selection');
  await page.locator('[data-action="gallery"]').click();await page.locator('#solo-landings [data-scenario="YUL-green"]').click();
  assert.equal(await page.locator('.landing-ability').count(),0);assert.equal(await page.locator('#solo-landings .landing-loadout').isVisible(),false);assert.ok(await page.locator('.landing-launch .landing-win-rate b').isVisible());
  console.log('✓ All 21 measured route rates/ranges; exact final-card rates; no visible dropdown or unnecessary card step');
  await page.evaluate(()=>Singleplayer.hideMenu());
  await page.evaluate(()=>startPassAndPlay());await page.locator('#landing-selection [data-scenario="YUL-green"]').click();
  await page.locator('#landing-selection [data-action="start"]').click();
  await page.waitForFunction(()=>pyodide&&aktuellerZustand?.phase==='platzieren',null,{timeout:90000});
  const digest=()=>page.evaluate(()=>({dice:[aktuellerZustand.pilot_wuerfel,aktuellerZustand.kopilot_wuerfel],planes:aktuellerZustand.flugzeuge,rng:pyodide.runPython('import random\nstr(random.getstate())')}));
  const original=await digest();
  const restart=async same=>{
   await page.locator('#menue-btn').click();await page.getByRole('button',{name:'Neustart',exact:true}).click();
   assert.equal(await page.locator('#restart-same-seed').isChecked(),false);
   if(same)await page.locator('#restart-same-seed').check();
   await page.getByRole('button',{name:'Neu starten',exact:true}).click();
   await page.waitForFunction(()=>aktuellerZustand?.phase==='platzieren'&&!GameDialogs.open());
  };
  await page.evaluate(()=>pyodide.runPython('random.random()'));
  await restart(true);assert.deepEqual(await digest(),original,'All initial dice and the subsequent RNG replay exactly');
  await restart(false);assert.notEqual((await digest()).rng,original.rng,'Default restart creates a fresh random sequence');
  console.log('✓ Unchecked restart defaults to fresh randomness; checked restores the exact initial dice, traffic and future RNG');
  // The private restart snapshot must survive a local leave/reload/resume.
  const resumable=await digest();await leaveGame(page);await page.reload();await page.locator('#resume-last-game').click();
  await page.locator('#spiel-ui').waitFor({state:'visible',timeout:90000});
  await restart(true);assert.deepEqual(await digest(),resumable);
  await page.evaluate(()=>{pyodide.runPython('import backend.bridge as b\nb._spiel.neuwurf_plaettchen=2');render(pyToJs(bridge.zustand()));});
  await page.locator('#s-neuwurf button').click();await page.getByRole('button',{name:'Spielfeld ansehen',exact:true}).click();
  for(const viewport of [{width:390,height:844},{width:320,height:740}]){
   await page.setViewportSize(viewport);await page.evaluate(()=>scrollTo(0,document.body.scrollHeight));
   const box=await page.locator('#neuwurf-zurueck').boundingBox();assert.ok(box&&box.y>=0&&box.y+box.height<viewport.height&&box.x>=0);
  }
  await page.locator('#neuwurf-zurueck').click();assert.ok(await page.locator('#neuwurf-dialog').isVisible());
  await page.getByRole('button',{name:'Abbrechen',exact:true}).click();await page.setViewportSize({width:390,height:844});
  const placed=await page.evaluate(()=>{
   const z=pyToJs(bridge.zustand()),role=z.am_zug;
   nachAktion(spielAktion({kind:'place',role,die:0,target:'ruder'}));
   return {motion:Boolean(document.querySelector('.motion-die')),role,value:aktuellerZustand.felder.ruder[role].wert};
  });
  assert.ok(placed.motion);await page.waitForTimeout(180);await page.screenshot({path:'/tmp/cockpit-die-motion.png'});
  await page.waitForTimeout(400);assert.equal(await page.locator('.motion-die').count(),0);
  await page.evaluate(()=>{
   pyodide.runPython('b._spiel.kopilot_wuerfel[0].augenzahl=1\nb._spiel.pilot_wuerfel[1].augenzahl=1\nb._spiel.am_zug="kopilot"');
   // A real current-field aircraft is removed by a legal radio placement.
   pyodide.runPython('b._spiel.landung.flugzeuge[0]=1');
   render(pyToJs(bridge.zustand()));
  });
  const plane=await page.evaluate(()=>{
   const answer=spielAktion({kind:'place',role:'kopilot',die:0,target:'funk',index:0,radio_index:0});nachAktion(answer);
   return {ok:answer.ergebnis.erfolg,reason:answer.ergebnis.grund,motion:Boolean(document.querySelector('.motion-plane'))};
  });
  assert.ok(plane.ok,JSON.stringify(plane));assert.ok(plane.motion);
  await page.waitForTimeout(200);await page.screenshot({path:'/tmp/cockpit-plane-motion.png'});await page.waitForTimeout(550);
  await page.locator('#game-log-button').click();const logs=await page.locator('#game-log').innerText();
  assert.match(logs,/Ruder/);assert.match(logs,/Funk/);assert.match(logs,/Flugzeug.*entfernt/);
  await page.screenshot({path:'/tmp/cockpit-flight-log.png'});await page.getByRole('button',{name:'Flugprotokoll schließen'}).click();
  assert.equal(await page.locator('#round-ready').isVisible(),false);
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.evaluate(()=>{nachAktion(spielAktion({kind:'place',role:'pilot',die:1,target:'triebwerk'}));});
  assert.equal(await page.locator('.motion-die').count(),0);
  // Isolate presentation of the fully placed state without inventing a successful game.
  await page.evaluate(()=>{
   const z=structuredClone(aktuellerZustand);z.pilot_wuerfel_frei.fill(false);z.kopilot_wuerfel_frei.fill(false);render(z);
  });
  assert.ok(await page.locator('#round-ready').isVisible());assert.ok(await page.locator('#rundenende-btn').isEnabled());
  const box=await page.locator('#round-ready').boundingBox();assert.ok(box.x>100&&box.y>600&&box.y+box.height<=844);
  await page.screenshot({path:'/tmp/cockpit-round-ready.png'});
  await page.evaluate(()=>render(pyToJs(bridge.zustand())));assert.equal(await page.locator('#round-ready').isVisible(),false);
  await page.evaluate(()=>{
   GameDialogs.reset();GameDialogs.connect({onPause(){},onResume(){},onRestart:()=>new Promise((resolve,reject)=>{window.finishRestart=resolve;window.failRestart=reject;})});GameDialogs.menu();
  });
  await page.getByRole('button',{name:'Neustart',exact:true}).click();await page.getByRole('button',{name:'Neu starten',exact:true}).click();
  assert.ok(await page.locator('#game-dialog').isVisible());assert.ok(await page.getByRole('button',{name:'Abbrechen',exact:true}).isDisabled());
  await page.keyboard.press('Escape');assert.match(await page.locator('#game-dialog-title').innerText(),/neu starten/);
  await page.evaluate(()=>window.failRestart(new Error('Vorübergehend offline')));
  await page.waitForFunction(()=>document.querySelector('.game-dialog-error')?.textContent==='Vorübergehend offline');
  assert.ok(await page.getByRole('button',{name:'Abbrechen',exact:true}).isEnabled());
  await page.getByRole('button',{name:'Abbrechen',exact:true}).click();await page.getByRole('button',{name:'Fortsetzen',exact:true}).click();
  assert.deepEqual(errors,[]);
  console.log('✓ Local replay after reload; visible reroll return at 320/390px; real placements/removals animate; reduced motion, header log, conditional round popup');
  await context.close();
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
