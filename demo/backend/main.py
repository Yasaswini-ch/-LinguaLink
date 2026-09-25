"""FastAPI backend for the multilingual entity linking demo.

Run with:
    uvicorn demo.backend.main:app --reload --port 8000

Exposes POST /link, consumed by the React frontend in demo/frontend.
"""
import os
import sys
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from mel.data.wikidata_kb import get_entity_relations  # noqa: E402
from mel.linking.pipeline import EntityLinkingPipeline  # noqa: E402
from mel.utils.config import load_config  # noqa: E402

app = FastAPI(title="Multilingual Entity Linking API")

# Comma-separated list of allowed frontend origins, e.g.
# "https://your-app.vercel.app,https://your-app-git-main.vercel.app".
# Defaults to the Vite dev server so local development needs no setup.
_allowed_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPPORTED_LANGUAGES = {"en": "English", "hi": "Hindi", "es": "Spanish", "de": "German"}


class LinkRequest(BaseModel):
    lang: str
    text: str


class CandidateOut(BaseModel):
    qid: str
    label: str
    description: str
    confidence: float          # raw cosine similarity (semantic score)
    popularity: int            # raw Wikidata sitelink count
    popularity_norm: float     # log1p(popularity), normalized 0-1 within this candidate set
    blended_score: float       # confidence + popularity_weight * popularity_norm — the actual ranking key
    source: str                # "local_cache" or "live_search"
    wikidata_url: str


class LinkedMentionOut(BaseModel):
    text: str
    label: str
    start_char: int
    end_char: int
    qid: str | None
    entity_label: str | None
    entity_description: str | None
    confidence: float
    is_nil: bool
    wikidata_url: str | None
    candidates: list[CandidateOut]


class LinkResponse(BaseModel):
    lang: str
    text: str
    mentions: list[LinkedMentionOut]
    nil_threshold: float       # raw semantic-similarity cutoff below which the top match becomes NIL
    popularity_weight: float   # weight applied to popularity_norm when computing blended_score


class RelationOut(BaseModel):
    property: str
    value: str
    value_qid: str
    value_url: str


class CoordinatesOut(BaseModel):
    lat: float
    lon: float


class RelationsResponse(BaseModel):
    qid: str
    relations: list[RelationOut]
    coordinates: CoordinatesOut | None


@lru_cache(maxsize=1)
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


@app.get("/languages")
def languages():
    return SUPPORTED_LANGUAGES


@app.post("/link", response_model=LinkResponse)
def link(req: LinkRequest):
    pipeline = get_pipeline()
    results = pipeline.run(req.text, req.lang)

    mentions = []
    for r in results:
        entity = r.linked_entity
        candidates_out = [
            CandidateOut(
                qid=c.qid,
                label=c.label,
                description=c.description,
                confidence=c.confidence,
                popularity=c.popularity,
                popularity_norm=c.popularity_norm,
                blended_score=c.blended_score,
                source=c.source,
                wikidata_url=f"https://www.wikidata.org/wiki/{c.qid}",
            )
            for c in entity.ranked_candidates
        ]
        top_description = candidates_out[0].description if candidates_out and not entity.is_nil else None
        mentions.append(
            LinkedMentionOut(
                text=r.mention.text,
                label=r.mention.label,
                start_char=r.mention.start_char,
                end_char=r.mention.end_char,
                qid=entity.qid or None,
                entity_label=entity.label or None,
                entity_description=top_description,
                confidence=entity.confidence,
                is_nil=entity.is_nil,
                wikidata_url=f"https://www.wikidata.org/wiki/{entity.qid}" if entity.qid else None,
                candidates=candidates_out,
            )
        )

    return LinkResponse(
        lang=req.lang,
        text=req.text,
        mentions=mentions,
        nil_threshold=pipeline.disambiguator.nil_threshold,
        popularity_weight=pipeline.disambiguator.POPULARITY_WEIGHT,
    )


@app.get("/entity/{qid}/relations", response_model=RelationsResponse)
def entity_relations(qid: str, lang: str = "en"):
    # Fetched lazily (only when the UI's Relations tab is opened for this
    # entity), not bundled into /link — keeps per-query request volume down
    # against Wikidata's rate limit.
    result = get_entity_relations(qid, lang)
    coords = result["coordinates"]
    return RelationsResponse(
        qid=qid,
        relations=[
            RelationOut(
                property=r["property"],
                value=r["value"],
                value_qid=r["value_qid"],
                value_url=f"https://www.wikidata.org/wiki/{r['value_qid']}",
            )
            for r in result["relations"]
        ],
        coordinates=CoordinatesOut(lat=coords["lat"], lon=coords["lon"]) if coords else None,
    )
