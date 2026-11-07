import React, { useEffect, useState } from "react";
import { request } from "./services/api";
import { downloadText } from "./services/download";
export default function Models({ act, refresh, busy }) {
  const [providers, setProviders] = useState([]),
    [selected, setSelected] = useState("groq");
  const [models, setModels] = useState([]),
    [routes, setRoutes] = useState([]),
    [chosen, setChosen] = useState("");
  const [search, setSearch] = useState(""),
    [freeOnly, setFreeOnly] = useState(true);
  async function load() {
    const [p, pool] = await Promise.all([
      request("/models/providers"),
      request("/models/pool"),
    ]);
    setProviders(p);
    setRoutes(pool.routes);
    await refresh();
  }
  useEffect(() => {
    act(load);
  }, []);
  const current = providers.find((p) => p.id === selected);
  async function discover() {
    setModels((await request(`/models/catalog/${selected}`)).models);
  }
  async function savePool(next) {
    await request("/models/pool", "PUT", { routes: next });
    setRoutes(next);
    await refresh();
  }
  return (
    <div className="settings-page">
      <span className="eyebrow">BUILT INTO OMNIDEV</span>
      <h2>Your models. One built-in router.</h2>
      <p>
        Set up providers here, browse their live models, and choose your
        fallback order. Cloud providers still require your own keys and their
        quotas apply. Free-tier availability depends on your account.
      </p>
      <div className="toolbar">
        <button type="button" disabled={busy || !models.length} onClick={() => act(() => downloadText(`omnidev-${selected}-catalog.json`, JSON.stringify(models, null, 2), "application/json"))}>↓ Download model catalog</button>
        <button type="button" disabled={busy || !routes.length} onClick={() => act(() => downloadText("omnidev-model-pool.json", JSON.stringify({ routes }, null, 2), "application/json"))}>↓ Download router configuration</button>
      </div>
      <div className="split connector-forms">
        <div>
          <h3>1. Set up a provider</h3>
          <label>
            Provider
            <select
              aria-label="Set up provider"
              value={selected}
              onChange={(e) => {
                setSelected(e.target.value);
                setModels([]);
                setChosen("");
              }}
            >
              {providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                  {p.configured ? " · ready" : ""}
                </option>
              ))}
            </select>
          </label>
          {current && (
            <>
              <p>
                <span className="badge">
                  {current.tier.replaceAll("_", " ")}
                </span>
                {current.configured
                  ? "Provider configured"
                  : "Provider setup needed"}{" "}
                ·{" "}
                <a href={current.signup_url} target="_blank" rel="noreferrer">
                  Provider website ↗
                </a>
              </p>
              <form
                className="form"
                key={selected}
                onSubmit={(e) => {
                  e.preventDefault();
                  const el = e.currentTarget;
                  const f = new FormData(el);
                  act(async () => {
                    await request(`/models/providers/${selected}`, "PUT", {
                      api_key: f.get("key") || "",
                      account_id: f.get("account") || "",
                    });
                    el.reset();
                    await load();
                  });
                }}
              >
                <label>
                  API key
                  <input
                    aria-label="Provider API key"
                    name="key"
                    type="password"
                    autoComplete="off"
                    placeholder="Blank keeps a saved key"
                  />
                </label>
                {current.account_id_required && (
                  <label>
                    Account ID
                    <input name="account" required />
                  </label>
                )}
                <div className="toolbar">
                  <button disabled={busy}>Save provider</button>
                  <button
                    disabled={busy}
                    type="button"
                    onClick={() =>
                      act(async () => {
                        await request(
                          `/models/providers/${selected}`,
                          "DELETE",
                        );
                        await load();
                      })
                    }
                  >
                    Remove saved key
                  </button>
                </div>
              </form>
            </>
          )}
          <h3>2. Choose models</h3>
          <button disabled={busy} onClick={() => act(discover)}>
            Load available models
          </button>
          <label>
            Filter models
            <input
              aria-label="Filter models"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
          {selected === "openrouter" && (
            <label>
              <input
                type="checkbox"
                checked={freeOnly}
                onChange={(e) => setFreeOnly(e.target.checked)}
              />{" "}
              Show models listed with free input and output
            </label>
          )}
          <select
            aria-label="Available models"
            size="7"
            value={chosen}
            onChange={(e) => setChosen(e.target.value)}
          >
            <option value="" disabled>
              Select a model
            </option>
            {models
              .filter(
                (m) =>
                  m.id.toLowerCase().includes(search.toLowerCase()) &&
                  (selected !== "openrouter" || !freeOnly || m.free === true),
              )
              .map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} ({m.id}){m.free === true ? " · free" : ""}
                </option>
              ))}
          </select>
          <label>
            Selected model ID
            <input
              aria-label="Selected model ID"
              value={chosen}
              onChange={(e) => setChosen(e.target.value)}
              placeholder="Select above or enter the provider's model ID"
            />
          </label>
          <button
            disabled={
              busy ||
              !chosen.trim() ||
              routes.some(
                (r) => r.provider === selected && r.model === chosen.trim(),
              )
            }
            onClick={() =>
              act(() =>
                savePool([
                  ...routes,
                  { provider: selected, model: chosen.trim(), enabled: true },
                ]),
              )
            }
          >
            Add to built-in router
          </button>
        </div>
        <div>
          <h3>3. Set your fallback order</h3>
          <p className="muted">
            Choose “OmniDev · built-in router” and “Automatic” in Chat or
            Agents. OmniDev tries these models in order, skips models cooling
            down after errors, and falls back before a streamed response starts.
          </p>
          {!routes.length && (
            <p>
              No models added yet. Set up a provider and add a model to get
              started.
            </p>
          )}
          {routes.map((r, i) => (
            <article key={r.provider + ":" + r.model}>
              <h3>
                {i + 1}. {r.model}
              </h3>
              <small>{r.provider}</small>
              <div className="toolbar">
                <label>
                  <input
                    type="checkbox"
                    checked={r.enabled}
                    onChange={(e) =>
                      act(() =>
                        savePool(
                          routes.map((v, n) =>
                            n === i ? { ...v, enabled: e.target.checked } : v,
                          ),
                        ),
                      )
                    }
                  />{" "}
                  Enabled
                </label>
                <button
                  disabled={busy || !i}
                  onClick={() =>
                    act(() => {
                      const next = [...routes];
                      [next[i - 1], next[i]] = [next[i], next[i - 1]];
                      return savePool(next);
                    })
                  }
                >
                  Move up
                </button>
                <button
                  disabled={busy}
                  onClick={() =>
                    act(() => savePool(routes.filter((_, n) => n !== i)))
                  }
                >
                  Remove
                </button>
              </div>
            </article>
          ))}
          <p className="muted">
            Keys are encrypted in the engine home. A key from your .env remains
            available if you remove a saved key. No gateway server is needed.
          </p>
        </div>
      </div>
    </div>
  );
}
