/* Navigate the same visible setup steps as a player. */
const assert = require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
// Historical runtime regressions deliberately expose archived release fixtures.
// The canonical production menu has its own separate browser test.
function legacySource(){
 return fs.readFileSync(path.join(__dirname,'../frontend/web/js/ai-models.js'),'utf8')+`
 window.COCKPIT_AI_CATALOG.models=window.COCKPIT_AI_CATALOG.models.filter(m=>!m.crew_number).map(({ui_hidden,...m})=>m);
 `;
}
async function installLegacyCatalogue(context){
 await context.route('**/js/ai-models.js',r=>r.fulfill({contentType:'application/javascript',body:legacySource()}));
}

async function chooseMode(page, mode) {
  while (await page.locator('#singleplayer-menu').getAttribute('data-step') !== 'mode')
    await page.locator('#solo-back').click();
  await page.locator(`[data-mode="${mode}"]`).click();
}

async function chooseModel(page, model, role) {
  if (await page.locator('#singleplayer-menu').getAttribute('data-step') === 'route')
    await page.locator('#solo-back').click();
  assert.equal(await page.locator('#singleplayer-menu').getAttribute('data-step'), 'model');
  if (model) await page.locator('#solo-model').selectOption(model);
  if (role) await page.locator('#solo-role').selectOption(role);
}

async function chooseRoute(page, route) {
  if (await page.locator('#singleplayer-menu').getAttribute('data-step') === 'model')
    await page.locator('#solo-next').click();
  assert.equal(await page.locator('#singleplayer-menu').getAttribute('data-step'), 'route');
  const gallery=page.locator('#solo-landings [data-action="gallery"]');
  if(await gallery.isVisible())await gallery.click();
  if(route)await page.locator(`#solo-landings [data-scenario="${route}"]`).click();
  const first=await page.locator('#solo-abilities option').count() ? await page.locator('#solo-abilities option').first().getAttribute('value') : null;
  if(first)await chooseAbilities(page,first);
}

async function chooseAbilities(page, key) {
  const wanted=key.split('|')[1]?.split(',').filter(Boolean)||[];
  const root=page.locator('#solo-landings');
  for(const id of await root.locator('[data-ability][aria-pressed="true"]').evaluateAll(buttons=>buttons.map(b=>b.dataset.ability)))
    if(!wanted.includes(id))await root.locator(`[data-ability="${id}"]`).click();
  for(const id of wanted)if(await root.locator(`[data-ability="${id}"]`).getAttribute('aria-pressed')!=='true')await root.locator(`[data-ability="${id}"]`).click();
  if(wanted.length&&await page.locator('#solo-abilities').inputValue()!==key){
    await root.locator(`[data-ability="${wanted[0]}"]`).click();await root.locator(`[data-ability="${wanted[0]}"]`).click();
  }
}

async function leaveGame(page) {
  const result=page.getByRole('button',{name:'Zurück zum Spielfeld',exact:true});
  if(await result.isVisible())await result.click();
  await page.locator('#menue-btn').click();
  await page.getByRole('button',{name:'Hauptmenü',exact:true}).click();
  await page.getByRole('button',{name:'Zum Hauptmenü',exact:true}).click();
}

module.exports = {chooseMode, chooseModel, chooseRoute, chooseAbilities, leaveGame, legacySource, installLegacyCatalogue};
