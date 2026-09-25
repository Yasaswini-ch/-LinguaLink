"""Candidate generation: retrieve plausible Wikidata entities for a mention.

Tries the local alias cache first (fast, built by scripts/build_kb_index.py);
falls back to a live Wikidata search-API query for mentions not in the cache.
Either way, descriptions get enriched with real Wikipedia extracts when
available — richer text than Wikidata's terse one-liner, which measurably
improves disambiguation (see mel.data.wikidata_kb.get_wikipedia_extracts).
"""
from pathlib import Path

from mel.data.wikidata_kb import get_candidates, get_candidates_local, get_wikipedia_extracts

DEFAULT_CACHE_PATH = Path("data/kb/wikidata_aliases.parquet")


def generate_candidates(
    mention: str, lang: str, top_k: int = 10, cache_path: str | Path = DEFAULT_CACHE_PATH
) -> list[dict]:
    """Return up to `top_k` candidate entities {qid, label, description}."""
    cache_path = Path(cache_path)
    candidates = []
    if cache_path.exists():
        candidates = get_candidates_local(mention, lang, cache_path, top_k=top_k)
        for c in candidates:
            c["source"] = "local_cache"

    if not candidates:
        # get_candidates (live search API) already enriches with Wikipedia
        # extracts internally, so no need to do it again below.
        live_candidates = get_candidates(mention, lang, top_k=top_k)
        for c in live_candidates:
            c["source"] = "live_search"
        return live_candidates

    # English extracts first (measurably better disambiguation — see the
    # get_candidates docstring in wikidata_kb.py for the verified Gujarat/
    # Gujarati example), native-language extract as fallback.
    qids = [c["qid"] for c in candidates]
    extracts = get_wikipedia_extracts(qids, "en")
    if lang != "en":
        missing = [qid for qid in qids if qid not in extracts]
        if missing:
            extracts.update(get_wikipedia_extracts(missing, lang))

    for c in candidates:
        if c["qid"] in extracts:
            c["description"] = extracts[c["qid"]]
    return candidates