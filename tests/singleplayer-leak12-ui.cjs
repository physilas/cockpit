/* Technical profile-12 fixture; no release/qualification evidence. Actual
 * original Crew-2 tensors stay intact. The NN selects its own rescue actions.
 */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const {chooseModel,chooseRoute,chooseAbilities,leaveGame} = require('./singleplayer-setup.cjs');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),crypto=require('node:crypto');
const web=path.resolve(__dirname,'../frontend/web');
const pageUrl=process.env.COCKPIT_TEST_PAGE_URL || `${process.env.COCKPIT_TEST_URL || 'http://127.0.0.1:8000'}/frontend/web/`;
const source=fs.readFileSync(path.join(web,'js/ai-models.js'),'utf8'),sandbox={window:{}};
vm.runInNewContext(source,sandbox);
const catalog=JSON.parse(JSON.stringify(sandbox.window.COCKPIT_AI_CATALOG));
const base=catalog.models.find(model=>model.id==='crew2-v1/best.pt');
assert.equal(base?.name,'Crew 2');
const asset=JSON.parse(fs.readFileSync(path.join(web,base.url),'utf8'));
assert.equal(asset.format,4);
const tensorHash=value=>crypto.createHash('sha256').update(JSON.stringify({source:value.source,residual:value.residual})).digest('hex');
const originalTensors=tensorHash(asset);
asset.guide_margin=12;
asset.model_config={...asset.model_config,guide_margin:12};
assert.equal(tensorHash(asset),originalTensors,'Technical setup must preserve every source/residual tensor');
const fixtureId='fixture-leak12/best.pt',fixtureUrl='models/__technical-leak12__.json';
const fixture={...base,id:fixtureId,name:'Leak 12 runtime fixture (Test)',assistance_version:12,
  guide_margin:12,model_config:{...asset.model_config},url:fixtureUrl,
  fingerprint:crypto.createHash('sha256').update(JSON.stringify(asset)).digest('hex'),
  supported_airports:['LOG_ATL_YELLOW'],quality:{approved:false},
  preview:{enabled:true,evaluation_kind:'development',technical_fixture:true,
    supported_cases:[{airport:'LOG_ATL_YELLOW',abilities:['adaptation']}],
    case_results:{'LOG_ATL_YELLOW|adaptation':{games:1,wins:0,win_rate:0}}}};
