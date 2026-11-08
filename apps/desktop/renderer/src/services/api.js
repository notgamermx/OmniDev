export function normalizeEngineUrl(value) {
  if (!value.trim()) return "";
  const url = new URL(value.trim());
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.search || url.hash) throw new Error("Use an HTTP(S) engine URL without credentials, query, or fragment.");
  url.pathname = url.pathname.replace(/\/(api\/v1|app)\/?$/, "").replace(/\/+$/, "");
  return url.toString().replace(/\/$/, "");
}
async function fetchEngine(url, options) {
  try { return await fetch(url, { ...options, credentials: "omit" }); }
  catch (error) { throw new Error(error.name === "TimeoutError" ? "The engine took too long to respond. Check Connection settings and try again." : "Cannot reach the engine. Check its address, that it is running, and that remote access allows this origin."); }
}
async function readResponse(response) {
  const content = response.headers.get("content-type") || "";
  if (!content.includes("application/json")) throw new Error(`Engine returned HTTP ${response.status} without JSON. Check the engine URL and reverse proxy.`);
  const result = await response.json();
  if (!response.ok) {
    const detail = typeof result.detail === "string" ? result.detail : `Engine returned HTTP ${response.status}.`;
    throw new Error(detail + ([401,403].includes(response.status) ? " Check your engine API token in Connection settings." : ""));
  }
  return result;
}
import { desktopConnection } from "./desktop.js";
export function connection() {
  const override = localStorage.getItem("omnidev-url");
  return {
    url:
      override ||
      desktopConnection?.url ||
      ((location.protocol === "http:" || location.protocol === "https:") &&
      location.hostname !== "tauri.localhost"
        ? ""
        : "http://127.0.0.1:8000"),
    token: override
      ? sessionStorage.getItem("omnidev-token") || ""
      : desktopConnection?.token ||
        sessionStorage.getItem("omnidev-token") ||
        "",
  };
}
export async function request(path, method = "GET", body) {
  const { url, token } = connection();
  const response = await fetchEngine(url + "/api/v1" + path, {
    signal: AbortSignal.timeout(30000),
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  return readResponse(response);
}
export async function streamChat(body, onText) {
  const { url, token } = connection();
  const response = await fetchEngine(url + "/api/v1/chat/completions/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    await readResponse(response);
  }
  if (!response.headers.get("content-type")?.includes("text/event-stream")) throw new Error("Engine did not return a chat stream. Check the engine URL and reverse proxy.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let i;
      while ((i = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, i).trim();
        buffer = buffer.slice(i + 1);
        if (!line.startsWith("data:")) continue;
        const data = line.slice(5).trim();
        if (data === "[DONE]") return;
        const event = JSON.parse(data);
        if (event.error) throw new Error(event.error.detail || event.error.message || "Provider rejected the stream");
        onText(event.choices?.[0]?.delta?.content || "");
      }
    }
  } finally {
    await reader.cancel();
    reader.releaseLock();
  }
}
