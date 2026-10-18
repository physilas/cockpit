/* Inference only. Observations and masks come from the Python training adapter. */
window.CockpitPolicy = (() => {
  function floats(encoded, count) {
    const bytes = Uint8Array.from(atob(encoded), c => c.charCodeAt(0));
    if (bytes.length !== count * 4) throw new Error("Beschädigte Modellgewichte.");
    const view = new DataView(bytes.buffer);
    return Float32Array.from({length: count}, (_, i) => view.getFloat32(i * 4, true));
  }

  function create(data, catalog) {
    if (data.format !== 1 || JSON.stringify(data.schema) !== JSON.stringify(catalog.schema)) {
      throw new Error("Das Modell passt nicht zur aktuellen KI-Schnittstelle.");
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