const sessions=page=>page.evaluate(async()=>{
  const db=await new Promise(resolve=>{const request=indexedDB.open('flyteam-learning-v1',2);request.onsuccess=()=>resolve(request.result);});
  return new Promise(resolve=>{const request=db.transaction('sessions').objectStore('sessions').getAll();request.onsuccess=()=>resolve(request.result);});
});
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.COCKPIT_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  try {
    const context=await browser.newContext({viewport:{width:390,height:844},serviceWorkers:'block'}),errors=[];
    await context.route('**/js/ai-models.js',route=>route.fulfill({contentType:'application/javascript',
      body:source+`\nwindow.COCKPIT_AI_CATALOG.models.unshift(${JSON.stringify(fixture)});`}));
    await context.route('**/'+fixtureUrl,route=>route.fulfill({contentType:'application/json',body:JSON.stringify(asset)}));
    await context.route('**/js/cloud-config.js',route=>route.fulfill({contentType:'application/javascript',body:'window.COCKPIT_LEARNING_CLOUD={};'}));
    const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
    await page.goto(pageUrl);await page.getByRole('button',{name:/Singleplayer/}).click();
    assert.equal(await page.locator('#solo-model').inputValue(),'crew-basegame-v1/best.pt');
    const unchanged=await page.evaluate(()=>COCKPIT_AI_CATALOG.models.filter(model=>!model.id.startsWith('fixture-leak12/')));
    assert.deepEqual(unchanged,catalog.models,'The fixture must preserve all real model declarations');
    assert.equal(unchanged.find(model=>model.id==='crew4-leak-preview-v1/best.pt').assistance_version,11);
    await page.locator('[data-mode="feedback"]').click();
    await chooseModel(page,fixtureId,'pilot');
    await chooseRoute(page,'ATL-yellow');
    assert.equal(await page.locator('#solo-abilities option').count(),1);
    assert.equal(await page.locator('#solo-abilities').inputValue(),'LOG_ATL_YELLOW|adaptation');
    assert.match(await page.locator('#solo-description').innerText(),/noch nicht unabhängig qualifiziert/);
    await page.locator('#solo-consent').check();await page.locator('#solo-start').click();
    await page.locator('#spiel-ui').waitFor({state:'visible',timeout:90000});
    const before=await page.evaluate(()=>{
      // Mirror the native rescue onto the AI copilot using legal published
      // placements. No NN action, logit, reference or policy label is injected.
      pyodide.runPython(`
import backend.bridge as b
while b._spiel.phase == 'verkehr': b._spiel.wirf_verkehrswuerfel()
g = b._spiel
g.landung.flugzeuge[:] = [0]*len(g.landung.flugzeuge)
g.neuwurf_plaettchen = 0
for role in ('pilot', 'kopilot'):
 for die in g._wuerfel_liste(role): die.augenzahl=1
for role, die, target, index, face in [
 ('pilot',0,'ruder',None,4),('kopilot',1,'triebwerk',None,3),
 ('pilot',1,'triebwerk',None,3),('kopilot',2,'landeklappe',0,1),
 ('pilot',2,'fahrwerk',0,1),('kopilot',3,'funk',None,1),
 ('pilot',3,'fahrwerk',1,3)]:
 g._wuerfel_liste(role)[die].augenzahl=face
 result=g.platziere(role,die,target,index)
 assert result.erfolg and not result.verloren,(role,target,result)
`);
      resetVerkehrUi();render(pyToJs(bridge.zustand()));
      const d=pyToJs(aiBridge.decision('kopilot','null',0,256,12,3));
      const m=COCKPIT_AI_CATALOG.models.find(model=>model.id==='fixture-leak12/best.pt');
      return {role:d.role,kinds:d.reference_action_mask.flatMap((ok,index)=>ok?[m.schema.actions[index].kind]:[]),
        observation:d.observation.length,mask:d.action_mask.length,
        ownFace:aktuellerZustand.kopilot_wuerfel[0],attitude:aktuellerZustand.fluglage,
        coffee:aktuellerZustand.kaffeetassen,publicKeys:Object.keys(d.public_state)};
    });
    assert.equal(before.role,'kopilot');assert.deepEqual(before.kinds,['adaptation']);
    assert.equal(before.observation,489);assert.equal(before.mask,217);
    assert.equal(before.ownFace,1);assert.equal(before.attitude,0);assert.equal(before.coffee,0);
    assert.ok(!before.publicKeys.includes('own_dice'));
    assert.ok(await page.locator('#wuerfel-kopilot .wuerfel:not(.platziert)').evaluateAll(dice=>dice.length===1 && dice.every(die=>die.textContent==='?')));
    let recording;
    for(let attempt=0;attempt<70;attempt++) {
      await page.waitForTimeout(100);
      if(await page.locator('#ai-resume').count()) throw new Error(await page.locator('.ai-paused').innerText());
      recording=(await sessions(page)).find(session=>session.model.id===fixtureId);
      if(recording?.events.filter(event=>event.actor==='ai').length>=2) break;
    }
    const actions=recording?.events.filter(event=>event.actor==='ai') || [];
    assert.deepEqual(actions.map(event=>({kind:event.action.kind,die:event.action.die,target:event.action.target})),
      [{kind:'adaptation',die:0,target:undefined},{kind:'place',die:0,target:'ruder'}],
      'Actual NN must choose both rescue actions; a reference alone is not this runtime proof');
    assert.ok(actions.every(event=>event.training_compatible && event.decision.observation.length===489
      && event.decision.action_mask.length===217 && event.decision.reference_action_mask.length===217
      && event.decision.reference_action_mask[event.action_id]));
    assert.ok(actions.every(event=>!('own_dice' in event.decision.public_state)));
    assert.equal(recording.model.assistance_version,12);
    assert.equal(recording.model.model_config.guide_margin,12);
    assert.equal(recording.model.fingerprint,fixture.fingerprint);
    assert.deepEqual(recording.scenario.ability_ids,['adaptation']);
    assert.equal(recording.scenario.case_key,'LOG_ATL_YELLOW|adaptation');
    const after=await page.evaluate(()=>({status:aktuellerZustand.status,reason:aktuellerZustand.verlust_grund || '',
      attitude:aktuellerZustand.fluglage,face:aktuellerZustand.kopilot_wuerfel[0],
      adaptation:aktuellerZustand.anpassung_verfuegbar.kopilot}));
    assert.equal(after.status,'laeuft');assert.equal(after.reason,'');
    assert.equal(after.attitude,2);assert.equal(after.face,6);assert.equal(after.adaptation,false);
    await page.evaluate(()=>Singleplayer.stop('technical_fixture_finished'));
    assert.deepEqual(errors,[]);
    console.log('✓ Profile12/margin12 with original Crew2 tensors: actual copilot NN chooses adaptation1→6 then safe rudder6; exact card identity, refs, schema3 records and old releases preserved (no win/qualification claim)');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
