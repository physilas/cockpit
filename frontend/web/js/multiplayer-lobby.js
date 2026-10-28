/* Host/guest are connection roles; pilot/copilot are selected flight roles. */
window.MultiplayerLobby = (() => {
  const other=role=>role==='pilot'?'kopilot':role==='kopilot'?'pilot':null;
  const create=()=>({version:2,revision:0,route:null,cards:[],hostRole:null,guestRole:null,hostReady:false,guestReady:false,started:false});
  function route(state,id,cards){return {...create(),revision:state.revision+1,route:id,cards:[...cards]};}
  function role(state,who,value){
    if(!state.route||!['host','guest'].includes(who)||!other(value))throw Error('Ungültige Rollenauswahl');
    return {...state,revision:state.revision+1,hostRole:who==='host'?value:other(value),guestRole:who==='guest'?value:other(value),hostReady:false,guestReady:false};
  }
  function ready(state,who,value,revision){
    if(revision!==state.revision||!['host','guest'].includes(who)||typeof value!=='boolean'||!state.hostRole||!state.guestRole)throw Error('Bitte die aktuelle Auswahl bestätigen.');
    return {...state,[`${who}Ready`]:value};
  }
  const canStart=state=>Boolean(state.route&&other(state.hostRole)===state.guestRole&&state.hostReady&&state.guestReady&&!state.started);
  return {other,create,route,role,ready,canStart};
})();
