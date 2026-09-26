// Backend base URL. Empty string = same-origin (works with the Vite dev proxy in
// vite.config.js, and with the FastAPI-served build in local `python run.py` mode).
// In production on Vercel, set VITE_API_BASE to the deployed backend's URL (Render).
const API_BASE = import.meta.env.VITE_API_BASE || "";

async function api(path, opts) {
  const res = await fetch(API_BASE + path, Object.assign({ headers: { "Content-Type": "application/json" } }, opts));
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch (e) {
      /* ignore */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

export const apiGet = (path) => api(path);
export const apiPost = (path, body) => api(path, { method: "POST", body: JSON.stringify(body || {}) });
export const apiPut = (path, body) => api(path, { method: "PUT", body: JSON.stringify(body || {}) });
