/* Inference only. Observations and masks come from the Python training adapter. */
window.CockpitPolicy = (() => {
  function floats(encoded, count) {
    const bytes = Uint8Array.from(atob(encoded), c => c.charCodeAt(0));
    if (bytes.length !== count * 4) throw new Error("Beschädigte Modellgewichte.");
    const view = new DataView(bytes.buffer);
    return Float32Array.from({length: count}, (_, i) => view.getFloat32(i * 4, true));
  }

  function create(data, catalog) {
    if (![1, 2, 3].includes(data.format) || JSON.stringify(data.schema) !== JSON.stringify(catalog.schema)) {
      throw new Error("Das Modell passt nicht zur aktuellen KI-Schnittstelle.");
    }
    if (data.format === 3) {
      const source = create(data.source, {schema: data.source.schema});
      const residual = create(data.residual, catalog);
      const logits = observation => {
        const inherited = source.logits(observation.slice(0, data.source.schema.features.length));
        return residual.logits(observation).map((v, i) => v + (inherited[i] || 0));
      };
      return {logits, select: decision => {
        const scores = logits(decision.observation);
        if (scores.length !== decision.action_mask.length) throw new Error("Ungültige Aktionsmaske.");
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
  return {create};
})();
