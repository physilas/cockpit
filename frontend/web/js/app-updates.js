/* Observe deployed app versions, prepare them fully, then switch at the menu. */
(() => {
  if(!('serviceWorker' in navigator))return;
  const current=COCKPIT_OFFLINE_ASSETS.version;
  let registration=null,available=null,dismissed=null,busy=false,reloading=false,lastCheck=0;
  const canApply=()=>{
    if(typeof window.CockpitUpdateHooks?.canApply==='function')return window.CockpitUpdateHooks.canApply();
    const menu=document.getElementById('start-menu')||document.getElementById('screen-menu');
    return Boolean(menu?.getClientRects().length);
  };
  const status=document.getElementById('app-update-status');
  const checkButton=document.getElementById('app-update-check');
  const modal=document.createElement('dialog');modal.className='app-update-dialog';modal.id='app-update-dialog';
  modal.setAttribute('aria-labelledby','app-update-title');
  modal.innerHTML='<h2 id="app-update-title">Update verfügbar</h2><p>Eine neue Version von Fly Team ist fertig heruntergeladen.</p><p id="app-update-message" role="status">Deine Spielstände und gespeicherten Crews bleiben erhalten.</p><div><button type="button" id="app-update-later">Später</button><button type="button" id="app-update-now">Jetzt aktualisieren</button></div>';
  document.body.appendChild(modal);
  const message=modal.querySelector('#app-update-message'),now=modal.querySelector('#app-update-now'),later=modal.querySelector('#app-update-later');
  function request(worker,data,progress,timeout=120000){
    return new Promise((resolve,reject)=>{
      if(!worker){reject(Error('Update noch nicht bereit.'));return;}
      const channel=new MessageChannel();let timer;
      const arm=()=>{clearTimeout(timer);timer=setTimeout(()=>{channel.port1.close();reject(Error('Verbindung unterbrochen. Bitte erneut versuchen.'));},timeout);};
      channel.port1.onmessage=({data:reply})=>{arm();if(reply.progress!==undefined){progress?.(reply);return;}clearTimeout(timer);channel.port1.close();reply.error?reject(Error(reply.error)):resolve(reply);};
      arm();worker.postMessage(data,[channel.port2]);
    });
  }
  async function info(worker){
    return request(worker,{type:'UPDATE_CAPABILITIES'},null,1200).catch(()=>null);
  }
  const originalController=navigator.serviceWorker.controller;
  const legacyMigration=originalController?info(originalController).then(details=>details?.protocol!==1):Promise.resolve(false);
  function show(){
    if(!available||busy||dismissed===available.version||!canApply())return;
    message.textContent='Deine Spielstände und gespeicherten Crews bleiben erhalten.';
    if(!modal.open)modal.showModal();
  }
  async function offer(worker,allowSameVersion=false){
    const details=await info(worker).catch(()=>null);
    if(!details?.version||details.version===current&&!allowSameVersion)return;
    available={worker,version:details.version};
    if(status)status.textContent='Neue Version verfügbar.';
    if(checkButton)checkButton.textContent='Update verfügbar';
    const header=document.getElementById('spiel-auswahl');
    if(header&&!document.getElementById('app-update-badge')){
      const badge=document.createElement('button');badge.id='app-update-badge';badge.textContent='↑';badge.title='Update verfügbar';badge.setAttribute('aria-label','Update verfügbar');badge.onclick=()=>{if(canApply())show();else window.setzeMeldung?.('Update bereit. Zum Aktualisieren bitte ins Hauptmenü wechseln.');};header.appendChild(badge);
    }
    show();
  }
  function observe(worker){if(!worker)return;worker.addEventListener('statechange',()=>{if(worker.state==='installed'&&navigator.serviceWorker.controller)offer(registration.waiting||worker);});}
  async function check(manual=false){
    if(busy||!registration)return;
    if(navigator.onLine===false){if(manual&&status)status.textContent='Updates werden geprüft, sobald du wieder online bist.';return;}
    if(!manual&&Date.now()-lastCheck<60000)return;
    lastCheck=Date.now();if(manual&&status)status.textContent='Suche nach Updates …';
    try{
      await registration.update();
      if(registration.waiting)await offer(registration.waiting);
      else if(registration.installing){if(status)status.textContent='Neue Version wird heruntergeladen …';observe(registration.installing);}
      else if(manual&&status)status.textContent='Du verwendest die aktuelle Version.';
    }catch{if(manual&&status)status.textContent='Update-Prüfung gerade nicht möglich. Offline-Spielen bleibt verfügbar.';}
  }
  later.onclick=()=>{dismissed=available?.version;modal.close();};
  modal.addEventListener('cancel',event=>{if(busy)event.preventDefault();else dismissed=available?.version;});
  now.onclick=async()=>{
    if(busy||!available||!canApply())return;
    busy=true;now.disabled=later.disabled=true;
    try{
      await window.CockpitUpdateHooks?.prepare?.();
      const waiting=registration.waiting;
      if(waiting){
        const previous=await request(navigator.serviceWorker.controller,{type:'OFFLINE_STATUS',version:current}).catch(()=>({ready:false}));
        if(previous.ready){
          message.textContent='Dein Offline-Paket wird mit aktualisiert …';
          await request(waiting,{type:'OFFLINE_DOWNLOAD',version:available.version},value=>{message.textContent=`Offline-Paket: ${Math.round(value.progress/value.total*100)} %`;});
        }
        message.textContent='Update wird aktiviert …';
        waiting.postMessage({type:'ACTIVATE_UPDATE'});
        // controllerchange performs exactly one reload after cache activation.
      }else{reloading=true;location.reload();}
    }catch(error){message.textContent=error.message;busy=false;now.disabled=later.disabled=false;}
  };
  navigator.serviceWorker.addEventListener('controllerchange',async()=>{
    if(busy&&!reloading&&canApply()){reloading=true;location.reload();}
    else {
      const migration=originalController&&navigator.serviceWorker.controller!==originalController&&await legacyMigration;
      offer(navigator.serviceWorker.controller,Boolean(migration));
    }
  });
  navigator.serviceWorker.register('./sw.js',{updateViaCache:'none'}).then(reg=>{
    registration=reg;observe(reg.installing);if(reg.waiting)offer(reg.waiting);
    reg.addEventListener('updatefound',()=>observe(reg.installing));check();
  }).catch(()=>{if(status)status.textContent='Automatische Updates sind momentan nicht verfügbar.';});
  checkButton?.addEventListener('click',()=>{dismissed=null;if(available)show();else check(true);});
  window.addEventListener('online',()=>check());
  window.addEventListener('pageshow',()=>{check();show();});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden){check();show();}});
  setInterval(()=>{if(!document.hidden)check();},300000);
  const menu=document.getElementById('start-menu')||document.getElementById('screen-menu');
  if(menu)new MutationObserver(()=>show()).observe(menu,{attributes:true,attributeFilter:['class']});
})();
