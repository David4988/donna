/**
 * Where the core is and how to authenticate. Nothing secret is in source:
 *  - In Tauri, a Rust command reads ~/.donna/session.json (written by the core).
 *  - In a plain browser (dev), the core prints a URL with `#port=...&token=...`.
 */
import { invoke, isTauri } from "@tauri-apps/api/core";

export interface CoreSession {
  url: string;
  token: string;
}

const STORAGE_KEY = "donna.session";

export function parseSessionHash(hash: string): CoreSession | null {
  const params = new URLSearchParams(hash.replace(/^#/, ""));
  const port = Number(params.get("port"));
  const token = params.get("token");
  if (!Number.isInteger(port) || port <= 0 || port > 65535 || !token) return null;
  return { url: `ws://127.0.0.1:${port}`, token };
}

function fromBrowser(): CoreSession | null {
  const fromHash = parseSessionHash(window.location.hash);
  if (fromHash) {
    // Keep it for reloads in this tab, but get the token out of the address bar.
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(fromHash));
    history.replaceState(null, "", window.location.pathname + window.location.search);
    return fromHash;
  }
  const stored = sessionStorage.getItem(STORAGE_KEY);
  return stored ? (JSON.parse(stored) as CoreSession) : null;
}

export async function loadSession(): Promise<CoreSession | null> {
  if (isTauri()) {
    try {
      const info = await invoke<{ port: number; token: string }>("core_session");
      return { url: `ws://127.0.0.1:${info.port}`, token: info.token };
    } catch {
      return null; // core not running yet
    }
  }
  return fromBrowser();
}
