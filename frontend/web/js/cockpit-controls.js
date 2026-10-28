/* Shared physical dice and a touch-friendly coffee wheel for both game modes. */
window.CockpitControls = (() => {
  function placedDie(container, die) {
    const source=die.quelle, owner=die.besitzer;
    container.classList.add('belegt',owner);
    if(source)container.classList.add(`source-${source}`);
    const cube=document.createElement('span');
    cube.className=`placed-die ${source==='synchronisation'?'black':source==='intern'?'intern':owner}`;
    cube.textContent=die.wert;
    cube.setAttribute('aria-label',`${source==='synchronisation'?'Schwarzer':owner==='pilot'?'Blauer':'Oranger'} Würfel: ${die.wert}`);
    container.replaceChildren(cube);
  }
  let dialog=null;
  function closeCoffee() {dialog?.close();}
  function coffee({value,deltas,owner,onApply}) {
    if(!dialog){dialog=document.createElement('dialog');dialog.id='coffee-dialog';dialog.className='coffee-dialog';document.body.appendChild(dialog);}
    const values=[value,...deltas.map(delta=>value+delta)].filter((n,i,a)=>n>=1&&n<=6&&a.indexOf(n)===i).sort((a,b)=>a-b);
    let selected=value;
    dialog.setAttribute('aria-labelledby','coffee-title');
    dialog.innerHTML=`<h2 id="coffee-title">Würfel mit Kaffee ändern</h2><p>Nach oben oder unten drehen</p><div class="coffee-wheel-wrap"><div class="coffee-wheel-band" aria-hidden="true"></div><div class="coffee-wheel" role="listbox" tabindex="0" aria-label="Neuer Würfelwert">${values.map(n=>`<div id="coffee-value-${n}" class="coffee-wheel-value" role="option" aria-selected="${n===value}" data-value="${n}">${n}</div>`).join('')}</div></div><p id="coffee-cost" aria-live="polite"></p><div class="coffee-dialog-actions"><button type="button" id="coffee-cancel">Abbrechen</button><button type="button" id="coffee-apply" disabled>Übernehmen</button></div>`;
    const wheel=dialog.querySelector('.coffee-wheel'), apply=dialog.querySelector('#coffee-apply');
    wheel.classList.add(owner==='pilot'?'pilot':'kopilot');
    const update=()=>{
      const index=Math.max(0,Math.min(values.length-1,Math.round(wheel.scrollTop/44)));
      selected=values[index];
      wheel.querySelectorAll('[role=option]').forEach(option=>option.setAttribute('aria-selected',String(Number(option.dataset.value)===selected)));
      wheel.setAttribute('aria-activedescendant',`coffee-value-${selected}`);
      const cups=Math.abs(selected-value);
      dialog.querySelector('#coffee-cost').textContent=cups?`${value} → ${selected} · ${cups} ${cups===1?'Kaffeetasse':'Kaffeetassen'}`:'Kein Kaffee nötig';
      apply.disabled=selected===value;
    };
    wheel.addEventListener('scroll',update,{passive:true});
    wheel.addEventListener('click',event=>{const option=event.target.closest('[data-value]');if(option){wheel.scrollTop=values.indexOf(Number(option.dataset.value))*44;update();}});
    wheel.addEventListener('keydown',event=>{
      if(!['ArrowUp','ArrowDown','Home','End'].includes(event.key))return;
      event.preventDefault();
      const index=values.indexOf(selected),next=event.key==='Home'?0:event.key==='End'?values.length-1:index+(event.key==='ArrowUp'?-1:1);
      wheel.scrollTop=Math.max(0,Math.min(values.length-1,next))*44;update();
    });
    dialog.querySelector('#coffee-cancel').onclick=closeCoffee;
    apply.onclick=()=>{const delta=selected-value;if(!deltas.includes(delta))return;closeCoffee();onApply(delta);};
    if(!dialog.open)dialog.showModal();
    wheel.scrollTop=values.indexOf(value)*44;update();wheel.focus({preventScroll:true});
  }
  return {placedDie,coffee,closeCoffee};
})();
