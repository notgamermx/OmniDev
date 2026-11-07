import React, { useEffect, useState } from "react";
import { request, streamChat, connection } from "./services/api";
import Connectors from "./Connectors";
import Models from "./Models";
import ModelPicker from "./ModelPicker";
import { desktopConnection } from "./services/desktop";
import Personalization, { loadAppearance } from "./Personalization";
const icons = {
  Chat: "✧",
  Agents: "♧",
  Tasks: "☷",
  Files: "▱",
  Terminal: "⌘",
  Memory: "◷",
  Connectors: "⌁",
  Models: "✺",
  Connection: "⊙",
  Settings: "⚙",
};
const views = [
  "Chat",
  "Agents",
  "Tasks",
  "Files",
  "Terminal",
  "Memory",
  "Models",
  "Connectors",
  "Connection",
  "Settings",
];
export default function App() {
  const [appearance, setAppearance] = useState(loadAppearance);
  const [threadSearch, setThreadSearch] = useState("");
  const [attachment, setAttachment] = useState(null);
  useEffect(() => {
    localStorage.setItem("omnidev-appearance", JSON.stringify(appearance));
    const element = document.documentElement;
    for (const [key, value] of Object.entries(appearance))
      element.dataset[key] = value;
  }, [appearance]);
  const [dialog, setDialog] = useState(null);
  function ask(title, value = "") {
    return new Promise((resolve) => setDialog({ title, value, resolve }));
  }

  const [view, setView] = useState("Chat"),
    [error, setError] = useState(window.omnidevStartupError || ""),
    [busy, setBusy] = useState(false),
    [online, setOnline] = useState(false);
  const [providers, setProviders] = useState([]),
    [provider, setProvider] = useState("builtin"),
    [model, setModel] = useState("auto");
  const [agents, setAgents] = useState([]),
    [agent, setAgent] = useState(""),
    [tasks, setTasks] = useState([]),
    [task, setTask] = useState(null);
  const [projects, setProjects] = useState([]),
    [project, setProject] = useState(""),
    [sessions, setSessions] = useState([]),
    [session, setSession] = useState(""),
    [messages, setMessages] = useState([]),
    [input, setInput] = useState("");
  const [files, setFiles] = useState([]),
    [directory, setDirectory] = useState("."),
    [file, setFile] = useState(""),
    [content, setContent] = useState(""),
    [dirty, setDirty] = useState(false);
  const [output, setOutput] = useState(""),
    [memories, setMemories] = useState([]),
    [preferences, setPreferences] = useState([]),
    [memoryKey, setMemoryKey] = useState(""),
    [memoryValue, setMemoryValue] = useState(""),
    [scope, setScope] = useState("session"),
    [root, setRoot] = useState(""),
    [terminal, setTerminal] = useState(false);
  const [url, setUrl] = useState(connection().url),
    [token, setToken] = useState(sessionStorage.getItem("omnidev-token") || "");
  async function act(fn) {
    setError("");
    setBusy(true);
    try {
      return await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function refresh() {
    const [p, a, t, s, j, w] = await Promise.all([
      request("/chat/providers/"),
      request("/agents/?enabled_only=false"),
      request("/tasks/"),
      request("/sessions"),
      request("/projects/"),
      request("/workspace"),
    ]);
    setProviders(p);
    setAgents(a.agents);
    setTasks(t.tasks);
    setSessions(s.sessions);
    setProjects(j.projects);
    setRoot(w.root);
    setTerminal(w.terminal_enabled);
    setOnline(true);
  }
  useEffect(() => {
    if (window.omnidevStartupError) {
      setError(window.omnidevStartupError);
      return;
    }
    act(refresh);
  }, []);
  useEffect(() => {
    if (view !== "Tasks") return;
    const timer = setInterval(() => {
      request("/tasks/")
        .then((t) => setTasks(t.tasks))
        .catch((e) => setError(e.message));
      if (task)
        request(`/tasks/${task.task.id}`)
          .then(setTask)
          .catch((e) => setError(e.message));
    }, 1500);
    return () => clearInterval(timer);
  }, [view, task?.task.id]);
  async function loadMemory() {
    const path =
      scope === "project"
        ? `/memory/project/${project}`
        : "/memory/session" + (session ? "?session_id=" + session : "");
    const [m, p] = await Promise.all([
      request(path),
      request("/memory/preference"),
    ]);
    setMemories(m.memories);
    setPreferences(p.preferences);
  }
  useEffect(() => {
    if (view === "Memory" && (scope !== "project" || project)) act(loadMemory);
  }, [view, scope, project, session]);
  async function newSession() {
    const s = await request("/sessions", "POST", {
      name: input.slice(0, 70) || "New conversation",
    });
    setSession(s.id);
    setMessages([]);
    setSessions((prev) => [s, ...prev]);
    return s.id;
  }
  async function send(e) {
    e.preventDefault();
    if (!input.trim()) return;
    const text =
      input +
      (attachment
        ? `\n\nFile: ${attachment.name}\n\`\`\`\n${attachment.content}\n\`\`\``
        : "");
    setAttachment(null);
    setInput("");
    await act(async () => {
      let id = session || (await newSession());
      const history = [...messages, { role: "user", content: text }];
      setMessages([...history, { role: "assistant", content: "" }]);
      await request(`/sessions/${id}`, "PUT", { messages: history });
      let response = "";
      try {
        const instruction = {
          ask: "Answer the user's question. Explain clearly and do not claim to have executed tools.",
          plan: "Create a concrete implementation plan with steps, risks and verification. Do not implement or claim tool execution.",
          code: "Help implement the user's request with usable code and verification commands. Chat has no execution tools; suggest Tasks for execution.",
        }[appearance.mode];
        await streamChat(
          {
            provider,
            model,
            messages: [
              {
                role: "system",
                content:
                  instruction + " Response style: " + appearance.style + ".",
              },
              ...history,
            ],
          },
          (chunk) => {
            response += chunk;
            setMessages([...history, { role: "assistant", content: response }]);
          },
        );
      } finally {
        const updated = [...history, { role: "assistant", content: response }];
        setMessages(updated);
        await request(`/sessions/${id}`, "PUT", { messages: updated });
      }
    });
  }
  async function listFiles(path) {
    const f = await request("/files?path=" + encodeURIComponent(path));
    setFiles(f.items);
    setDirectory(path);
  }
  async function openFile(path) {
    if (dirty && !(await ask("Discard unsaved edits?", null))) return;
    const f = await request("/file?path=" + encodeURIComponent(path));
    setFile(path);
    setContent(f.content);
    setDirty(false);
  }
  async function makeTask(e) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    await act(async () => {
      const created = await request("/tasks/", "POST", {
        agent_id: Number(data.get("agent")),
        title: data.get("title"),
        description: data.get("description"),
        verification_command: data.get("verification") || null,
        project_id: project ? Number(project) : null,
        max_steps: 25,
      });
      await request(`/tasks/${created.id}/run`, "POST", {
        project_root: directory,
      });
      setTask(await request(`/tasks/${created.id}`));
      await refresh();
    });
  }
  const button = (label, fn) => (
    <button type="button" disabled={busy} onClick={() => act(fn)}>
      {label}
    </button>
  );
  return (
    <div className="app">
      {dialog && (
        <div className="modal">
          <form
            role="dialog"
            aria-modal="true"
            aria-label={dialog.title}
            onSubmit={(event) => {
              event.preventDefault();
              dialog.resolve(dialog.value === null ? true : dialog.value);
              setDialog(null);
            }}
          >
            <h2>{dialog.title}</h2>
            {dialog.value !== null && (
              <input
                autoFocus
                aria-label={dialog.title}
                value={dialog.value}
                onChange={(event) =>
                  setDialog({ ...dialog, value: event.target.value })
                }
              />
            )}
            <div className="toolbar">
              <button type="submit">Confirm</button>
              <button
                type="button"
                onClick={() => {
                  dialog.resolve(null);
                  setDialog(null);
                }}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}
      <aside>
        <div className="brand">
          <span>✦</span> OmniDev <small>WORKSPACE</small>
        </div>
        <button
          className="sidebar-search"
          onClick={() => {
            setView("Chat");
            setTimeout(
              () => document.getElementById("thread-search")?.focus(),
              0,
            );
          }}
        >
          ⌕ <span>Find a conversation</span>
          <kbd>⌘ K</kbd>
        </button>
        <span className="nav-label">Workspace</span>
        <nav>
          {views.map((v) => (
            <button
              key={v}
              className={view === v ? "active" : ""}
              onClick={() => {
                setView(v);
                if (v === "Files") act(() => listFiles(directory));
              }}
            >
              <span className="nav-icon" aria-hidden="true">
                {icons[v]}
              </span>
              {v === "Chat" ? "Ask AI" : v}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <span>✧</span>
          <strong>A little help, a lot of possibility.</strong>
          <p>Your ideas. Your models. Your workspace.</p>
          <button onClick={() => setView("Connectors")}>
            Connect your tools ↗
          </button>
        </div>
        <div className="connection">
          <i className={online ? "online" : ""} />{" "}
          {online ? "Connected" : "Disconnected"}
          <small>{root || "Connect to your engine"}</small>
        </div>
      </aside>
      <main>
        <div className="breadcrumb">
          <span>Workspace</span>
          <span> / </span>
          <strong>{view === "Chat" ? "Ask AI" : view}</strong>
          <button
            aria-label="Toggle theme"
            title="Toggle light and dark"
            onClick={() =>
              setAppearance({
                ...appearance,
                theme: appearance.theme === "dark" ? "light" : "dark",
              })
            }
          >
            ◐
          </button>
        </div>
        <header>
          <h1>{view === "Chat" ? "Ask AI" : view}</h1>
          {busy && <small role="status">Working…</small>}
          <select
            aria-label="Project"
            value={project}
            onChange={(e) => setProject(e.target.value)}
          >
            <option value="">All projects</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          {button("New project", async () => {
            const name = await ask("Project name");
            if (name) {
              await request("/projects/", "POST", { name });
              await refresh();
            }
          })}
          {button("Refresh", refresh)}
        </header>
        {error && (
          <div role="alert" className="error">
            {error}
            <button onClick={() => setError("")}>Dismiss</button>
          </div>
        )}
        <section className={view === "Chat" ? "chat-section" : ""}>
          {view === "Chat" && (
            <div className="chat">
              <div className="toolbar chat-tools">
                <input
                  id="thread-search"
                  aria-label="Search threads"
                  placeholder="⌕  Search threads"
                  value={threadSearch}
                  onChange={(e) => setThreadSearch(e.target.value)}
                />
                <select
                  aria-label="Conversation"
                  disabled={busy}
                  value={session}
                  onChange={(e) =>
                    act(async () => {
                      setSession(e.target.value);
                      setMessages(
                        e.target.value
                          ? (await request(`/sessions/${e.target.value}`))
                              .messages
                          : [],
                      );
                    })
                  }
                >
                  <option value="">New conversation</option>
                  {sessions
                    .filter((s) =>
                      s.name.toLowerCase().includes(threadSearch.toLowerCase()),
                    )
                    .map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                </select>
                {button("Create folder", async () => {
                  const path = await ask("Folder path relative to workspace");
                  if (path) await request("/directories", "POST", { path });
                })}
                <button
                  className="primary"
                  disabled={busy}
                  onClick={() => {
                    setSession("");
                    setMessages([]);
                    setInput("");
                  }}
                >
                  + New chat
                </button>
                {session &&
                  button("Delete conversation", async () => {
                    await request(`/sessions/${session}`, "DELETE");
                    setSession("");
                    setMessages([]);
                    await refresh();
                  })}
              </div>
              <div className="messages">
                {!messages.length && (
                  <div className="empty">
                    <div className="orbital" aria-hidden="true">
                      <div className="orbital-core">✦</div>
                      <div className="orbit one" />
                      <div className="orbit two" />
                      <div className="orbit three" />
                    </div>
                    <span className="eyebrow">
                      A LITTLE SPARK. ENDLESS POSSIBILITIES.
                    </span>
                    <h2>
                      Hello, <span>what’s on your mind?</span>
                    </h2>
                    <p>From a first thought to your next big thing.</p>
                  </div>
                )}
                {messages.map((m, i) => (
                  <article className={"message " + m.role} key={i}>
                    <small>{m.role}</small>
                    <pre>
                      {m.content || (busy ? "Thinking…" : "No response")}
                    </pre>
                  </article>
                ))}
              </div>
              <form onSubmit={send} className="compose">
                <div className="compose-heading">
                  <span>✦</span>{" "}
                  {appearance.mode === "plan"
                    ? "Let’s make a plan"
                    : appearance.mode === "code"
                      ? "Let’s build something"
                      : "Ask me anything"}
                  <small> — a little clarity goes a long way.</small>
                </div>
                <textarea
                  aria-label="Message"
                  placeholder="Ask a question or describe an idea…"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  disabled={busy}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) send(e);
                  }}
                />
                {attachment && (
                  <div className="attachment">
                    {attachment.name}
                    <button type="button" onClick={() => setAttachment(null)}>
                      Remove
                    </button>
                  </div>
                )}
                <div className="compose-footer">
                  <label className="attach-button">
                    ↗ Attach text
                    <input
                      type="file"
                      aria-label="Attach text file"
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f)
                          act(async () => {
                            if (f.size > 200000)
                              throw new Error(
                                "Choose a text file smaller than 200 KB",
                              );
                            const text = await f.text();
                            if (text.includes("\0"))
                              throw new Error("Please attach a text file");
                            setAttachment({ name: f.name, content: text });
                          });
                        e.target.value = "";
                      }}
                    />
                  </label>
                  <select
                    aria-label="Chat mode"
                    value={appearance.mode}
                    onChange={(e) =>
                      setAppearance({ ...appearance, mode: e.target.value })
                    }
                  >
                    <option value="ask">Ask</option>
                    <option value="plan">Plan</option>
                    <option value="code">Code</option>
                  </select>
                  <select
                    aria-label="Response style"
                    value={appearance.style}
                    onChange={(e) =>
                      setAppearance({ ...appearance, style: e.target.value })
                    }
                  >
                    <option value="balanced">Balanced</option>
                    <option value="concise">Concise</option>
                    <option value="detailed">Detailed</option>
                  </select>
                  <button
                    className="send"
                    aria-label="Send message"
                    disabled={busy || !input.trim() || !model.trim()}
                  >
                    {busy ? "···" : "↑"}
                  </button>
                </div>
              </form>
              <div className="model-bar">
                <ModelPicker
                  providers={providers}
                  provider={provider}
                  model={model}
                  onProvider={setProvider}
                  onModel={setModel}
                  busy={busy}
                />
                <small>Ctrl + Enter to send</small>
              </div>
            </div>
          )}
          {view === "Agents" && (
            <>
              <h2>Create an agent</h2>
              <form
                className="form"
                onSubmit={(e) => {
                  e.preventDefault();
                  const f = new FormData(e.currentTarget);
                  act(async () => {
                    await request("/agents/", "POST", {
                      name: f.get("name"),
                      provider: f.get("provider"),
                      model: f.get("model"),
                      tool_names: f.getAll("tools"),
                      system_prompt:
                        "Plan the task, use tools to implement it, run tests and fix failures before COMPLETE. Use THOUGHT, ACTION: tool_name {JSON}, COMPLETE: summary.",
                    });
                    await refresh();
                  });
                }}
              >
                <label>
                  Name
                  <input name="name" required />
                </label>
                <ModelPicker
                  providers={providers}
                  provider={provider}
                  model={model}
                  onProvider={setProvider}
                  onModel={setModel}
                  busy={busy}
                  form
                />
                <fieldset>
                  <legend>Allowed tools</legend>
                  {[
                    "think",
                    "read_file",
                    "list_files",
                    "write_file",
                    "git_status",
                    "git_diff",
                    "git_commit",
                    ...(terminal ? ["shell"] : []),
                  ].map((t) => (
                    <label key={t}>
                      <input
                        type="checkbox"
                        name="tools"
                        value={t}
                        defaultChecked={[
                          "think",
                          "read_file",
                          "list_files",
                        ].includes(t)}
                      />
                      {t}
                    </label>
                  ))}
                </fieldset>
                <button disabled={busy}>Create agent</button>
              </form>
              <div className="cards">
                {agents.map((a) => (
                  <article key={a.id}>
                    <h3>{a.name}</h3>
                    <p>
                      {a.provider} / {a.model}
                    </p>
                    <p>
                      {a.tool_count} tools ·{" "}
                      {a.enabled ? "Enabled" : "Disabled"}
                    </p>
                    {button("Delete", async () => {
                      if (await ask("Delete agent and its tasks?", null)) {
                        await request(`/agents/${a.id}`, "DELETE");
                        await refresh();
                      }
                    })}
                  </article>
                ))}
              </div>
            </>
          )}
          {view === "Tasks" && (
            <div className="split">
              <div>
                <h2>Run a development task</h2>
                <form className="form" onSubmit={makeTask}>
                  <label>
                    Agent
                    <select
                      required
                      name="agent"
                      value={agent}
                      onChange={(e) => setAgent(e.target.value)}
                    >
                      <option value="">Choose an agent</option>
                      {agents
                        .filter((a) => a.enabled)
                        .map((a) => (
                          <option key={a.id} value={a.id}>
                            {a.name}
                          </option>
                        ))}
                    </select>
                  </label>
                  <label>
                    Title
                    <input name="title" required />
                  </label>
                  <label>
                    Instructions
                    <textarea name="description" required />
                  </label>
                  <label>
                    Verification command
                    <input
                      name="verification"
                      placeholder="python -m unittest discover"
                    />
                  </label>
                  <p className="muted">
                    Runs in {directory} under the project root. Assign shell and
                    write tools to enable development and verification.
                  </p>
                  <button disabled={busy}>Start task</button>
                </form>
                <h2>Task history</h2>
                {tasks.map((t) => (
                  <button
                    className="row"
                    key={t.id}
                    onClick={() =>
                      act(async () => setTask(await request(`/tasks/${t.id}`)))
                    }
                  >
                    <strong>{t.title}</strong>
                    <span>
                      {t.status} · {t.step_count} steps
                    </span>
                  </button>
                ))}
              </div>
              <div>
                {task ? (
                  <>
                    <h2>{task.task.title}</h2>
                    <p>{task.task.status}</p>
                    {["pending", "running"].includes(task.task.status) &&
                      button("Cancel", async () => {
                        await request(`/tasks/${task.task.id}`, "DELETE");
                        setTask(await request(`/tasks/${task.task.id}`));
                      })}
                    <pre>{task.task.result || task.task.error}</pre>
                    {task.steps.map((s, i) => (
                      <article key={i}>
                        <small>
                          Step {s.step_index} · {s.kind} {s.tool_name}
                        </small>
                        <pre>{s.content}</pre>
                      </article>
                    ))}
                  </>
                ) : (
                  <p className="empty">Select a task to follow its progress.</p>
                )}
              </div>
            </div>
          )}
          {view === "Files" && (
            <div className="split files">
              <div>
                <div className="toolbar">
                  <input
                    aria-label="Directory"
                    value={directory}
                    onChange={(e) => setDirectory(e.target.value)}
                  />
                  {button("Open", () => listFiles(directory))}
                  {button("Up", () =>
                    listFiles(
                      directory.includes("/")
                        ? directory.split("/").slice(0, -1).join("/") || "."
                        : ".",
                    ),
                  )}
                  {button("New file", async () => {
                    const path = await ask("Path relative to project root");
                    if (path) {
                      await request("/file", "PUT", { path, content: "" });
                      await listFiles(directory);
                      await openFile(path);
                    }
                  })}
                </div>
                {files.map((f) => (
                  <button
                    className="row"
                    key={f.path}
                    onClick={() =>
                      act(() =>
                        f.isDirectory ? listFiles(f.path) : openFile(f.path),
                      )
                    }
                  >
                    {f.isDirectory ? "▸" : "·"} {f.name}
                  </button>
                ))}
              </div>
              <div className="editor">
                <div className="toolbar">
                  <strong>
                    {file || "Select a file"}
                    {dirty ? " •" : ""}
                  </strong>
                  {button("Save", async () => {
                    if (!file) return;
                    await request("/file", "PUT", { path: file, content });
                    setDirty(false);
                  })}
                </div>
                <textarea
                  aria-label="Code editor"
                  disabled={!file}
                  value={content}
                  spellCheck="false"
                  onChange={(e) => {
                    setContent(e.target.value);
                    setDirty(true);
                  }}
                />
              </div>
            </div>
          )}
          {view === "Terminal" && (
            <>
              <p className="muted">
                Commands run in {directory}.{" "}
                {terminal
                  ? "Execution enabled."
                  : "Enable TERMINAL_ENABLED on the server to use the terminal."}
              </p>
              <form
                className="toolbar"
                onSubmit={(e) => {
                  e.preventDefault();
                  const form = e.currentTarget;
                  const command = new FormData(form).get("command");
                  act(async () => {
                    const result = await request("/terminal", "POST", {
                      command,
                      path: directory,
                    });
                    setOutput(
                      (prev) =>
                        prev +
                        "\n$ " +
                        command +
                        "\n" +
                        result.output +
                        "\nExit: " +
                        result.exit_code +
                        (result.timed_out ? " (timed out)" : ""),
                    );
                    form.reset();
                  });
                }}
              >
                <input
                  name="command"
                  aria-label="Command"
                  placeholder="Command…"
                  required
                  disabled={!terminal || busy}
                />
                <button disabled={!terminal || busy}>Run</button>
                {button("Clear", async () => setOutput(""))}
              </form>
              <pre className="terminal">
                {output || "Command output will appear here."}
              </pre>
            </>
          )}
          {view === "Memory" && (
            <>
              <div className="toolbar">
                <select
                  aria-label="Memory scope"
                  value={scope}
                  onChange={(e) => setScope(e.target.value)}
                >
                  <option value="session">Session</option>
                  <option disabled={!project} value="project">
                    Project
                  </option>
                  <option value="preference">Preferences</option>
                </select>
                <input
                  placeholder="Key"
                  aria-label="Memory key"
                  value={memoryKey}
                  onChange={(e) => setMemoryKey(e.target.value)}
                />
                <input
                  placeholder="Value"
                  aria-label="Memory value"
                  value={memoryValue}
                  onChange={(e) => setMemoryValue(e.target.value)}
                />
                {button("Save memory", async () => {
                  if (!memoryKey) return;
                  const body = {
                    key: memoryKey,
                    value: memoryValue,
                    ...(scope === "session" && session
                      ? { session_id: session }
                      : {}),
                    ...(scope === "preference"
                      ? { category: "general", user_id: "default" }
                      : {}),
                  };
                  await request(
                    scope === "project"
                      ? `/memory/project/${project}`
                      : scope === "preference"
                        ? "/memory/preference"
                        : "/memory/session",
                    "POST",
                    body,
                  );
                  setMemoryKey("");
                  setMemoryValue("");
                  await loadMemory();
                })}
              </div>
              {(scope === "preference" ? preferences : memories).map((m) => (
                <article key={m.key}>
                  <h3>{m.key}</h3>
                  <pre>{m.value || JSON.stringify(m.data)}</pre>
                  {button("Delete", async () => {
                    await request(
                      scope === "project"
                        ? `/memory/project/${project}/${encodeURIComponent(m.key)}`
                        : scope === "preference"
                          ? `/memory/preference/${m.category}/${encodeURIComponent(m.key)}`
                          : `/memory/session/${encodeURIComponent(m.key)}` +
                            (session ? "?session_id=" + session : ""),
                      "DELETE",
                    );
                    await loadMemory();
                  })}
                </article>
              ))}
            </>
          )}
          {view === "Models" && (
            <Models act={act} refresh={refresh} busy={busy} />
          )}
          {view === "Connectors" && (
            <Connectors act={act} refresh={refresh} busy={busy} />
          )}
          {view === "Settings" && (
            <Personalization value={appearance} onChange={setAppearance} />
          )}
          {view === "Connection" && (
            <form
              className="form"
              onSubmit={(e) => {
                e.preventDefault();
                if (
                  desktopConnection &&
                  url.replace(/\/$/, "") === desktopConnection.url
                ) {
                  localStorage.removeItem("omnidev-url");
                  sessionStorage.removeItem("omnidev-token");
                } else {
                  localStorage.setItem("omnidev-url", url.replace(/\/$/, ""));
                  sessionStorage.setItem("omnidev-token", token);
                }
                act(async () => {
                  setOnline(false);
                  await refresh();
                });
              }}
            >
              <h2>Connect to your engine</h2>
              <p>
                Web uses the current server. Packaged Windows desktop starts its
                own local engine; other desktop builds default to
                http://127.0.0.1:8000. Remote engines require HTTPS and an API
                token.
              </p>
              <label>
                Engine URL
                <input
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="Leave empty for this server"
                />
              </label>
              <label>
                API token
                <input
                  type="password"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  autoComplete="off"
                />
              </label>
              <button>Connect</button>
              <label className="execution-toggle">
                <input
                  type="checkbox"
                  checked={terminal}
                  onChange={(e) => {
                    const enabled = e.target.checked;
                    act(async () => {
                      await request("/workspace/execution", "PUT", { enabled });
                      setTerminal(enabled);
                    });
                  }}
                />{" "}
                Allow terminal and external harness execution for this engine
                session
              </label>
              <small>
                Commands run with your OS account permissions. This setting
                resets to the engine configuration when it restarts.
              </small>
              <p className="muted">
                The token is kept for this browser session. Provider keys stay
                on the server.
              </p>
            </form>
          )}
        </section>
      </main>
    </div>
  );
}
