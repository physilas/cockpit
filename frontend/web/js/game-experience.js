/* Public board presentation only: no RNG, private hands, or game-rule changes. */
window.GameExperience = (() => {
  let previous=null, log=[], dialog=null, logButton=null, toast=null, toastTimer=null;
  const moving=new Set(), names={pilot:'Pilotin',kopilot:'Co-Pilot'};
  const fieldNames={ruder:'Ruder',triebwerk:'Schub',fahrwerk:'Fahrwerk',landeklappe:'Klappen',bremse:'Bremsen',eisbremse:'Eisbremsen',funk:'Funk',konzentration:'Konzentration',kerosin:'Kerosin',training:'Praktikantenausbildung'};
  const fields=()=>[...document.querySelectorAll('#spiel-ui .feld-zelle[data-ziel], #intern-strip .intern-end .feld-zelle')];
  const key=el=>el.dataset.ziel ? [el.dataset.ziel,el.dataset.index,el.dataset.funkFeld,el.dataset.besitzer].join('|')
    : `training|${el.closest('.intern-end').classList.contains('kopilot')?'kopilot':'pilot'}`;
  const rect=el=>el?.getBoundingClientRect();
  const visible=r=>r&&r.width>0&&r.height>0&&r.bottom>0&&r.top<innerHeight;
  const reduced=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;
  function mount() {
    if(logButton)return;
    logButton=document.createElement('button');logButton.id='game-log-button';logButton.type='button';
    logButton.title='Flugprotokoll';logButton.setAttribute('aria-label','Flugprotokoll öffnen');
    logButton.setAttribute('aria-haspopup','dialog');
    logButton.innerHTML='<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><rect x="4" y="3" width="16" height="18" rx="3"/><path d="M8 8h8M8 12h8M8 16h5"/></svg><span class="game-log-dot" hidden></span>';
    document.getElementById('menue-btn').before(logButton);
    dialog=document.createElement('dialog');dialog.id='game-log';dialog.className='game-dialog';
    dialog.setAttribute('aria-labelledby','game-log-title');
    dialog.innerHTML='<div class="game-log-heading"><h2 id="game-log-title">Flugprotokoll</h2><button type="button" aria-label="Flugprotokoll schließen">✕</button></div><ol class="game-log-list"></ol>';
    dialog.querySelector('button').onclick=()=>dialog.close();
    dialog.addEventListener('close',()=>logButton.focus({preventScroll:true}));
    document.body.appendChild(dialog);
    logButton.onclick=()=>{renderLog();logButton.querySelector('span').hidden=true;dialog.showModal();};
    toast=document.createElement('div');toast.id='game-notice';toast.hidden=true;toast.setAttribute('role','alert');document.body.appendChild(toast);
  }
  function renderLog() {
    const list=dialog.querySelector('ol');list.replaceChildren();
    for(const row of [...log].reverse()) {
      const li=document.createElement('li');li.className=row.kind||'';
      const time=document.createElement('time');time.textContent=row.time;
      const text=document.createElement('span');text.textContent=row.text;
      li.append(time,text);list.appendChild(li);
    }
    if(!log.length){const li=document.createElement('li');li.textContent='Hier erscheinen eure Spielzüge.';list.appendChild(li);}
  }
  function record(text,kind='') {
    if(!text)return;
    mount();
    log.push({text:String(text),kind,time:new Date().toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'})});
    if(log.length>150)log.shift();
    if(dialog.open)renderLog();else logButton.querySelector('span').hidden=false;
    if(kind==='fehler') {
      clearTimeout(toastTimer);toast.textContent=text;toast.hidden=false;
      toastTimer=setTimeout(()=>{toast.hidden=true;},4500);
    }
  }
  function reset() {
    previous=null;log=[];for(const animation of moving)animation.cancel();moving.clear();
    dialog?.close();if(toast)toast.hidden=true;clearTimeout(toastTimer);
    if(logButton)logButton.querySelector('span').hidden=true;
  }
  function begin(z) {
    mount();
    if(!previous||previous.id!==z.szenario_id||previous.round!==z.runde||previous.undo!==z.rueckgaengig_id)return null;
    return {state:previous, occupied:new Set(fields().filter(el=>el.classList.contains('belegt')).map(key)),
      bonus:rect(document.querySelector(previous.bonus==='intern'?'.intern-placement-hint .intern-token':'#sync-reminder .traffic-die')),
      dice:Object.fromEntries(['pilot','kopilot'].map(role=>[role,[...document.querySelectorAll(`#wuerfel-${role} .wuerfel-slot > .wuerfel`)].map(rect)])),
      planes:[...document.querySelectorAll('.vtrack-aircraft')].map(el=>({distance:Number(el.dataset.distance),icons:[...el.querySelectorAll('.aircraft-icon')].map(rect)}))};
  }
  function fly(el,frames,options) {
    document.body.appendChild(el);
    const animation=el.animate(frames,options);moving.add(animation);
    const done=()=>{el.remove();moving.delete(animation);};animation.onfinish=done;animation.oncancel=done;
  }
  function diceMotion(target,from) {
    const to=rect(target);if(!visible(from)||!visible(to)||reduced())return;
    const die=document.createElement('div');die.className=`motion-die ${target.classList.contains('kopilot')?'kopilot':'pilot'}${target.classList.contains('source-synchronisation')?' black':''}${target.classList.contains('source-intern')?' intern':''}`;
    die.textContent=target.textContent;die.setAttribute('aria-hidden','true');
    Object.assign(die.style,{left:`${from.left}px`,top:`${from.top}px`,width:`${to.width}px`,height:`${to.height}px`});
    const x=to.left-from.left,y=to.top-from.top;
    fly(die,[{transform:'translate(0,0) rotate(-16deg) scale(.9)',opacity:.85},
      {transform:`translate(${x*.48}px,${y*.48-35}px) rotate(9deg) scale(1.15)`,offset:.5},
      {transform:`translate(${x}px,${y-3}px) rotate(-3deg) scale(1.02)`,offset:.85},
      {transform:`translate(${x}px,${y}px) rotate(0deg) scale(1)`,opacity:1}],{duration:480,easing:'cubic-bezier(.22,.7,.3,1)'});
    target.animate([{opacity:0},{opacity:0,offset:.82},{opacity:1}],{duration:480});
  }
  function planeMotion(from) {
    if(!visible(from)||reduced())return;
    const plane=document.createElement('span');plane.className='motion-plane';plane.textContent='✈';plane.setAttribute('aria-hidden','true');
    Object.assign(plane.style,{left:`${from.left}px`,top:`${from.top}px`,fontSize:`${Math.max(18,from.height)}px`});
    fly(plane,[{transform:'translate(0,0) rotate(0deg)',opacity:1},
      {transform:'translate(28px,-18px) rotate(-12deg) scale(1.1)',opacity:1,offset:.4},
      {transform:'translate(85px,-70px) rotate(-25deg) scale(.35)',opacity:0}],{duration:700,easing:'ease-in'});
  }
  function finish(z,before,{reroll=false}={}) {
    const ready=document.getElementById('round-ready'),button=document.getElementById('rundenende-btn');
    const complete=['pilot','kopilot'].every(role=>z[`${role}_wuerfel_frei`]?.every(free=>!free));
    const show=z.status==='laeuft'&&z.phase==='platzieren'&&complete&&!z.zusatzaktion&&!z.kooperation&&!reroll;
    ready.hidden=!show;
    button.disabled=button.disabled||!show;
    button.textContent=z.letzte_runde?'Landung auswerten →':'Nächste Runde →';
    ready.querySelector('strong').textContent=z.letzte_runde?'Bereit zur Landung':'Alles gesetzt';
    if(before&&before.state.revision!==z.rueckgaengig_version) {
      for(const target of fields().filter(el=>el.classList.contains('belegt')&&!before.occupied.has(key(el)))) {
        const role=target.classList.contains('kopilot')?'kopilot':'pilot';
        const die=before.state.free[role].findIndex((free,i)=>free&&!z[`${role}_wuerfel_frei`][i]);
        if(die>=0)diceMotion(target,before.dice[role][die]);
        else if(before.state.bonus&&target.classList.contains(`source-${before.state.bonus}`))diceMotion(target,before.bonus);
        record(`${names[role]}: ${target.textContent} auf ${fieldNames[target.dataset.ziel||'training']||target.dataset.ziel}.`);
      }
      // Distance/round changes move the track; only same-position radio removals fly away.
      if(before.state.distance===z.entfernung) {
        let removed=0;
        (z.flugzeuge||[]).forEach((count,i)=>{
          const n=Math.max(0,(before.state.planes[i]||0)-count);removed+=n;
          const icons=before.planes.find(row=>row.distance===z.laenge-1-i)?.icons||[];
          if(n)icons.slice(-n).forEach(planeMotion);
        });
        if(removed)record(`${removed===1?'Ein Flugzeug':`${removed} Flugzeuge`} per Funk entfernt.`,'erfolg');
      }
    }
    previous={id:z.szenario_id,round:z.runde,undo:z.rueckgaengig_id,revision:z.rueckgaengig_version,distance:z.entfernung,bonus:z.zusatzaktion?.quelle,
      planes:[...(z.flugzeuge||[])],free:Object.fromEntries(['pilot','kopilot'].map(role=>[role,[...z[`${role}_wuerfel_frei`]]]))};
  }
  return {record,reset,begin,finish};
})();
