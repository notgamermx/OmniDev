import React, { useEffect, useState } from "react";
import { request } from "./services/api";
import { downloadText } from "./services/download";

export default function Connectors({ act, refresh, busy, ask }) {
  const [data, setData] = useState({ providers: [], harnesses: [] });
  const [models, setModels] = useState([]),
    [output, setOutput] = useState("");
  async function load() {
    setData(await request("/connectors"));
    await refresh();
  }
  useEffect(() => {
    act(load);
  }, []);
  function save(kind, event) {
    event.preventDefault();
    const element = event.currentTarget;
    const form = new FormData(element);
    act(async () => {
      const value =
        kind === "providers"
          ? {
              name: form.get("name"),
              base_url: form.get("base_url"),
              api_key: form.get("api_key"),
              model: form.get("model"),
            }
          : {
              name: form.get("name"),
              command: form.get("command"),
              args: JSON.parse(form.get("args")),
              install_command: JSON.parse(form.get("install_command") || "[]"),
            };
      await request(`/connectors/${kind}/${form.get("id")}`, "PUT", value);
      await load();
      if (kind === "providers") element.elements.api_key.value = "";
    });
  }
  return (
    <div className="settings-page">
      <div className="page-intro">
        <span className="eyebrow">YOUR TOOLS, CONNECTED</span>
        <h2>One workspace. Your choice of engine.</h2>
        <p>Connect a model gateway or bring an external coding harness.</p>
      </div>
      <div className="split connector-forms">
        <div>
          <h3>Model connection</h3>
          <p className="muted">
            Built-in provider setup and automatic routing are in Models. This
            optional connection supports an existing compatible server.
          </p>
          <form className="form" onSubmit={(e) => save("providers", e)}>
            <label>
              ID
              <input
                name="id"
                required
                pattern="custom_[a-z0-9_-]+"
                defaultValue="custom_local"
              />
            </label>
            <label>
              Display name
              <input name="name" required defaultValue="My model server" />
            </label>
            <label>
              API base URL
              <input
                name="base_url"
                type="url"
                required
                defaultValue="http://127.0.0.1:1234/v1"
              />
            </label>
            <label>
              API key
              <input
                name="api_key"
                type="password"
                autoComplete="off"
                placeholder="Optional · blank preserves saved key"
              />
            </label>
            <label>
              Default model
              <input name="model" required defaultValue="auto" />
            </label>
            <button disabled={busy} className="primary">
              Save connection
            </button>
          </form>
        </div>
        <div>
          <h3>Harness connector</h3>
          <p className="muted">
            Use a noninteractive command from your chosen harness. Each argument
            is a JSON array item; include {"{prompt}"} where the task goes. Runs
            in the selected workspace folder.
          </p>
          <form className="form" onSubmit={(e) => save("harnesses", e)}>
            <label>
              ID
              <input
                name="id"
                required
                pattern="[a-z][a-z0-9_-]*"
                placeholder="my-harness"
              />
            </label>
            <label>
              Display name
              <input name="name" required placeholder="My coding harness" />
            </label>
            <label>
              Executable
              <input
                name="command"
                required
                placeholder="Executable path or command on PATH"
              />
            </label>
            <label>
              Arguments (JSON array)
              <input name="args" required defaultValue={'["{prompt}"]'} />
            </label>
            <label>
              Optional install command (JSON array)
              <textarea
                name="install_command"
                defaultValue="[]"
                placeholder={'["npm", "install", "--global", "your-package"]'}
              />
            </label>
            <p className="muted">
              Install and Run execute with your OS account permissions. Only
              save commands you trust. Interactive login stays in your own
              terminal. On Windows, use a native .exe or node/python entrypoint
              for prompts containing shell symbols.
            </p>
            <button disabled={busy} className="primary">
              Save harness
            </button>
          </form>
        </div>
      </div>
      <h3>Saved connections</h3>
      <div className="cards">
        {data.providers.map((p) => (
          <article key={p.id}>
            <span className="badge">MODEL GATEWAY</span>
            <h3>{p.name}</h3>
            <p>{p.base_url}</p>
            <small>
              {p.id} · {p.has_api_key ? "Key saved" : "No key"}
            </small>
            <div className="toolbar">
              <button
                disabled={busy}
                onClick={() =>
                  act(async () =>
                    setModels(
                      (await request(`/connectors/providers/${p.id}/models`))
                        .models,
                    ),
                  )
                }
              >
                Discover models
              </button>
              <button
                disabled={busy}
                onClick={() =>
                  act(async () => {
                    await request(`/connectors/providers/${p.id}`, "DELETE");
                    await load();
                  })
                }
              >
                Remove
              </button>
            </div>
          </article>
        ))}
        {data.harnesses.map((h) => (
          <article key={h.id}>
            <span className="badge">COMMAND HARNESS</span>
            <h3>{h.name}</h3>
            <code>{h.command}</code>
            <p>Privileged host operation · approval required for every install or run.</p>
            <div className="toolbar">
              {!!h.install_command.length && (
                <button
                  disabled={busy}
                  onClick={async () => {
                    if (!await ask("Approve host installation", null, `Install ${h.name} on your computer?\n\nCommand: ${JSON.stringify(h.install_command)}\n\nThis runs with your OS account permissions and network access, outside Docker. It can change files outside the workspace. Approve only a command you trust.`)) return;
                    act(async () =>
                      setOutput(
                        JSON.stringify(
                          await request(
                            `/connectors/harnesses/${h.id}/install`,
                            "POST",
                            { approve_host_execution: true },
                          ),
                          null,
                          2,
                        ),
                      ),
                    );
                  }}
                >
                  Install
                </button>
              )}
              <button
                disabled={busy}
                onClick={() =>
                  act(async () => {
                    await request(`/connectors/harnesses/${h.id}`, "DELETE");
                    await load();
                  })
                }
              >
                Remove
              </button>
            </div>
            <form
              className="form"
              onSubmit={async (e) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                const argv = [h.command, ...h.args.map(arg => arg.replaceAll("{prompt}", f.get("prompt")))];
                if (!await ask("Approve host execution", null, `Run ${h.name} on your computer?\n\nCommand: ${JSON.stringify(argv)}\nFolder: ${f.get("path")}\n\nThis runs with your OS account permissions and network access, outside Docker. It can read or change files outside the workspace. Approve only a harness you trust.`)) return;
                act(async () =>
                  setOutput(
                    JSON.stringify(
                      await request(
                        `/connectors/harnesses/${h.id}/run`,
                        "POST",
                        { prompt: f.get("prompt"), path: f.get("path"), approve_host_execution: true },
                      ),
                      null,
                      2,
                    ),
                  ),
                );
              }}
            >
              <label>
                Workspace folder
                <input name="path" defaultValue="." required />
              </label>
              <label>
                Task
                <textarea
                  name="prompt"
                  required
                  placeholder="Describe what this harness should do…"
                />
              </label>
              <button disabled={busy}>Run harness</button>
            </form>
          </article>
        ))}
      </div>
      {!!models.length && (
        <article>
          <h3>Available models</h3>
          <button disabled={busy} onClick={() => act(() => downloadText("omnidev-connector-models.txt", models.join("\n")))}>↓ Download model list</button>
          <pre>{models.join("\n")}</pre>
        </article>
      )}
      {output && (
        <article>
          <h3>Harness result</h3>
          <button disabled={busy} onClick={() => act(() => downloadText("omnidev-harness-result.json", output, "application/json"))}>↓ Download result</button>
          <pre>{output}</pre>
        </article>
      )}
    </div>
  );
}
