"""Build plain-dict API response shapes shared by every deployment path —
the FastAPI backend (demo/backend/main.py) and the Streamlit deployment
(streamlit_app.py) both call these, so their JSON shapes can't drift apart.
"""
from mel.data.wikidata_kb import get_entity_relations
from mel.linking.pipeline import EntityLinkingPipeline


def _candidate_dict(c) -> dict:
    return {
        "qid": c.qid,
        "label": c.label,
        "description": c.description,
        "confidence": c.confidence,
        "popularity": c.popularity,
        "popularity_norm": c.popularity_norm,
        "blended_score": c.blended_score,
        "source": c.source,
        "wikidata_url": f"https://www.wikidata.org/wiki/{c.qid}",
    }


def build_link_response(pipeline: EntityLinkingPipeline, lang: str, text: str) -> dict:
    results = pipeline.run(text, lang)

    mentions = []
    for r in results:
        entity = r.linked_entity
        candidates_out = [_candidate_dict(c) for c in entity.ranked_candidates]
        top_description = candidates_out[0]["description"] if candidates_out and not entity.is_nil else None
        mentions.append(
            {
                "text": r.mention.text,
                "label": r.mention.label,
                "start_char": r.mention.start_char,
                "end_char": r.mention.end_char,
                "qid": entity.qid or None,
                "entity_label": entity.label or None,
                "entity_description": top_description,
                "confidence": entity.confidence,
                "is_nil": entity.is_nil,
                "wikidata_url": f"https://www.wikidata.org/wiki/{entity.qid}" if entity.qid else None,
                "candidates": candidates_out,
            }
        )

    return {
        "lang": lang,
        "text": text,
        "mentions": mentions,
        "nil_threshold": pipeline.disambiguator.nil_threshold,
        "popularity_weight": pipeline.disambiguator.POPULARITY_WEIGHT,
    }


def build_relations_response(qid: str, lang: str) -> dict:
    result = get_entity_relations(qid, lang)
    coords = result["coordinates"]
    return {
        "qid": qid,
        "relations": [
            {
                "property": r["property"],
                "value": r["value"],
                "value_qid": r["value_qid"],
                "value_url": f"https://www.wikidata.org/wiki/{r['value_qid']}",
            }
            for r in result["relations"]
        ],
        "coordinates": {"lat": coords["lat"], "lon": coords["lon"]} if coords else None,
    }
