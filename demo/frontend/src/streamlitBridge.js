// Bridges Streamlit's request/rerun component protocol to look like a
// normal async request/response call, so apiClient.js can use it as a
// drop-in alternative to fetch() when this bundle is embedded as a
// Streamlit custom component (VITE_TRANSPORT=streamlit) instead of served
// standalone against demo/backend's FastAPI server.
//
// Protocol: this frontend calls Streamlit.setComponentValue({id, type,
// ...payload}) to send a request "up"; streamlit_app.py runs the pipeline
// on its next rerun and sends the result back "down" as the `response`
// prop, matching by id. See demo/streamlit_component/__init__.py and
// streamlit_app.py for the Python side.
import { Streamlit } from "streamlit-component-lib";

let requestCounter = 0;
const pending = new Map(); // id -> { resolve, reject }
let lastSeenResponseId = null;

export function initStreamlitBridge() {
  Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, (event) => {
    const args = event.detail.args || {};
    const response = args.response;

    if (response && response.id !== lastSeenResponseId && pending.has(response.id)) {
      lastSeenResponseId = response.id;
      const { resolve, reject } = pending.get(response.id);
      pending.delete(response.id);
      if (response.error) reject(new Error(response.error));
      else resolve(response.data);
    }
  });

  Streamlit.setComponentReady();

  // RENDER_EVENT only fires when Python pushes new props, but most of this
  // app's content changes (tabs, expanding "view all candidates", loading
  // states, results appearing) are pure client-side React state with no
  // round trip to Python at all — a ResizeObserver on the whole document is
  // what actually keeps the iframe sized to fit, including the very first
  // paint (which otherwise races ahead of React's initial render, since
  // this bridge initializes before ReactDOM.render() is even called).
  const resizeObserver = new ResizeObserver(() => {
    Streamlit.setFrameHeight();
  });
  resizeObserver.observe(document.body);

  Streamlit.setFrameHeight();
}

export function sendStreamlitRequest(type, payload) {
  return new Promise((resolve, reject) => {
    const id = `${Date.now()}-${++requestCounter}`;
    pending.set(id, { resolve, reject });
    Streamlit.setComponentValue({ id, type, ...payload });
  });
}
