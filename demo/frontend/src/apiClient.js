// Single place App.jsx calls out to the backend, so it doesn't need to know
// whether it's running standalone (talking to demo/backend's FastAPI server
// over HTTP) or embedded as a Streamlit custom component (talking to
// streamlit_app.py via the request/rerun bridge in streamlitBridge.js).
// Picked at build time via VITE_TRANSPORT, since the two deployments ship
// as separate bundles (see README.md's Deployment section). The dynamic
// import is dead-code-eliminated from the HTTP bundle: VITE_TRANSPORT is
// inlined as a literal at build time, so the branch below is unreachable
// there and Rollup drops the streamlit-component-lib chunk entirely.
const TRANSPORT = import.meta.env.VITE_TRANSPORT || "http";
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

async function streamlitRequest(type, payload) {
  const { sendStreamlitRequest } = await import("./streamlitBridge.js");
  return sendStreamlitRequest(type, payload);
}

export async function linkText(lang, text) {
  if (TRANSPORT === "streamlit") {
    return streamlitRequest("link", { lang, text });
  }
  const res = await fetch(`${API_BASE_URL}/link`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lang, text }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getRelations(qid, lang) {
  if (TRANSPORT === "streamlit") {
    return streamlitRequest("relations", { qid, lang });
  }
  const res = await fetch(`${API_BASE_URL}/entity/${qid}/relations?lang=${lang}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
