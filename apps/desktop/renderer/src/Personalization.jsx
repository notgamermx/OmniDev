import React from "react";
export const defaults = {
  theme: "light",
  accent: "blue",
  density: "comfortable",
  font: "system",
  motion: "full",
  style: "balanced",
  mode: "ask",
};
export function loadAppearance() {
  try {
    const saved = JSON.parse(localStorage.getItem("omnidev-appearance") || "{}");
    return { ...defaults, ...saved, accent: ["blue", "graphite"].includes(saved.accent) ? saved.accent : "blue" };
  } catch {
    return defaults;
  }
}
export default function Personalization({ value, onChange }) {
  const options = {
    theme: ["light", "dark", "system"],
    accent: ["blue", "graphite"],
    density: ["comfortable", "compact"],
    font: ["system", "serif", "mono"],
    motion: ["full", "reduced"],
    style: ["balanced", "concise", "detailed"],
    mode: ["ask", "plan", "code"],
  };
  return (
    <div className="settings-page">
      <span className="eyebrow">PREFERENCES</span>
      <h2>Appearance & behavior</h2>
      <p>
        Appearance is saved on this device. Response style and chat mode guide
        the model’s next reply.
      </p>
      <div className="personalization-grid">
        {Object.entries(options).map(([key, values]) => (
          <article key={key}>
            <h3>
              {key === "style"
                ? "Response style"
                : key === "mode"
                  ? "Default chat mode"
                  : key[0].toUpperCase() + key.slice(1)}
            </h3>
            <div className="choice-group">
              {values.map((item) => (
                <button
                  key={item}
                  className={value[key] === item ? "selected" : ""}
                  onClick={() => onChange({ ...value, [key]: item })}
                >
                  {item}
                </button>
              ))}
            </div>
          </article>
        ))}
      </div>
      <button onClick={() => onChange(defaults)}>Reset preferences</button>
    </div>
  );
}
