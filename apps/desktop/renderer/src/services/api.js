import { desktopConnection } from "./desktop";
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
  const response = await fetch(url + "/api/v1" + path, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const result = await response.json();
  if (!response.ok)
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : JSON.stringify(result.detail || result),
    );
  return result;
}
export async function streamChat(body, onText) {
  const { url, token } = connection();
  const response = await fetch(url + "/api/v1/chat/completions/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const result = await response.json();
    throw new Error(result.detail || "Chat failed");
  }
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
        if (event.error) throw new Error(event.error.detail);
        onText(event.choices?.[0]?.delta?.content || "");
      }
    }
  } finally {
    await reader.cancel();
    reader.releaseLock();
  }
}
