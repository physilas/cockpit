/* Navigate the same visible setup steps as a player. */
const assert = require('node:assert/strict');

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
  if (route) await page.locator('#solo-route').selectOption(route);
}

module.exports = {chooseMode, chooseModel, chooseRoute};
