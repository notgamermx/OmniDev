import { invoke } from "@tauri-apps/api/core";
export let desktopConnection = null;
export async function initializeDesktop() {
  if (!window.__TAURI_INTERNALS__) return;
  desktopConnection = await invoke("desktop_connection");
  if (!desktopConnection) return;
  const deadline = Date.now() + 30000;
  for (let attempt = 0; attempt < 120 && Date.now() < deadline; attempt++) {
    try {
      const response = await fetch(desktopConnection.url + "/api/v1/health/", {
        headers: { Authorization: "Bearer " + desktopConnection.token },
        signal: AbortSignal.timeout(1000),
      });
      if (response.ok) {
        await invoke("engine_ready");
        return;
      }
    } catch {
      /* Wait for migrations and the local server. */
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(
    "The bundled engine did not become ready. See %USERPROFILE%\\.omnidev\\desktop-engine.log (or OMNIDEV_HOME), or connect to an engine in Connection settings.",
  );
}
