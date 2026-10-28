/* Public goals before rolling; move ratings remain separate learning records. */
window.RoundPlanning = (() => {
  let dialog=null, current=null, submitting=false, peeking=false, returnButton=null;
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const copy=value=>JSON.parse(JSON.stringify(value));
  function draftFor(proposal,saved) {
    const compatible=saved?.version===1&&saved.round===proposal.round;
    const values=Object.fromEntries(proposal.goals.map(goal=>[goal.key,compatible&&goal.options.some(o=>o.value===saved.values?.[goal.key])?saved.values[goal.key]:goal.selected]));
    return {version:1,round:proposal.round,values,index:compatible?Math.max(0,Math.min(2,saved.index||0)):0,
      mode:compatible&&['dialog','own','summary'].includes(saved.mode)?saved.mode:'dialog',
      accepted:proposal.goals.map((_,i)=>compatible&&saved.accepted?.[i]===true),source:compatible&&saved.source==='human'?'human':'ai',
      rejected:compatible&&Array.isArray(saved.rejected)?saved.rejected.slice(-24):[]};
  }
  const choice=(goal,draft)=>goal.options.find(o=>o.value===draft.values[goal.key]);
  const plan=(proposal,draft)=>({version:1,round:proposal.round,...draft.values});
  function mount() {
    if(dialog)return;
    returnButton=document.createElement('button');returnButton.id='round-plan-return';returnButton.type='button';returnButton.hidden=true;
    returnButton.textContent='Zurück zur Rundenabsprache';returnButton.addEventListener('click',()=>{peeking=false;returnButton.hidden=true;if(current){render();dialog.showModal();}});document.body.appendChild(returnButton);
    dialog=document.createElement('dialog');dialog.id='round-plan-dialog';dialog.setAttribute('aria-labelledby','round-plan-title');
    dialog.addEventListener('cancel',event=>{event.preventDefault();if(current?.inspect)close();});
    dialog.addEventListener('change',event=>{
      const c=current,input=event.target;if(!c||c.inspect||!input.matches('select[name]'))return;
      const goal=c.proposal.goals.find(g=>g.key===input.name),option=goal?.options[Number(input.value)];
      if(!option)return;c.draft.values[goal.key]=option.value;c.draft.source='human';c.draft.accepted=[false,false,false];
      c.callbacks.onChange(copy(c.draft));
    });
    dialog.addEventListener('click',async event=>{
      const b=event.target.closest('button[data-plan-action]');if(!b||submitting)return;
      const action=b.dataset.planAction,c=current;if(!c)return;
      if(action==='close'){close();return;}
      if(action==='peek'){peeking=true;dialog.close();returnButton.hidden=false;returnButton.focus({preventScroll:true});return;}
      if(action==='menu'){c.callbacks.onMenu();return;}
      const d=c.draft,g=c.proposal.goals[d.index];
      if(action==='yes'){d.accepted[d.index]=true;if(d.index===2)d.mode='summary';else d.index++;}
      if(action==='no'){
        d.rejected.push({key:g.key,value:d.values[g.key]});d.rejected=d.rejected.slice(-24);
        const i=g.options.findIndex(o=>o.value===d.values[g.key]);d.values[g.key]=g.options[(i+1)%g.options.length].value;d.accepted[d.index]=false;
      }
      if(action==='back'){d.index=Math.max(0,d.index-1);d.mode='dialog';}
      if(action==='own')d.mode='own';
      if(action==='review'){d.index=0;d.mode='dialog';}
      if(action==='apply-own'){
        c.proposal.goals.forEach(goal=>{const input=dialog.querySelector(`[name="${goal.key}"]`);if(input)d.values[goal.key]=goal.options[Number(input.value)].value;});
        d.source='human';d.accepted=[true,true,true];d.mode='summary';
      }
      if(action==='confirm'||action==='skip'){
        submitting=true;render();
        try{await c.callbacks.onConfirm(action==='skip'?null:plan(c.proposal,d),copy(d),c.proposal);close();}
        catch(error){submitting=false;render();dialog.querySelector('[role=alert]').textContent=error.message;}
        return;
      }
      c.callbacks.onChange(copy(d));render(action==='no'?'no':null);
    });
    document.body.appendChild(dialog);
  }
  function summary(proposal,draft) {
    return `<ul class="round-plan-list">${proposal.goals.map(g=>`<li><span>${esc(g.title)}</span><strong>${esc(choice(g,draft).label)}</strong></li>`).join('')}</ul>`;
  }
  function render(focusAction=null) {
    const c=current;if(!c)return;
    if(c.inspect){
      dialog.innerHTML=`<div class="round-plan-heading"><h2 id="round-plan-title">Rundenplan · Runde ${c.entry.round}</h2></div>${summary(c.entry.proposal,c.entry.draft)}<p class="round-plan-note">Nach dem Würfeln bleibt die Absprache fest. Je nach Wurf kann die KI davon abweichen.</p>${c.entry.result?`<p>${esc(c.entry.result)}</p>`:''}<button type="button" class="round-plan-primary" data-plan-action="close">Zurück zum Spiel</button><button type="button" data-plan-action="peek">Spielfeld ansehen</button>`;
      return;
    }
    const {proposal:p,draft:d}=c,g=p.goals[d.index],selected=choice(g,d);
    const btn=(action,text,primary=false)=>`<button type="button" ${submitting?'disabled':''} class="${primary?'round-plan-primary':action==='peek'?'neuwurf-ansehen':''}" data-plan-action="${action}">${text}</button>`;
    let body;
    if(d.mode==='own'){
      body=`<h3>Meine Ansage</h3><div class="round-plan-own">${p.goals.map(goal=>`<label>${esc(goal.title)}${goal.options.length>1?`<select name="${goal.key}">${goal.options.map((o,i)=>`<option value="${i}" ${o.value===d.values[goal.key]?'selected':''}>${esc(o.label)}</option>`).join('')}</select>`:`<strong>${esc(goal.options[0].label)}</strong>`}</label>`).join('')}</div>${btn('apply-own','Ansage übernehmen',true)}${btn('review','Zurück zu den Vorschlägen')}`;
    }else if(d.mode==='summary'){
      body=`<h3>${d.source==='human'?'Deine Ansage · so versteht sie die KI':'Unser gemeinsamer Plan'}</h3>${summary(p,d)}<p class="round-plan-note">Ein Ziel ist eine Priorität. Die Würfel entscheiden, was möglich ist.</p>${btn('confirm','Plan übernehmen & würfeln',true)}${btn('own','Meine Ansage ändern')}${btn('review','Vorschläge noch einmal ansehen')}`;
    }else{
      body=`<p class="round-plan-step">Vorschlag ${d.index+1} von 3 · ${esc(g.title)}</p><h3 class="round-plan-proposal">${esc(selected.label)}</h3><p class="round-plan-reason">${esc(selected.reason)}</p><div class="round-plan-votes">${btn('yes','👍 Passt',true)}${g.options.length>1?btn('no','👎 Anders'):''}</div><div class="round-plan-nav">${d.index?btn('back','← Vorheriger Vorschlag'):''}${btn('own','Meine Ansage')}</div>`;
    }
    dialog.innerHTML=`<div class="round-plan-heading"><div><p>Vor dem Würfeln</p><h2 id="round-plan-title">Runde ${p.round} · Unser Plan</h2></div>${btn('menu','Menü')}</div>${p.previousResult?`<p class="round-plan-previous">${esc(p.previousResult)}</p>`:''}<div class="round-plan-body">${body}</div><div role="alert" class="round-plan-error"></div><div class="round-plan-footer">${btn('peek','Spielfeld ansehen')}${btn('skip','Ohne Absprache würfeln')}</div>`;
    if(dialog.open){
      const target=dialog.querySelector(focusAction?`[data-plan-action="${focusAction}"]`:d.mode==='own'?'select':d.mode==='summary'?'[data-plan-action="confirm"]':'[data-plan-action="yes"]');
      target?.focus({preventScroll:true});
    }
  }
  function show(proposal,saved,callbacks) {
    mount();
    const key=`${proposal.public_state.szenario_id}:${proposal.round}`;
    if(current?.key===key&&!current.inspect&&(dialog.open||peeking)){current.callbacks=callbacks;return;}
    peeking=false;returnButton.hidden=true;current={key,proposal:copy(proposal),draft:draftFor(proposal,saved),callbacks};submitting=false;render();
    if(!dialog.open)dialog.showModal();
  }
  function close(){if(dialog?.open)dialog.close();if(returnButton)returnButton.hidden=true;current=null;submitting=false;peeking=false;}
  function inspect(entry){if(!entry?.plan)return;mount();peeking=false;returnButton.hidden=true;current={inspect:true,entry:copy(entry)};render();if(!dialog.open)dialog.showModal();}
  function outcome(entry,state){
    const start=entry.proposal.public_state;
    const sum=values=>(values||[]).reduce((n,v)=>n+Number(v),0);
    return {status:state.status,reason:state.verlust_grund||null,movement:Math.max(0,start.entfernung-state.entfernung),
      requested_movement:entry.plan?.movement_preference??null,
      tasks_completed:sum(state.fahrwerk_ausgefahren)+sum(state.landeklappen_ausgefahren)-sum(start.fahrwerk_ausgefahren)-sum(start.landeklappen_ausgefahren),
      planes_removed:Math.max(0,sum(start.flugzeuge)-sum(state.flugzeuge)),coffee_change:state.kaffeetassen-start.kaffeetassen,
      fuel_spent:start.kerosin==null?null:start.kerosin-state.kerosin,
      brakes_completed:sum(state.bremsen_aktiviert)-sum(start.bremsen_aktiviert)+(state.eis_fortschritt||0)-(start.eis_fortschritt||0),
      synchronisation:entry.synchronisation===true,attitude:state.fluglage,wind_value:state.wind_wert,
      public_after:Object.fromEntries(Object.keys(start).map(key=>[key,state[key]]))};
  }
  function result(entry,state){
    const o=outcome(entry,state),focus=entry.plan?.focus;
    const detail=focus==='tasks'?`${o.tasks_completed} Aufgaben an Fahrwerk & Klappen`:focus==='radio'?`${o.planes_removed} Flugzeuge entfernt`:focus==='coffee'?`Kaffee ${o.coffee_change>=0?'+':''}${o.coffee_change}`:focus==='fuel'?`${o.fuel_spent} Kerosin verbraucht`:'';
    return `Runde ${entry.round}: ${o.movement} ${o.movement===1?'Feld':'Felder'} weiter${entry.plan?` (Ziel ${entry.plan.movement_preference})`:''}${detail?` · ${detail}`:''}.`;
  }
  return {show,close,inspect,draftFor,plan,result,outcome};
})();
