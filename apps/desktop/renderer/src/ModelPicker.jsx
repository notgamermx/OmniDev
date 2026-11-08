import React, { useEffect, useState } from "react";
import { request } from "./services/api";
export default function ModelPicker({ providers, provider, model, onProvider, onModel, onSetup, busy, form = false }) {
  const [models, setModels] = useState([]), [notice, setNotice] = useState("");
  const [generation, setGeneration] = useState(0), [editing, setEditing] = useState(false);
  const ready = providers.filter(p => p.configured).sort((a,b) => Number(a.name === "ollama") - Number(b.name === "ollama"));
  const selected = ready.find(p => p.name === provider);
  useEffect(() => {
    if (providers.length && !selected && ready.length) {
      onProvider(ready[0].name); onModel(ready[0].name === "builtin" ? "auto" : "");
    }
  }, [providers, provider]);
  useEffect(() => {
    let active = true;
    setModels([]);
    if (!selected) { setNotice("Add a provider key in Models & keys to get started."); return; }
    setNotice("Loading models…");
    request(`/models/catalog/${encodeURIComponent(provider)}`)
      .then(data => { if (active) { setModels(data.models); setNotice(data.models.length ? "" : "No models returned. Enter the provider’s model ID."); if (!model && !editing && data.models.length) onModel(data.models[0].id); } })
      .catch(error => { if (active) setNotice(provider === "ollama" ? "Start Ollama locally, or add a cloud provider key in Models & keys." : error.message); });
    return () => { active = false; };
  }, [provider, !!selected, generation]);
  const known = models.some(m => m.id === model), manual = editing || (!!model && !known);
  return <div className="model-picker">
    <label>Provider<select aria-label="Provider" name={form ? "provider" : undefined} value={selected ? provider : ""} disabled={busy || !ready.length} onChange={e => { setEditing(false); onProvider(e.target.value); onModel(e.target.value === "builtin" ? "auto" : ""); }}>
      {!selected && <option value="">Choose a configured provider</option>}
      {ready.map(p => <option key={p.name} value={p.name}>{p.name === "builtin" ? "Automatic routing" : (p.display_name || p.name)}</option>)}
    </select></label>
    <label>Model<select aria-label="Choose model" name={form && known ? "model" : undefined} value={known ? model : manual ? "__manual" : ""} disabled={busy || !selected} required={form} onChange={e => { setEditing(e.target.value === "__manual"); onModel(e.target.value === "__manual" ? "" : e.target.value); }}>
      <option value="">Choose a model</option>{models.map(m => <option key={m.id} value={m.id}>{m.name}{m.free === true ? " · free" : ""}</option>)}<option value="__manual">Enter model ID…</option>
    </select></label>
    {manual && <label>Model ID<input aria-label="Model ID" name={form ? "model" : undefined} value={model} onChange={e => onModel(e.target.value)} required={form} /></label>}
    <button type="button" disabled={busy || !selected} onClick={() => setGeneration(g => g+1)} aria-label="Refresh models">↻</button>
    {onSetup && <button type="button" onClick={onSetup}>Manage keys</button>}
    {notice && <small className="model-notice" role="status">{notice}</small>}
  </div>;
}
