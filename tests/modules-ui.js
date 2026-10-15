/* Real DOM regressions for integrated controls: placement, privacy, geometry
 * and clean scenario changes. The board markup is taken from both real pages. */
document.getElementById('run-tests').addEventListener('click', async event => {
  event.target.disabled = true;
  const output = document.getElementById('test-results'), fixture = document.getElementById('fixture');
  const lines = []; let count = 0, actions = [], selected = {besitzer:'pilot',index:0};
  const assert = (value, text) => {if (!value) throw new Error(text);};
  const test = (label, fn) => {fn(); count++; lines.push(`✓ ${label}`); output.textContent = lines.join('\n');};
  const options = {role:null, selected, reroll:false, onAction:(...args) => actions.push(args), onPlace:(...args) => actions.push(args), conceal() {options.selected = null; FlightModules.render(state,options);}};
  const base = {
    szenario_id:'fixture', runde:1, status:'laeuft', phase:'platzieren', am_zug:'pilot',
    module:['kerosene','wind','ice','intern','realtime'], faehigkeitskarten:['control','adaptation'],
    kerosin:20, wind_position:0, wind_wert:3, wind_ring:[3,3,2,2,1,0,-1,-2,-3,-3,-3,-2,-1,0,1,2,2,3],
    eis_fortschritt:0, praktikant:[3,6,1,5,4,2], bremsstaerke:1.5,
    felder:{kerosin:[null],eisbremse:Array(8).fill(null),training:{pilot:null,kopilot:null}},
    pilot_wuerfel:[4,2,3,5], kopilot_wuerfel:[1,6,2,4], pilot_wuerfel_frei:[true,true,true,true], kopilot_wuerfel_frei:[true,true,true,true],
    anpassung_verfuegbar:{pilot:true,kopilot:true}, voraussicht_verfuegbar:true, kooperation_verfuegbar:true,
    timer_deadline_ms:null, server_time_ms:1000, geschwindigkeit:null,
  };
  let state;
  const render = patch => {
    state = {...structuredClone(base),...patch}; options.selected = selected;
    document.getElementById('schub-reihe').innerHTML = '<div class="feld-zelle"></div><span class="inline-label">Schub</span><div class="feld-zelle"></div>';
    const identify = (selector, entry, owner = null) => document.querySelectorAll(selector).forEach((el,i) => FlightModules.identifyField(el,entry,i,owner));
    for (const role of ['pilot','kopilot']) {
      document.getElementById(`ruder-slot-${role}`).innerHTML = '<div class="feld-zelle"></div>';
      identify(`#ruder-slot-${role} .feld-zelle`,{ziel:'ruder',zugriff:['pilot','kopilot']},role);
    }
    identify('#schub-reihe .feld-zelle:first-child',{ziel:'triebwerk',zugriff:['pilot','kopilot']},'pilot');
    identify('#schub-reihe .feld-zelle:last-child',{ziel:'triebwerk',zugriff:['pilot','kopilot']},'kopilot');
    identify('#col-pilot-felder .feld-zelle',{ziel:'fahrwerk',zugriff:['pilot']});
    identify('#col-kopilot-felder .feld-zelle',{ziel:'landeklappe',zugriff:['kopilot']});
    for (const role of ['pilot','kopilot']) identify(`#fixture-funk-${role} .feld-zelle`,{ziel:'funk',zugriff:[role],funk_feld_basis:0});
    document.getElementById('konzentration-reihe').innerHTML = '<div class="feld-zelle"></div>'.repeat(3);
    identify('#konzentration-reihe .feld-zelle',{ziel:'konzentration',zugriff:['pilot','kopilot']});
    FlightModules.renderBrakes(state.bremsstaerke); FlightModules.render(state,options);
  };
  const rect = el => el.getBoundingClientRect();
  const overlap = (a,b) => Math.min(a.right,b.right)-Math.max(a.left,b.left)>1 && Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1;
  try {
    for (const page of ['index.html','multiplayer.html']) {
      const html = await (await fetch(`../frontend/web/${page}`)).text();
      const doc = new DOMParser().parseFromString(html,'text/html');
      fixture.replaceChildren(document.importNode(doc.querySelector('header'),true),document.importNode(doc.getElementById('spiel-ui'),true));
      fixture.querySelector('header').classList.remove('versteckt');
      document.getElementById('spiel-ui').classList.remove('versteckt');
      document.getElementById('col-pilot-felder').innerHTML = '<div class="feld-zeile"><span class="feld-label">Fahrw.</span><div class="feld-zelle">1/2</div><div class="feld-zelle">3/4</div><div class="feld-zelle">5/6</div></div>';
      document.getElementById('col-kopilot-felder').innerHTML = '<div class="feld-zeile"><span class="feld-label">Klappen</span><div class="feld-zelle">1/2</div><div class="feld-zelle">2/3</div><div class="feld-zelle">4/5</div><div class="feld-zelle">5/6</div></div>';
      for (const role of ['pilot','kopilot']) document.getElementById(`col-${role}`).insertAdjacentHTML('beforeend', `<div id="fixture-funk-${role}"><div class="feld-zelle"></div>${role === 'kopilot' ? '<div class="feld-zelle"></div>' : ''}</div>`);
      render({});
      Landings.updateFlight({...state,szenario_id:'KEF-black'});
      test(`${page}: compact header includes accessible flight context`, () => {
        const summary=document.getElementById('flight-summary');
        assert(summary.closest('header'),'Flight info remains outside header');
        assert(summary.textContent.includes('KEF') && summary.textContent.includes('Heroisch'),'Flight context absent');
        assert(summary.getAttribute('aria-label').includes('Wind'),'Full accessible info absent');
        assert(rect(fixture.querySelector('header')).height<=43,'Header not reduced by 10%');
      });
      test(`${page}: native mount points, eight ice fields, no duplicate panels`, () => {
        assert(document.getElementById('fuel-action').closest('.board-grid'),'Fuel field outside cockpit');
        assert(document.getElementById('ice-brakes').closest('.center-col'),'Ice outside brake area');
        assert(document.getElementById('ice-brakes').querySelectorAll('button.feld-zelle').length===8,'Ice pair missing');
        assert(document.getElementById('flight-modules').classList.contains('versteckt'),'Idle module panel remains');
        assert(document.getElementById('bremse-reihe').classList.contains('versteckt'),'Normal brakes still visible');
      });
      test(`${page}: fuel, ice and training keep placement arguments and role restrictions`, () => {
        actions=[];
        document.querySelector('#fuel-action .feld-zelle').click();
        document.querySelector('#ice-brakes .ice-pair .feld-zelle').click();
        document.querySelector('.intern-end.pilot button').click();
        assert(JSON.stringify(actions)===JSON.stringify([['pilot',0,'kerosin',null],['pilot',0,'eisbremse',0],['pilot',0,'training',null]]),'Wrong placement dispatch');
        selected={besitzer:'kopilot',index:1}; render({am_zug:'kopilot'});
        assert(document.querySelector('#ice-brakes .ice-pair button:first-child').disabled,'Co-pilot can fill pilot ice slot');
        assert(!document.querySelector('#ice-brakes .ice-pair button:nth-child(2)').disabled,'Shared ice slot blocked');
        assert(document.querySelector('.intern-end.pilot button').disabled,'Other role can train');
      });
      test(`${page}: no action while rerolling or preparing`, () => {
        options.reroll=true; render({});
        assert(document.querySelector('#fuel-action button').disabled,'Fuel during reroll');
        options.reroll=false; render({phase:'vorbereitung'});
        assert(document.querySelector('#fuel-action button').disabled,'Fuel during preparation');
        assert(document.querySelector('#realtime-instrument .timer-start'),'Missing timer start');
      });
      test(`${page}: every brake threshold stays between numbers`, () => {
        for (const strength of [0,2,4,6,1.5,2.5,3.5,4.5,5.5]) {
          FlightModules.renderBrakes(strength);
          const marker=document.querySelector('.brems-marker'); marker.style.transition='none';
          const m=rect(marker);
          document.querySelectorAll('.brems-number').forEach(n => {
            const r=rect(n), center=(r.left+r.right)/2;
            assert(Math.abs((m.left+m.right)/2-center)>r.width*.35,`Marker covers ${n.textContent} at ${strength}`);
          });
        }
      });
      selected={besitzer:'pilot',index:0}; render({});
      for (const width of [320,390,600]) {
        fixture.style.width=`${width}px`;
        test(`${page}: instruments fit a ${width}px board`, () => {
          const board=rect(document.querySelector('.board-grid')), wind=rect(document.querySelector('.wind-mini'));
          const engine=rect(document.querySelector('#schub-reihe .feld-zelle:last-child'));
          const fuel=rect(document.getElementById('fuel-gauge'));
          assert(!overlap(wind,engine),'Wind overlaps engine');
          assert(wind.right < fuel.left,'Wind overlaps right rail');
          assert(fuel.right <= board.right,'Fuel gauge outside board');
          document.querySelectorAll('#ice-brakes .feld-zelle,.intern-token,.intern-end button').forEach(el => {
            const r=rect(el); assert(r.left>=board.left && r.right<=board.right, 'Module slot outside board');
          });
        });
      }
      test(`${page}: leak replaces fuel action; inactive modules leave base cockpit clean`, () => {
        render({module:['leak']});
        assert(!document.querySelector('#fuel-action .feld-zelle'),'Leak still has fuel die slot');
        assert(document.querySelector('#fuel-action .leak-indicator'),'Leak indicator absent');
        render({module:[],kerosin:null,faehigkeitskarten:[]});
        for(const id of ['fuel-gauge','fuel-action','wind-instrument','ice-brakes','intern-strip','ability-strip','realtime-instrument']) assert(document.getElementById(id).classList.contains('versteckt'),`${id} not hidden`);
        assert(!document.querySelector('.board-grid').classList.contains('has-fuel'),'Fuel padding retained');
        assert(!document.getElementById('bremse-reihe').classList.contains('versteckt'),'Normal brakes absent');
      });
      const target = (ziel, index, ziel_besitzer, funk_feld = 0) => ({ziel,index,ziel_besitzer,funk_feld,label:`${ziel} ${index ?? funk_feld} · ${ziel_besitzer}`});
      const pending = (ziele, quelle = 'intern', rolle = 'kopilot') => ({rolle,quelle,wert:3,ziele,kaffee_deltas:[]});
      test(`${page}: intern taps the physical field with the correct colour and radio index`, () => {
        const radio = target('funk',null,'kopilot',1), rudder = target('ruder',null,'kopilot');
        options.role='kopilot'; actions=[];
        render({zusatzaktion:pending([radio,rudder])});
        assert(document.querySelectorAll('.bonus-target').length===2,'Incorrect legal destinations highlighted');
        assert(!document.querySelector('#ruder-slot-pilot .bonus-target'),'Wrong-colour rudder enabled');
        assert(!document.querySelector('#konzentration-reihe .bonus-target'),'Intern can make coffee');
        assert(document.getElementById('flight-modules').classList.contains('versteckt'),'Word-list panel remains');
        const button=document.querySelector('#fixture-funk-kopilot .feld-zelle:nth-child(2)');
        assert(button.getAttribute('role')==='button' && button.tabIndex===0,'Field not keyboard-accessible');
        button.click();
        assert(JSON.stringify(actions)===JSON.stringify([['kopilot','zusatz_platzieren',radio]]),'Radio field dispatch lost index or colour');
      });
      test(`${page}: native bonus fields and keyboard dispatch exactly one bonus action`, () => {
        const fuel=target('kerosin',null,'kopilot'), ice=target('eisbremse',1,'kopilot');
        actions=[]; render({zusatzaktion:pending([fuel,ice])});
        document.querySelector('#fuel-action .bonus-target').click();
        assert(JSON.stringify(actions)===JSON.stringify([['kopilot','zusatz_platzieren',fuel]]),'Fuel also dispatches a normal placement');
        render({zusatzaktion:pending([fuel,ice])});
        actions=[];
        document.querySelector('#ice-brakes .bonus-target').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));
        assert(JSON.stringify(actions)===JSON.stringify([['kopilot','zusatz_platzieren',ice]]),'Keyboard dispatches wrong or repeated action');
        const pilotRudder=target('ruder',null,'pilot');
        render({zusatzaktion:pending([pilotRudder],'synchronisation')}); actions=[];
        document.querySelector('#ruder-slot-pilot .bonus-target').click();
        assert(JSON.stringify(actions)===JSON.stringify([['kopilot','zusatz_platzieren',pilotRudder]]),'Co-pilot cannot place synchronisation on pilot field');
      });
      test(`${page}: waiting roles and completed actions cannot place a stale bonus`, () => {
        const fuel=target('kerosin',null,'kopilot'), p=pending([fuel]);
        options.role='pilot'; actions=[]; render({zusatzaktion:p});
        assert(!document.querySelector('.bonus-target'),'Waiting role can place partner token');
        document.querySelector('#fuel-action .feld-zelle').click();
        assert(actions.length===0,'Waiting role dispatched an action');
        assert(document.querySelector('.intern-placement-hint').textContent.includes('Co-Pilot platziert'),'Waiting status absent');
        options.role='kopilot'; render({zusatzaktion:p});
        const oldField=document.querySelector('#fuel-action .bonus-target');
        render({}); oldField.click();
        assert(actions.length===0 && !document.querySelector('.bonus-target'),'Stale highlight still places a token');
        assert(!document.querySelector('.intern-placement-hint'),'Pending hint remains after placement');
        options.role=null;
      });
      FlightModules.reset();
    }
    fixture.style.width=''; render({});
    test('Wind opens all 18 positions in a dismissible detail window', () => {
      document.querySelector('.wind-mini').click();
      assert(document.querySelector('#module-detail[open]'),'Wind window closed');
      assert(document.querySelectorAll('#module-detail .wind-tick').length===18,'Wind positions missing');
      document.querySelector('.module-close').click();
      assert(!document.querySelector('#module-detail[open]'),'Wind close failed');
    });
    // Closing a dialog dispatches its close event in the next task.
    await new Promise(resolve => setTimeout(resolve,0));
    test('Ability actions conceal free dice until the requested role reveals them', () => {
      document.querySelectorAll('.ability-chip')[1].click();
      const actionsBefore=actions.length;
      [...document.querySelectorAll('#module-detail .module-button')].find(b=>b.textContent.startsWith('Pilotin')).click();
      assert(document.getElementById('flight-modules').textContent.includes('Würfel anzeigen'),'Private handoff absent');
      assert(!document.getElementById('flight-modules').textContent.includes('1: 4'),'Private value exposed early');
      assert(actions.length===actionsBefore,'Ability used before die selection');
    });
    test('Pending partner choices stay private on the other device', () => {
      options.role='kopilot'; render({kooperation:{wartet_auf:'pilot'}});
      assert(document.getElementById('flight-modules').textContent.includes('Warte auf Pilotin'),'Missing partner waiting message');
      assert(!document.getElementById('flight-modules').querySelector('button'),'Other role can reveal dice');
    });
    const bonusTarget = {ziel:'ruder',index:null,ziel_besitzer:'pilot',funk_feld:0,label:'Ruder · Pilotin'};
    const unrolled = {rolle:'kopilot',quelle:'synchronisation',wert:null,geworfen:false,ziele:[],kaffee_deltas:[]};
    options.role='pilot'; render({zusatzaktion:unrolled});
    test('Synchronisation opens a black die popup and waits for the designated other player', () => {
      assert(document.querySelector('#sync-dialog[open]'),'Roll popup absent');
      assert(document.querySelector('#sync-dialog .traffic-roll-die').textContent==='?','Die rolled automatically');
      assert(document.querySelector('.sync-roll-button').disabled,'Wrong role can roll');
      assert(!document.querySelector('.bonus-target'),'Can place before rolling');
    });
    options.role='kopilot'; actions=[];
    const onAction=options.onAction;
    options.onAction=(...args) => {
      actions.push(args);
      if (args[1]==='synchronisation_wuerfeln') render({zusatzaktion:{...unrolled,wert:4,geworfen:true,ziele:[bonusTarget]}});
    };
    render({zusatzaktion:unrolled});
    document.querySelector('.sync-roll-button').click();
    document.querySelector('.sync-roll-button').click();
    await new Promise(resolve => setTimeout(resolve,500));
    test('One manual roll animates, dispatches once and shows the host result', () => {
      assert(actions.length===1 && actions[0][0]==='kopilot' && actions[0][1]==='synchronisation_wuerfeln','Roll duplicated or wrong owner');
      assert(document.querySelector('#sync-dialog .traffic-roll-die').textContent==='4','Rolled value absent');
      assert(document.querySelector('.sync-roll-button').textContent==='Im Cockpit platzieren','Placement transition absent');
    });
    test('The result closes into direct board placement with the same pending die', () => {
      document.querySelector('.sync-roll-button').click();
      assert(!document.querySelector('#sync-dialog[open]'),'Roll popup still blocks board');
      document.querySelector('#ruder-slot-pilot .bonus-target').click();
      assert(actions.length===2 && actions[1][1]==='zusatz_platzieren' && actions[1][2]===bonusTarget,'Board placement lost the bonus target');
      render({});
      assert(!document.querySelector('#sync-dialog[open]'),'Popup reappears after completion');
    });
    options.onAction=onAction; options.role=null;
    lines.push(`\n${count} Prüfungen bestanden.`); output.textContent=lines.join('\n');
  } catch(e) {lines.push(`✗ ${e.message}`); output.textContent=lines.join('\n'); console.error(e);}
  finally {FlightModules.reset(); event.target.disabled=false;}
});
