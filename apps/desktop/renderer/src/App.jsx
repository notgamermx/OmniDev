import React, { useEffect, useState } from "react";
import { request, streamChat, connection, normalizeEngineUrl } from "./services/api";
import Connectors from "./Connectors";
import Models from "./Models";
import OmniMode from "./OmniMode";
import ModelPicker from "./ModelPicker";
import logo from "./assets/logo.svg";
import ResponseContent from "./ResponseContent";
import { downloadText } from "./services/download";
import { desktopConnection } from "./services/desktop";
import Personalization, { loadAppearance } from "./Personalization";
const iconPaths = {
  Chat: "M4 4h16v12H9l-5 4z", Tasks: "m5 6 2 2 4-4M13 6h7M5 13h15M5 19h15",
  Agents: "M8 4h8v5H8zM4 15h5v5H4zM15 15h5v5h-5zM12 9v3M6 15v-3h12v3",
  OmniMode: "M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8m7.2 7.2 2.8 2.8m0-12.8-2.8 2.8m-7.2 7.2-2.8 2.8M9 9h6v6H9z",
  Files: "M3 6h7l2 3h9v12H3z", Terminal: "m5 6 5 6-5 6M13 18h6",
  Memory: "M5 4h14v16H5zM8 8h8M8 12h8M8 16h5", Models: "M12 3 3 8l9 5 9-5zM3 12l9 5 9-5M3 16l9 5 9-5",
  Connectors: "m8 3 4 4-5 5-4-4zM17 12l4 4-5 5-4-4zM9 15l6-6", Connection: "M4 8a12 12 0 0 1 16 0M7 12a7 7 0 0 1 10 0M10 16a3 3 0 0 1 4 0M12 20h.01",
  Settings: "M4 7h16M4 17h16M8 4v6M16 14v6",
};
function Icon({ name }) { return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={iconPaths[name]} /></svg>; }
const label = (view) => ({ Chat: "Chat", Tasks: "Activity", Models: "Models & keys" }[view] || view);
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
  const [showThreads, setShowThreads] = useState(false);
  const [attachment, setAttachment] = useState(null);\n  const [imagePreview, setImagePreview] = useState("");
  useEffect(() => {
    localStorage.setItem("omnidev-appearance", JSON.stringify(appearance));
    const element = document.documentElement;
    for (const [key, value] of Object.entries(appearance))
      element.dataset[key] = value;
  }, [appearance]);
  const [dialog, setDialog] = useState(null);
  function ask(title, value = "", description = "") {
    return new Promise((resolve) => setDialog({ title, value, description, resolve }));
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
    await request("/health/").then(() => setOnline(true)).catch(error => { setOnline(false); throw error; });
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
  }
  useEffect(() => {
    if (window.omnidevStartupError) {
      setError(window.omnidevStartupError);
      return;
    }
    act(refresh);
    const reconnect = () => refresh().catch((e) => setError(e.message));
    window.addEventListener("online", reconnect);
    return () => window.removeEventListener("online", reconnect);
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
    if (!input.trim() || busy) return;
    if (!model.trim()) { setError("Choose a model before sending a message."); return; }
    const text =
      input +
      (attachment
        ? `\n\nFile: ${attachment.name}\n\`\`\`\n${attachment.content}\n\`\`\``
        : "");
    setAttachment(null);
    setInput("");
    await act(async () => {
      let id = session || (await newSession());
      const history = [...messages.filter((m) => m.content?.trim()), { role: "user", content: text }];
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
        if (!response.trim()) throw new Error("The model returned an empty reply. Choose another chat model or shorten your conversation.");
      } finally {
        const updated = response ? [...history, { role: "assistant", content: response }] : history;
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
  async function activateProject(value) {
    await act(async () => {
      if (!value) {
        setProject("");
        await listFiles(".");
        return;
      }
      const workspace = await request(`/projects/${value}/workspace`, "POST");
      setProject(String(value));
      await listFiles(workspace.path);
    });
  }
  async function importFiles(event) {
    const selectedFiles = Array.from(event.target.files || []);
    event.target.value = "";
    if (!selectedFiles.length) return;
    await act(async () => {
      for (const selectedFile of selectedFiles) {
        if (selectedFile.size <= 0 || selectedFile.size > 10000000) {
          throw new Error(`Choose a non-empty file under 10 MB: ${selectedFile.name}`);
        }
        const dataUrl = await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(String(reader.result || ""));
          reader.onerror = () => reject(new Error(`Could not read ${selectedFile.name}`));
          reader.readAsDataURL(selectedFile);
        });
        const relativePath = directory === "." ? selectedFile.name : `${directory}/${selectedFile.name}`;
        await request("/files/import", "POST", {
          path: relativePath,
          content_base64: dataUrl.slice(dataUrl.indexOf(",") + 1),
          overwrite: false,
        });
      }
      await listFiles(directory);
    });
  }
  async function openImage(path) {
    if (dirty && !(await ask("Discard unsaved edits?", null))) return;
    const data = await request("/file/base64?path=" + encodeURIComponent(path));
    setFile(path);
    setContent("");
    setImagePreview(`data:${data.media_type};base64,${data.content_base64}`);
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
            className={dialog.description ? "host-approval" : undefined}
            aria-modal="true"
            aria-label={dialog.title}
            onSubmit={(event) => {
              event.preventDefault();
              dialog.resolve(dialog.value === null ? true : dialog.value);
              setDialog(null);
            }}
          >
            <h2>{dialog.title}</h2>
            {dialog.description && <p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{dialog.description}</p>}
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
          <img src={logo} alt="" width="28" height="28" /> <strong>OmniDev</strong>
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
                <Icon name={v} />
              </span>
              {label(v)}
            </button>
          ))}
        </nav>
        <button className="connection" onClick={() => setView("Connection")}>
          <i className={online ? "online" : ""} />
          <span>{online ? "Engine connected" : "Engine offline"}</span>
          <span aria-hidden="true">↗</span>
        </button>
      </aside>
      <main>
        <header>
          <h1>{label(view)}</h1>
          {busy && <small role="status">Working…</small>}
          <select
            aria-label="Project"
            value={project}
            onChange={(e) => activateProject(e.target.value)}
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
          <button className="theme-toggle" aria-label="Toggle theme" title="Toggle light and dark" onClick={() => setAppearance({ ...appearance, theme: appearance.theme === "dark" ? "light" : "dark" })}>◐</button>
        </header>
        {error && (
          <div role="alert" className="error">
            <span>{error}</span>
            {view === "Chat" && <button onClick={() => { setView("Models"); setError(""); }}>Model settings</button>}
            <button onClick={() => setError("")}>Dismiss</button>
          </div>
        )}
        <section className={view === "Chat" ? "chat-section" : ""}>
          {view === "Chat" && (
            <div className={"chat-workspace" + (showThreads ? " threads-open" : "")}>
              <div className="conversation-sidebar" role="navigation" aria-label="Conversations">
                <div className="conversation-sidebar-heading"><strong>Conversations</strong><span>{sessions.length}</span><button className="close-threads" aria-label="Close conversations" onClick={() => setShowThreads(false)}>×</button></div>
                <button className="new-conversation" disabled={busy} onClick={() => { setSession(""); setMessages([]); setInput(""); setShowThreads(false); }}>+ New conversation</button>
                <input id="thread-search" aria-label="Search threads" placeholder="Search conversations…" value={threadSearch} onChange={e => setThreadSearch(e.target.value)} />
                <div className="conversation-list">
                  {sessions.filter(s => s.name.toLowerCase().includes(threadSearch.toLowerCase())).map(s => <button key={s.id} className={String(session) === String(s.id) ? "selected" : ""} aria-current={String(session) === String(s.id) ? "page" : undefined} disabled={busy} onClick={() => act(async () => { const saved = await request(`/sessions/${s.id}`); setSession(s.id); setMessages(saved.messages); setShowThreads(false); })}><Icon name="Chat" /><span>{s.name}</span></button>)}
                  {!sessions.length && <p>Your conversations will appear here.</p>}
                  {!!sessions.length && !sessions.some(s => s.name.toLowerCase().includes(threadSearch.toLowerCase())) && <p>No matching conversations.</p>}
                </div>
                <button className="workspace-files" onClick={() => { setView("Files"); act(() => listFiles(directory)); }}><Icon name="Files" /><span>Browse workspace files</span><span>↗</span></button>
              </div>
              <div className="chat">
                <div className="conversation-heading">
                  <button className="threads-toggle" aria-label="Toggle conversations" aria-expanded={showThreads} onClick={() => setShowThreads(!showThreads)}><Icon name="Chat" /></button>
                  <span>{sessions.find(s => String(s.id) === String(session))?.name || "New conversation"}</span>
                  <div className="conversation-actions">
                    {button("Create folder", async () => { const path = await ask("Folder path relative to workspace"); if (path) await request("/directories", "POST", { path }); })}
                    {messages.length > 0 && button("↓ Download chat", () => downloadText("omnidev-conversation.md", messages.map(m => `## ${m.role}\n\n${m.content}`).join("\n\n"), "text/markdown;charset=utf-8"))}
                    {session && button("Delete conversation", async () => { if (!(await ask("Delete this conversation?", null))) return; await request(`/sessions/${session}`, "DELETE"); setSession(""); setMessages([]); await refresh(); })}
                  </div>
                </div>
              <div className="messages">
                {!messages.length && (
                  <div className="conversation-empty">
                    <span className="workspace-caption"><span className="workspace-mark">/</span> {projects.find(p => String(p.id) === String(project))?.name || "Your workspace"}</span>
                    <h2>Start a conversation.</h2>
                    <p>Bring a question, a piece of code, or your next change.</p>
                    <div className="starter-list">
                      {[
                        ["Explain this project", "Find your way around the codebase."],
                        ["Plan a feature", "Break an idea into useful steps."],
                        ["Review my code", "Get a second look at a change."],
                      ].map(([text, detail], i) => <button key={text} onClick={() => { setInput(text); document.querySelector('[aria-label="Message"]')?.focus(); }}><span className="starter-number">0{i + 1}</span><span><strong>{text}</strong><small>{detail}</small></span><span aria-hidden="true">↗</span></button>)}
                    </div>
                    <button className="text-link" onClick={() => setView("Tasks")}>Run an agent task <span>→</span></button>
                  </div>
                )}
                {messages.map((m, i) => (
                  <article className={"message " + m.role} key={i}>
                    <div className="message-heading">
                      <small>{m.role === "assistant" ? "OmniDev" : "You"}</small>
                      <button type="button" className="download-action" disabled={busy || !m.content}
                        onClick={() => act(() => downloadText(`omnidev-${m.role}-${i + 1}.md`, m.content, "text/markdown;charset=utf-8"))}>↓ Download</button>
                    </div>
                    <ResponseContent text={m.content || (busy ? "Thinking…" : "No response")} act={act} busy={busy} />
                  </article>
                ))}
              </div>
              <form onSubmit={send} className="compose">
                <textarea
                  aria-label="Message"
                  placeholder="Describe a change, ask about your code, or paste an error…"
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
                <div className="composer-models">
                <ModelPicker
                  onSetup={() => setView("Models")}
                  providers={providers}
                  provider={provider}
                  model={model}
                  onProvider={setProvider}
                  onModel={setModel}
                  busy={busy}
                />
                </div>
              </form>
              <small className="compose-hint">Ctrl + Enter to send · Conversations saved locally</small>
              </div>
            </div>
          )}
          {view === "OmniMode" && (\n            <OmniMode agents={agents} providers={providers} act={act} busy={busy} onSetup={() => setView("Models")} />\n          )}\n          {view === "Agents" && (
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
                  onSetup={() => setView("Models")}
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
                    <div className="activity-summary" role="status">
                      <span className="status-tag">{task.task.status}</span>
                      <span>{agents.find(a => a.id === task.task.agent_id)?.name || "Agent"}</span>
                      <span>{task.task.model || agents.find(a => a.id === task.task.agent_id)?.model}</span>
                      <span>{task.task.step_count || 0} planning steps</span>
                      <span>{task.task.token_spent || 0} budget units reserved</span>
                    </div>
                    <details className="permission-panel"><summary>Execution permissions</summary><p>Files: {root}. Shell: {terminal ? "Docker sandbox, network disabled" : "disabled"}. Harnesses: separate host approval required.</p><p>Assigned tools: {(agents.find(a => a.id === task.task.agent_id)?.tool_names || []).join(", ") || "none"}. Existing verification files are protected.</p></details>
                    {["pending", "queued", "running", "verifying", "paused"].includes(task.task.status) &&
                      button("Cancel", async () => {
                        await request(`/tasks/${task.task.id}`, "DELETE");
                        setTask(await request(`/tasks/${task.task.id}`));
                      })}
                    {["running", "paused"].includes(task.task.status) && button(task.task.status === "paused" ? "Resume" : "Pause after operation", async () => {
                      await request(`/tasks/${task.task.id}/pause`, "POST", { paused: task.task.status !== "paused" });
                      setTask(await request(`/tasks/${task.task.id}`));
                    })}
                    {button("↓ Download task", () => downloadText("omnidev-task.json", JSON.stringify(task, null, 2), "application/json"))}
                    <pre>{task.task.result || task.task.error}</pre>
                    <h3>Execution history</h3>
                    <div className="activity-timeline">{task.steps.map((s, i) => (
                      <details key={i} open={i === task.steps.length - 1}>
                        <summary><span>{s.kind}</span> {s.tool_name || (s.kind === "state" ? "State transition" : "Planning")} <time>{new Date(s.created_at).toLocaleTimeString()}</time></summary>
                        <pre>{s.content}</pre>
                      </details>
                    ))}</div>
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
                  {button("Open", () => listFiles(directory))}\n                  <label className="import-button">\n                    Import files\n                    <input type="file" multiple onChange={importFiles} aria-label="Import files into workspace" />\n                  </label>
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
                        f.isDirectory ? listFiles(f.path) : f.isImage ? openImage(f.path) : openFile(f.path),
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
                  <button type="button" disabled={!file || busy} onClick={() => act(() => downloadText(file, content))}>↓ Download file</button>
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
                <button type="button" disabled={!output || busy} onClick={() => act(() => downloadText("omnidev-terminal.txt", output))}>↓ Download output</button>
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
              {button("↓ Download memory", () => downloadText(`omnidev-${scope}-memory.json`, JSON.stringify(scope === "preference" ? preferences : memories, null, 2), "application/json"))}
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
            <Connectors act={act} refresh={refresh} busy={busy} ask={ask} />
          )}
          {view === "Settings" && (
            <Personalization value={appearance} onChange={setAppearance} />
          )}
          {view === "Connection" && (
            <form
              className="form"
              onSubmit={(e) => {
                e.preventDefault();
                let normalized;
                try { normalized = normalizeEngineUrl(url); } catch (error) { setError(error.message); return; }
                if (
                  desktopConnection &&
                  normalized === desktopConnection.url
                ) {
                  localStorage.removeItem("omnidev-url");
                  sessionStorage.removeItem("omnidev-token");
                } else {
                  localStorage.setItem("omnidev-url", normalized);
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
              <div className="toolbar"><button disabled={busy}>Connect</button><button type="button" onClick={() => { localStorage.removeItem("omnidev-url"); sessionStorage.removeItem("omnidev-token"); setUrl(connection().url); setToken(""); act(refresh); }}>Use default engine</button></div>
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
                Terminal commands run in Docker. External harnesses use your OS
                account and require separate approval for each operation. This
                setting resets when the engine restarts.
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
