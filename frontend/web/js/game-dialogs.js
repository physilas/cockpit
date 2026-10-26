/* Shared menu and result overlays. Game logic remains in the adapters. */
window.GameDialogs = (() => {
  let dialog, adapter, screen = null, dismissed = null, signature = null;
  const esc = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function mount() {
    if (dialog) return;
    dialog=document.createElement('dialog');dialog.id='game-dialog';dialog.className='game-dialog';
    dialog.setAttribute('aria-labelledby','game-dialog-title');
    dialog.addEventListener('cancel',e=>{e.preventDefault();if(screen?.confirm)show(screen.parent);else close();});
    document.body.appendChild(dialog);
  }
  function close(resume=true) {
    if(screen?.result)dismissed=signature;
    dialog?.close();screen=null;
    if(resume)adapter?.onResume?.();
  }
  function show(next) {
    mount();screen=next;
    const title=next.confirm ? (next.action==='restart'?'Partie neu starten?':'Zum Hauptmenü?')
      : next.result ? (next.status==='gewonnen'?'Sicher gelandet!':'Leider verloren') : 'Spielmenü';
    const text=next.confirm ? (next.action==='restart'?'Die laufende Partie wird durch eine neue ersetzt.':adapter?.confirmMainText||'Dein Spielstand bleibt auf diesem Gerät zum Fortsetzen gespeichert.')
      : next.result ? next.message : 'Bereit für den nächsten Zug?';
    dialog.innerHTML=`<div class="game-dialog-icon" aria-hidden="true">${next.confirm?'?':next.result?(next.status==='gewonnen'?'🛬':'✈'):'✈'}</div><h2 id="game-dialog-title">${esc(title)}</h2><p>${esc(text)}</p><div class="game-dialog-actions"></div><p class="game-dialog-error" role="alert"></p>`;
    const actions=dialog.querySelector('.game-dialog-actions');
    const add=(label,action,primary=false)=>{
      const b=document.createElement('button');b.type='button';b.textContent=label;
      if(primary)b.className='primary';
      b.onclick=async()=>{try{await action();}catch(e){screen=next;if(!dialog.open)dialog.showModal();dialog.querySelector('.game-dialog-error').textContent=e.message;}};
      actions.appendChild(b);
    };
    const confirm=action=>show({confirm:true,action,parent:next});
    if(next.confirm) {
      add('Abbrechen',()=>show(next.parent));
      add(next.action==='restart'?'Neu starten':'Zum Hauptmenü',async()=>{
        close(false);await adapter[next.action==='restart'?'onRestart':'onMainMenu']();
      },true);
    } else if(next.result) {
      add('Erneut spielen',()=>confirm('restart'),true);
      if(adapter?.canRestart?.()===false){actions.lastElementChild.disabled=true;actions.lastElementChild.title='Nur der Gastgeber kann neu starten.';}
      add('Zurück zum Spielfeld',()=>close());
      add('Zurück zum Hauptmenü',()=>confirm('main'));
    } else {
      add('Fortsetzen',()=>close(),true);
      add('Neustart',()=>confirm('restart'));
      if(adapter?.canRestart?.()===false){actions.lastElementChild.disabled=true;actions.lastElementChild.title='Nur der Gastgeber kann neu starten.';}
      add('Hauptmenü',()=>confirm('main'));
    }
    if(!dialog.open)dialog.showModal();
    actions.querySelector('button')?.focus();
  }
  return {
    connect(value){adapter=value;},
    menu(){adapter?.onPause?.();show({menu:true});},
    result(z,message){
      if(z.status==='laeuft'){if(screen?.result)close(false);signature=null;dismissed=null;return;}
      signature=`${z.szenario_id}|${z.runde}|${z.status}|${z.verlust_grund}`;
      if(signature!==dismissed&&!screen){adapter?.onPause?.();show({result:true,status:z.status,message});}
    },
    reset(){close(false);dismissed=signature=null;},
    open:()=>Boolean(screen),
    dismiss:close,
  };
})();
