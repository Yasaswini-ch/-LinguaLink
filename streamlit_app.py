"""Streamlit Community Cloud entrypoint — a self-contained, single-process
deployment of the LinguaLink demo. Runs the exact same pipeline as
demo/backend/main.py (via mel.linking.serialize, shared by both), but with
no separate FastAPI server, no CORS config, and no HTTP hop: the embedded
React UI (demo/streamlit_component) sends requests up via Streamlit's
component bridge, this script runs the pipeline directly in-process on
each rerun, and sends the result back down.

Run locally with:
    streamlit run streamlit_app.py
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from mel.linking.pipeline import EntityLinkingPipeline  # noqa: E402
from mel.linking.serialize import build_link_response, build_relations_response  # noqa: E402
from mel.utils.config import load_config  # noqa: E402

from demo.streamlit_component import lingualink_ui  # noqa: E402

st.set_page_config(page_title="LinguaLink", layout="wide")
# The embedded app already has its own navbar/hero; trim Streamlit's default
# block padding so it doesn't add a second layer of empty space above it.
st.markdown(
    # padding-top keeps clear of Streamlit's floating toolbar (Stop/Deploy);
    # 0 there clipped the embedded app's own navbar underneath it.
    "<style>.block-container { padding-top: 3.5rem; padding-bottom: 0; }</style>",
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner="Loading models (first run only — this can take a minute)...")
def get_pipeline() -> EntityLinkingPipeline:
    ner_cfg = load_config("configs/ner_xlmr.yaml")
    linking_cfg = load_config("configs/linking.yaml")
    return EntityLinkingPipeline(
        ner_model_path=ner_cfg["inference_model_path"],
        embedding_model=linking_cfg["disambiguation"]["embedding_model"],
        nil_threshold=linking_cfg["disambiguation"]["nil_threshold"],
        context_window_tokens=linking_cfg["disambiguation"]["context_window_tokens"],
        kb_cache_path=linking_cfg["candidate_generation"]["local_dump_path"],
    )


pipeline = get_pipeline()

if "ll_last_request_id" not in st.session_state:
    st.session_state.ll_last_request_id = None
if "ll_response" not in st.session_state:
    st.session_state.ll_response = None

request = lingualink_ui(response=st.session_state.ll_response, key="lingualink")

if request and request.get("id") != st.session_state.ll_last_request_id:
    st.session_state.ll_last_request_id = request["id"]
    try:
        if request["type"] == "link":
            data = build_link_response(pipeline, request["lang"], request["text"])
        elif request["type"] == "relations":
            data = build_relations_response(request["qid"], request["lang"])
        else:
            raise ValueError(f"unknown request type: {request.get('type')!r}")
        st.session_state.ll_response = {"id": request["id"], "data": data}
    except Exception as e:  # noqa: BLE001 — surface any pipeline failure to the frontend rather than crashing the app
        st.session_state.ll_response = {"id": request["id"], "error": str(e)}
    st.rerun()
