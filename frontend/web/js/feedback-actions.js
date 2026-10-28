/* Equivalent decisions: moving the same die to another coffee/radio slot is no new idea. */
window.FeedbackActions = (() => {
  function face(action,schema,observation) {
    if(action.die>=0){const start=schema.features.indexOf(`die.${action.die}.0`);if(start>=0)return observation.slice(start,start+7).indexOf(Math.max(...observation.slice(start,start+7)));}
    const pending=schema.features.indexOf('pending.value');
    return pending>=0?Math.round(observation[pending]*6):null;
  }
  function signature(action,schema,observation) {
    if(['place','bonus_place'].includes(action.kind)){
      const slot=schema.slots[action.slot];
      return JSON.stringify([action.kind,slot.target,slot.owner, ['konzentration','funk'].includes(slot.target)?null:slot.index,face(action,schema,observation)]);
    }
    if(['coffee','bonus_coffee'].includes(action.kind))return JSON.stringify([action.kind,face(action,schema,observation),action.delta]);
    if(['adaptation','anticipation','swap_choose'].includes(action.kind))return JSON.stringify([action.kind,face(action,schema,observation)]);
    return JSON.stringify([action.kind,action.die,action.slot,action.delta,action.subset]);
  }
  function alternatives(order,originalId,schema,observation,mask) {
    const original=schema.actions[originalId],key=signature(original,schema,observation);
    const different=order.filter(id=>mask[id]&&signature(schema.actions[id],schema,observation)!==key);
    const target=action=>['place','bonus_place'].includes(action.kind)?schema.slots[action.slot].target:action.kind;
    const placements=different.filter(id=>['place','bonus_place'].includes(schema.actions[id].kind)&&target(schema.actions[id])!==target(original));
    return [...placements,...different.filter(id=>!placements.includes(id)&&target(schema.actions[id])!==target(original)),...different.filter(id=>target(schema.actions[id])===target(original))];
  }
  return {face,signature,alternatives};
})();
