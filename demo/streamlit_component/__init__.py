"""Streamlit custom-component wrapper embedding the LinguaLink React frontend
unchanged (same CSS, disambiguation graphs, tabs, etc.) inside a Streamlit
app, instead of rebuilding the UI with Streamlit's native widgets.

The component serves the prebuilt static bundle in `frontend_dist/` (built
via `npm run build -- --outDir ../streamlit_component/frontend_dist` with
`VITE_TRANSPORT=streamlit`, from demo/frontend — see README.md's Deployment
section). That bundle talks to Python via `streamlit-component-lib`'s
request/rerun bridge (demo/frontend/src/streamlitBridge.js) rather than
`fetch()`, since there is no separate backend server in this deployment
path — see streamlit_app.py for the Python side of that bridge.
"""
from pathlib import Path

import streamlit.components.v1 as components

_BUILD_DIR = Path(__file__).parent / "frontend_dist"

_component_func = components.declare_component("lingualink_ui", path=str(_BUILD_DIR))


def lingualink_ui(response: dict | None, key: str | None = None):
    """Render the LinguaLink UI and return the latest {id, type, ...}
    request sent up from the frontend (or None if nothing has been sent yet
    this session). `response` is threaded back down as a prop so the
    frontend can resolve the pending request whose id it matches.
    """
    return _component_func(response=response, key=key, default=None)
