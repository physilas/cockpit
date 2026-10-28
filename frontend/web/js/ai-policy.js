/* Inference only. Observations and masks come from the Python training adapter. */
window.CockpitPolicy = (() => {
  function floats(encoded, count) {
    const bytes = Uint8Array.from(atob(encoded), c => c.charCodeAt(0));
    if (bytes.length !== count * 4) throw new Error("Beschädigte Modellgewichte.");
    const view = new DataView(bytes.buffer);
    return Float32Array.from({length: count}, (_, i) => view.getFloat32(i * 4, true));
  }

  function create(data, catalog) {
    if (![1, 2, 3, 4].includes(data.format) || JSON.stringify(data.schema) !== JSON.stringify(catalog.schema)) {
      throw new Error("Das Modell passt nicht zur aktuellen KI-Schnittstelle.");
    }
    if (data.format === 3 || data.format === 4) {
      if (data.format === 4 && (!Number.isFinite(data.guide_margin) || data.guide_margin <= 0)) throw new Error("Ungültige Planungsvorgabe.");
      const source = create(data.source, {schema: data.source.schema});
      const residual = create(data.residual, catalog);
      const logits = (observation, referenceMask) => {
        const original = source.logits(observation.slice(0, data.source.schema.features.length));
        // Expanded checkpoints assign zero inherited logits to new actions.
        // Include those zeros when finding the guided maximum, too.
        const inherited = Array.from({length:data.schema.actions.length},(_,i)=>original[i] ?? 0);
        if (data.format === 4) {
          if (!referenceMask || referenceMask.length !== data.schema.actions.length || !referenceMask.some(Boolean)) throw new Error("Die öffentliche Planungsvorgabe fehlt.");
          const top = Math.max(...inherited.filter((_, i) => referenceMask[i]));
          return residual.logits(observation).map((v, i) => v + (referenceMask[i] ? inherited[i] || 0 : top - data.guide_margin));
        }
        return residual.logits(observation).map((v, i) => v + (inherited[i] || 0));
      };
      return {logits, select: decision => {
        const scores = logits(decision.observation, decision.reference_action_mask);
        if (scores.length !== decision.action_mask.length) throw new Error("Ungültige Aktionsmaske.");
        if (data.format === 4 && decision.reference_action_mask.some((v, i) => v && !decision.action_mask[i])) throw new Error("Die Planungsvorgabe enthält eine unerlaubte Aktion.");
        let selected = -1;
        for (let i=0; i<scores.length; i++) if (decision.action_mask[i] && (selected<0 || scores[i]>scores[selected])) selected=i;
        if (selected<0) throw new Error("Die KI hat keine erlaubte Aktion mehr.");
        return selected;
      }};
    }
    if (data.format === 2) {
      if (Object.keys(data.roles || {}).sort().join(",") !== "kopilot,pilot") throw new Error("Beide KI-Rollen werden benötigt.");
      const roles = Object.fromEntries(Object.entries(data.roles).map(([role, layers]) =>
        [role, create({format: 1, schema: data.schema, layers}, catalog)]));
      const pilotFeature = catalog.schema.features.indexOf("role.pilot");
      if (pilotFeature < 0) throw new Error("Die Rollenbeobachtung fehlt.");
      const branch = observation => roles[observation[pilotFeature] > 0.5 ? "pilot" : "kopilot"];
      return {logits: observation => branch(observation).logits(observation),
              select: decision => branch(decision.observation).select(decision)};
    }
    let width = catalog.schema.features.length;
    const layers = data.layers.map(layer => {
      if (layer.input !== width || !Number.isInteger(layer.output) || layer.output < 1) throw new Error("Ungültige Netzstruktur.");
      width = layer.output;
      return {...layer, weight: floats(layer.weight, layer.input * layer.output), bias: floats(layer.bias, layer.output)};
    });
    if (width !== catalog.schema.actions.length || !layers.length) throw new Error("Ungültige Aktionsausgabe.");

    function logits(observation) {
      if (observation.length !== layers[0].input) throw new Error("Ungültige Beobachtung.");
      let values = observation;
      layers.forEach((layer, index) => {
        const output = new Float32Array(layer.output);
        for (let row = 0; row < layer.output; row++) {
          let sum = layer.bias[row];
          const offset = row * layer.input;
          for (let col = 0; col < layer.input; col++) sum += layer.weight[offset + col] * values[col];
          output[row] = index === layers.length - 1 ? sum : Math.tanh(sum);
        }
        values = output;
      });
      return Array.from(values);
    }
    return {
      logits,
      select(decision) {
        const scores = logits(decision.observation);
        if (scores.length !== decision.action_mask.length) throw new Error("Ungültige Aktionsmaske.");
        let selected = -1;
        for (let i = 0; i < scores.length; i++) {
          if (decision.action_mask[i] && (selected < 0 || scores[i] > scores[selected])) selected = i;
        }
        if (selected < 0) throw new Error("Die KI hat keine erlaubte Aktion mehr.");
        return selected;
      },
    };
  }
  return {create(data,catalog){
    const policy=create(data,catalog);
    const networkSelect=policy.select;
    policy.select=decision=>{
      const plan=decision.public_plan;
      if (!plan) return networkSelect(decision);
      const allowed=decision.action_mask;
      if (plan.version!==1 || !Array.isArray(plan.baseline_mask) || plan.baseline_mask.length!==allowed.length
          || plan.baseline_mask.some((flag,i)=>typeof flag!=="boolean" || flag&&!allowed[i])
          || !plan.baseline_mask.some(Boolean) || !plan.scores || typeof plan.scores!=="object" || Array.isArray(plan.scores)
          || !Number.isFinite(plan.tolerance) || plan.tolerance<0) throw new Error("Ungültiger öffentlicher Handplan.");
      const legal=index=>Number.isInteger(index)&&index>=0&&index<allowed.length&&allowed[index];
      for (const [key,value] of Object.entries(plan.scores)) {
        const index=Number(key);
        if (String(index)!==key || !legal(index) || !Number.isFinite(value)) throw new Error("Ungültiger Planungswert.");
      }
      // Pyodide maps Python None to undefined; JSON fixtures use null.
      if (plan.best_action!=null && (!legal(plan.best_action) || !Object.hasOwn(plan.scores,String(plan.best_action)))) throw new Error("Ungültiges Planungsziel.");
      if (plan.forced_action!=null && !legal(plan.forced_action)) throw new Error("Unerlaubte Planungsaktion.");
      const baseline=networkSelect({...decision,action_mask:plan.baseline_mask,public_plan:undefined});
      const value=Object.hasOwn(plan.scores,String(baseline)) ? plan.scores[String(baseline)] : -Infinity;
      let selected=baseline;
      if (plan.best_action!=null && value<plan.scores[String(plan.best_action)]-plan.tolerance) selected=plan.best_action;
      if (plan.forced_action!=null) selected=plan.forced_action;
      return selected;
    };
    policy.rank=decision=>{
      const selected=policy.select(decision); // Validate the same observation/reference/mask/plan.
      const scores=policy.logits(decision.observation,decision.reference_action_mask);
      const ranked=scores.map((score,index)=>({score,index})).filter(row=>decision.action_mask[row.index])
        .sort((a,b)=>b.score-a.score||a.index-b.index).map(row=>row.index);
      return decision.public_plan ? [selected,...ranked.filter(index=>index!==selected)] : ranked;
    };
    return policy;
  }};
})();
