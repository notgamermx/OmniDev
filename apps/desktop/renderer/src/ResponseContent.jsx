import React from "react";
import { downloadText } from "./services/download";

const extensions = { javascript: "js", typescript: "ts", python: "py", bash: "sh", shell: "sh", powershell: "ps1", html: "html", css: "css", json: "json", jsx: "jsx", tsx: "tsx", rust: "rs", sql: "sql", yaml: "yaml", markdown: "md" };

// Render fenced code as text, without executing HTML returned by a model.
export default function ResponseContent({ text, act, busy }) {
  const parts = [];
  const pattern = /^```([^\n`]*)\n([\s\S]*?)^```\s*$/gm;
  let offset = 0, match;
  while ((match = pattern.exec(text))) {
    if (match.index > offset) parts.push(<pre key={offset}>{text.slice(offset, match.index)}</pre>);
    const language = match[1].trim().split(/\s+/)[0].toLowerCase();
    const extension = extensions[language] || (/^[a-z0-9]{1,8}$/.test(language) ? language : "txt");
    const code = match[2];
    parts.push(<div className="code-block" key={match.index}>
      <div className="code-heading"><span>{language || "code"}</span>
        <button type="button" disabled={busy} onClick={() => act(() => downloadText(`snippet.${extension}`, code))}>↓ Download code</button>
      </div>
      <pre><code>{code}</code></pre>
    </div>);
    offset = pattern.lastIndex;
  }
  if (offset < text.length) parts.push(<pre key={offset}>{text.slice(offset)}</pre>);
  return parts;
}
