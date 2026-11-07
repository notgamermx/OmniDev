import { invoke } from "@tauri-apps/api/core";

export async function downloadText(name, content, type = "text/plain;charset=utf-8") {
  const filename = name.split(/[\\/]/).pop().replace(/[<>:"|?*\x00-\x1f]/g, "_") || "omnidev.txt";
  if (window.__TAURI_INTERNALS__) {
    return invoke("export_text", { name: filename, content });
  }
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}
