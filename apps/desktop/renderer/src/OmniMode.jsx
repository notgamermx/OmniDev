import React, { useState } from "react";
import ModelPicker from "./ModelPicker";
import { request } from "./services/api";

export default function OmniMode({ agents, providers, act, busy, onSetup }) {
  const [prompt, setPrompt] = useState("");
  const [selected, setSelected] = useState([]);
  const [reviewerProvider, setReviewerProvider] = useState("builtin");
  const [reviewerModel, setReviewerModel] = useState("auto");
  const [result, setResult] = useState(null);

  function toggleAgent(id) {
    setSelected((current) =>
      current.includes(id)
        ? current.filter((value) => value !== id)
        : current.length < 5
          ? [...current, id]
          : current,
    );
  }

  function run() {
    if (!prompt.trim()) return;
    if (!selected.length) {
      return act(async () => {
        throw new Error("Choose at least one specialist agent.");
      });
    }
    if (!reviewerProvider || !reviewerModel.trim()) {
      return act(async () => {
        throw new Error("Choose a reviewer provider and model.");
      });
    }
    setResult(null);
    return act(async () => {
      const data = await request("/omnimode/run", "POST", {
        prompt: prompt.trim(),
        agent_ids: selected,
        reviewer_provider: reviewerProvider,
        reviewer_model: reviewerModel.trim(),
      });
      setResult(data);
    });
  }

  const enabledAgents = agents.filter((agent) => agent.enabled);
  const review = result?.review;
  const totalTokens = [...(result?.specialists || []), ...(review ? [review] : [])]
    .reduce((sum, item) => sum + (item.usage?.total_tokens || 0), 0);

  return (
    <div className="omnimode-page">
      <div className="omnimode-intro">
        <span className="eyebrow">PARALLEL REASONING WORKFLOW</span>
        <h2>OmniMode</h2>
        <p>Send one task to independent specialist agents at the same time. A separate reviewer compares their work, challenges weak claims, and writes the final synthesis.</p>
        <div className="omnimode-flow">
          <span>One task</span><b>→</b><span>Parallel agents</span><b>→</b><span>Independent review</span><b>→</b><span>Final answer</span>
        </div>
      </div>

      <section className="omnimode-panel">
        <div className="omnimode-panel-heading">
          <div><h3>1. Define the task</h3><p>Give every specialist the same task so their approaches can be compared.</p></div>
          <span className="omnimode-count">{selected.length}/5 agents</span>
        </div>
        <textarea aria-label="OmniMode task" className="omnimode-prompt" rows={5} value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Describe the problem, expected result, constraints, and what a good answer must include…" disabled={busy} />
      </section>

      <section className="omnimode-panel">
        <div className="omnimode-panel-heading">
          <div><h3>2. Choose specialist agents</h3><p>Each selected agent uses its saved provider, model, focus, and instructions.</p></div>
          <span className="omnimode-count">{enabledAgents.length} available</span>
        </div>
        {!enabledAgents.length && <p className="empty">Create and enable agents in the Agents page first.</p>}
        <div className="omnimode-agent-grid">
          {enabledAgents.map((agent) => (
            <label className={"omnimode-agent" + (selected.includes(agent.id) ? " selected" : "")} key={agent.id}>
              <input type="checkbox" checked={selected.includes(agent.id)} disabled={busy || (!selected.includes(agent.id) && selected.length >= 5)} onChange={() => toggleAgent(agent.id)} />
              <span className="omnimode-agent-copy">
                <strong>{agent.name}</strong>
                <small>{agent.description || "General specialist"}</small>
                <small className="omnimode-model">{agent.provider} · {agent.model}</small>
              </span>
              <span className="omnimode-check">{selected.includes(agent.id) ? "Selected" : "Select"}</span>
            </label>
          ))}
        </div>
      </section>

      <section className="omnimode-panel">
        <div className="omnimode-panel-heading">
          <div><h3>3. Independent reviewer</h3><p>Choose your strongest configured model. For example, use NVIDIA NIM with Nemotron 3 Ultra 550B when your account has access to it.</p></div>
        </div>
        <ModelPicker providers={providers} provider={reviewerProvider} model={reviewerModel} onProvider={(value) => { setReviewerProvider(value); setReviewerModel(value === "builtin" ? "auto" : ""); }} onModel={setReviewerModel} onSetup={onSetup} busy={busy} />
        <p className="muted omnimode-note">The reviewer compares model outputs and flags reasoning gaps. This review is not a substitute for actually running tests, checking external sources, or inspecting project files.</p>
      </section>

      <div className="omnimode-run-row">
        <button className="omnimode-run" type="button" disabled={busy || !prompt.trim() || !selected.length || !reviewerModel.trim()} onClick={run}>{busy ? "Running parallel agents…" : "Run OmniMode ↗"}</button>
        <span>Up to 5 specialists run concurrently, followed by 1 reviewer call.</span>
      </div>

      {result && (
        <section className="omnimode-results">
          <div className="omnimode-results-heading">
            <div><span className="eyebrow">RUN REPORT</span><h3>Specialist outputs</h3></div>
            <span className={"omnimode-status " + result.status}>{result.status.replaceAll("_", " ")}</span>
          </div>
          <div className="omnimode-result-grid">
            {result.specialists.map((agent) => (
              <article className="omnimode-result-card" key={agent.agent_id}>
                <div className="omnimode-result-card-heading"><strong>{agent.name}</strong><span className={"omnimode-status " + agent.status}>{agent.status}</span></div>
                <small>{agent.provider} · {agent.model} · {(agent.elapsed_ms / 1000).toFixed(1)}s</small>
                {agent.output ? <pre>{agent.output}</pre> : <p className="empty">{agent.error || "No output returned."}</p>}
              </article>
            ))}
          </div>
          <article className="omnimode-review-card">
            <div className="omnimode-result-card-heading"><div><span className="eyebrow">INDEPENDENT REVIEW</span><h3>Final synthesis</h3></div><span className={"omnimode-status " + (review?.status || "failed")}>{review?.status || "not run"}</span></div>
            <small>{review?.provider} · {review?.model} {review?.elapsed_ms != null ? "· " + (review.elapsed_ms / 1000).toFixed(1) + "s" : ""}</small>
            {review?.output ? <pre>{review.output}</pre> : <p className="empty">{review?.error || "Reviewer did not return an answer."}</p>}
          </article>
          <p className="muted omnimode-note">Verification scope: model cross-review only · {totalTokens.toLocaleString()} reported tokens across successful calls. Provider token counts may be unavailable or estimates.</p>
        </section>
      )}
    </div>
  );
}
