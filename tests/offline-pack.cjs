/* Service-worker behavior without browser automation or network access. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {webcrypto} = require('node:crypto');
const root = path.resolve(__dirname, '../frontend/web');
const origin = 'https://example.test/cockpit/';
const maps = new Map(), handlers = {}, requests = [];
let online = true, corrupt = null, quota = false, skips=0;
const key = request => typeof request === 'string' ? request : request.url;
const fetchFile = async request => {
  const url = key(request); requests.push(url);
  if (!online) throw new Error('offline');
  const rel = new URL(url).pathname.replace(/^\/cockpit\//, '');
  const data = rel === corrupt ? Buffer.from('interrupted download') : fs.readFileSync(path.join(root, rel));
  return new Response(data, {status:200});
};
const caches = {
  async open(name) {
    if (!maps.has(name)) maps.set(name, new Map());
    const map = maps.get(name);
    return {
      async match(request) { const data=map.get(key(request)); return data ? new Response(data.slice()) : undefined; },
      async put(request, response) {
        if (quota) { const error = new Error('quota'); error.name='QuotaExceededError'; throw error; }
        map.set(key(request), new Uint8Array(await response.arrayBuffer()));
      },
      async addAll(list) { for (const request of list) await this.put(request, await fetchFile(request)); },
    };
  },
  async keys() {return [...maps.keys()];},
  async delete(name) {return maps.delete(name);},
};
const context = vm.createContext({Request, Response, URL, caches, crypto:webcrypto,
  fetch:fetchFile, self:{location:{href:origin+'sw.js',origin:new URL(origin).origin},
    addEventListener:(name, fn)=>{handlers[name]=fn;},skipWaiting:async()=>{skips++;},clients:{claim:async()=>{}}}});
context.importScripts = (...names) => names.forEach(name => vm.runInContext(fs.readFileSync(path.join(root,name.replace('./','')),'utf8'),context));
vm.runInContext(fs.readFileSync(path.join(root,'sw.js'),'utf8'),context);
const pack=vm.runInContext('PACK',context);
const shellName=vm.runInContext('CACHE_NAME',context);
async function lifecycle(type) {let result;handlers[type]({waitUntil:p=>{result=p;}});await result;}
async function message(type, version=pack.version) {
  const messages=[];let done;
  handlers.message({data:{type,version},ports:[{postMessage:data=>messages.push(data)}],waitUntil:p=>{done=p;}});
  await done;return messages;
}
async function get(url) {let result;handlers.fetch({request:new Request(url),respondWith:p=>{result=p;}});return result===undefined?undefined:await result;}
(async()=>{
  await lifecycle('install');
  assert.equal(skips,1,'first/legacy installation activates');
  context.setTimeout=setTimeout;context.clearTimeout=clearTimeout;
  context.MessageChannel=class {constructor(){this.port1={close(){}};this.port2={reply:data=>this.port1.onmessage({data})};}};
  context.self.registration={active:{postMessage(data,ports){ports[0].reply({protocol:1});}}};
  await lifecycle('install');assert.equal(skips,1,'managed update waits for user');
  assert.equal((await message('UPDATE_CAPABILITIES')).at(-1).protocol,1);
  await message('ACTIVATE_UPDATE');assert.equal(skips,2,'explicit update activates');
  assert.equal((await message('OFFLINE_STATUS')).at(-1).ready,false);
  assert.match((await message('OFFLINE_STATUS','old-version')).at(-1).error,/neu laden/);
  corrupt=pack.assets[1].url;
  let result=await message('OFFLINE_DOWNLOAD');
  assert.match(result.at(-1).error,/App-Version/);
  assert.equal((await message('OFFLINE_STATUS')).at(-1).ready,false);
  assert(!maps.get(pack.cache).has(new URL(corrupt,origin).href),'reject corrupt WASM');
  const validFirst = new URL(pack.assets[0].url,origin).href;
  const before=requests.filter(url=>url===validFirst).length;
  corrupt=null;
  result=await message('OFFLINE_DOWNLOAD');
  assert.equal(result.at(-1).ready,true,JSON.stringify(result.at(-1)));
  assert.equal(requests.filter(url=>url===validFirst).length,before,'retry reuses verified files');
  assert.equal(result.at(-2).progress,pack.bytes);
  online=false;
  for(const asset of [...pack.shell,...pack.assets]){
    const response=await get(new URL(asset.url+'?cache-buster=1',origin).href);
    assert(response?.ok,asset.url+' available offline');
  }
  assert((await get(origin)).ok,'directory navigation offline');
  assert.equal(await get(origin+'api/feedback'),undefined,'cloud data not cached');
  const missing=pack.assets.at(-1);
  maps.get(pack.cache).delete(new URL(missing.url,origin).href);
  assert.equal((await message('OFFLINE_STATUS')).at(-1).ready,false,'detect eviction');
  assert((await message('OFFLINE_DOWNLOAD')).at(-1).error,'offline incomplete download reported');
  online=true;quota=true;
  assert.match((await message('OFFLINE_DOWNLOAD')).at(-1).error,/Speicher/);
  quota=false;
  assert.equal((await message('OFFLINE_DOWNLOAD')).at(-1).ready,true);
  maps.set('cockpit-old-release',new Map());
  await lifecycle('activate');
  assert(!maps.has('cockpit-old-release'));
  assert(maps.has(pack.cache),'immutable runtime/models retained on activation');
  assert(maps.has(shellName));
  console.log('Offline checks passed: integrity, interrupted retry, quota, eviction, version mismatch, every runtime/model, directory navigation, cache isolation.');
})().catch(error=>{console.error(error);process.exitCode=1;});
