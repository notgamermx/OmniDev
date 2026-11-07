import React, { useEffect, useState } from "react";
import { request } from "./services/api";
export default function ModelPicker({
  providers,
  provider,
  model,
  onProvider,
  onModel,
  busy,
  form = false,
}) {
  const [models, setModels] = useState([]),
    [notice, setNotice] = useState("");
  const [generation, setGeneration] = useState(0);
  useEffect(() => {
    let active = true;
    setModels([]);
    setNotice("Loading models…");
    request(`/models/catalog/${encodeURIComponent(provider)}`)
      .then((data) => {
        if (active) {
          setModels(data.models);
          setNotice(
            data.models.length
              ? ""
              : "No models returned. Enter a model ID manually.",
          );
        }
      })
      .catch((error) => {
        if (active) setNotice(error.message);
      });
    return () => {
      active = false;
    };
  }, [provider, generation]);
  const known = models.some((m) => m.id === model);
  const manual = model !== "" && !known;
  return (
    <div className="model-picker">
      <label>
        Provider
        <select
          aria-label="Provider"
          name={form ? "provider" : undefined}
          value={provider}
          disabled={busy}
          onChange={(e) => {
            onProvider(e.target.value);
            onModel(e.target.value === "builtin" ? "auto" : "");
          }}
        >
          {providers.map((p) => (
            <option key={p.name} value={p.name}>
              {p.display_name || p.name}
              {p.configured ? "" : " · setup needed"}
            </option>
          ))}
        </select>
      </label>
      <label>
        Model
        <select
          aria-label="Choose model"
          name={form && known ? "model" : undefined}
          value={known ? model : manual ? "__manual" : ""}
          disabled={busy}
          onChange={(e) =>
            onModel(
              e.target.value === "__manual"
                ? "custom-model-id"
                : e.target.value,
            )
          }
          required={form}
        >
          <option value="">Choose a model</option>
          {models.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
              {m.free === true ? " · free" : ""}
            </option>
          ))}
          <option value="__manual">Enter model ID…</option>
        </select>
      </label>
      {manual && (
        <label>
          Model ID
          <input
            aria-label="Model ID"
            name={form ? "model" : undefined}
            value={model}
            onChange={(e) => onModel(e.target.value)}
            required={form}
          />
        </label>
      )}
      <button
        type="button"
        disabled={busy}
        onClick={() => setGeneration(generation + 1)}
      >
        ↻ Models
      </button>
      {notice && <small className="model-notice">{notice}</small>}
    </div>
  );
}
