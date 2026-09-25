"""Query Wikidata for entity labels, aliases, and descriptions.

Lookup paths:
  - `get_candidates`: live entity search via the `wbsearchentities` MediaWiki
    API — fuzzy, popularity-ranked matching (handles surnames, partial
    names, minor misspellings), used as an online fallback for mentions not
    present in the local cache. Preferred over raw SPARQL for this purpose:
    SPARQL's exact-literal alias match returns whichever matching entity
    happens to come back first (we saw it pick an obscure "Elon Musk" and a
    non-notable "Modi" over the well-known ones), while wbsearchentities
    ranks by relevance/notability and returns the description directly, no
    second query needed.
  - `get_candidates_local`: fast lookup against a parquet cache built by
    `scripts/build_kb_index.py` (labels/aliases/descriptions for a seed set
    of QIDs, across all configured languages).
  - `fetch_entity_details` / `build_local_index`: SPARQL-based bulk fetch
    used only for building that local cache (batch VALUES queries are more
    efficient there than one search-API call per entity).
"""
import time
import urllib.error
import urllib.parse
from pathlib import Path

import pandas as pd
from SPARQLWrapper import SPARQLWrapper, JSON

from mel.utils.http import get_json_with_retry as _get_json_with_retry

WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
WIKIDATA_SEARCH_API = "https://www.wikidata.org/w/api.php"
WIKIPEDIA_SUMMARY_API = "https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"

ENTITY_DETAILS_QUERY = """
SELECT ?item ?lang ?label ?alias ?description WHERE {{
  VALUES ?item {{ {values} }}
  VALUES ?lang {{ {langs} }}
  ?item rdfs:label ?label . FILTER(LANG(?label) = ?lang)
  OPTIONAL {{ ?item skos:altLabel ?alias . FILTER(LANG(?alias) = ?lang) }}
  OPTIONAL {{ ?item schema:description ?description . FILTER(LANG(?description) = ?lang) }}
}}
"""


def get_candidates(mention: str, lang: str, top_k: int = 10) -> list[dict]:
    """Return candidate Wikidata entities (QID, label, description) for a
    mention, via the wbsearchentities search API.

    Returns [] (rather than raising) on any network/HTTP failure so callers
    (batch eval, the demo) degrade to NIL for that mention instead of
    crashing the whole run.
    """
    data = _get_json_with_retry(
        WIKIDATA_SEARCH_API,
        {"action": "wbsearchentities", "search": mention, "language": lang, "format": "json", "limit": top_k},
    )
    if data is None:
        return []

    candidates = [
        {
            "qid": item["id"],
            "label": item.get("label", item.get("display", {}).get("label", {}).get("value", "")),
            "description": item.get("description", item.get("display", {}).get("description", {}).get("value", "")),
        }
        for item in data.get("search", [])
    ]

    # Enrich only the top few candidates — search results are already
    # relevance-ranked, and each enriched candidate costs 2-3 extra HTTP
    # calls, which adds up fast against the action API's rate limit.
    enrich_qids = [c["qid"] for c in candidates[:5]]
    sitelink_counts = get_sitelink_counts(enrich_qids)

    # Always prefer the ENGLISH Wikipedia extract, even when the mention/
    # search language is not English — English extracts are consistently
    # longer and more descriptive than native-language ones for many
    # entities in this KB, which generally gives the embedding model more to
    # match against. NOTE: this does NOT fix the Gujarat/Gujarati case
    # (Hindi "गुजरात") — tested directly against the real pipeline with
    # fully English context AND descriptions on both sides, Gujarati still
    # outranks Gujarat (0.574 vs 0.508). See docs/LATE_STAGE_FINDINGS.md; an
    # earlier claim that English-language translation fixed this case was
    # based on unrepresentative hand-written test data and was wrong — the
    # real cause is that Gujarat's own English description contains the
    # literal word "Gujarat", which Gujarati's description shares by root,
    # so the two candidates overlap lexically regardless of language.
    # Falls back to a native-language extract only for candidates with no
    # English Wikipedia article at all.
    extracts = get_wikipedia_extracts(enrich_qids, "en")
    if lang != "en":
        missing = [qid for qid in enrich_qids if qid not in extracts]
        if missing:
            extracts.update(get_wikipedia_extracts(missing, lang))

    for c in candidates:
        c["popularity"] = sitelink_counts.get(c["qid"], 0)
        # Prefer the richer Wikipedia extract over Wikidata's terse one-liner
        # when we have one — short generic descriptions (e.g. "American
        # businessman (born 1971)") give the embedding model little to match
        # against a mention's context; a real intro paragraph gives it much
        # more to work with.
        if c["qid"] in extracts:
            c["description"] = extracts[c["qid"]]
    return candidates


def get_sitelink_counts(qids: list[str]) -> dict[str, int]:
    """Fetch each QID's Wikidata sitelink count (how many Wikipedia language
    editions have an article on it) — a simple, effective notability proxy.
    E.g. the real Lionel Messi (Q615) has 225 sitelinks; an unrelated,
    obscure entity that also happens to be labeled "Messi" has 2. Used as a
    tiebreaker in disambiguation when semantic similarity scores are close.
    Returns {} on failure (disambiguation just skips the popularity term).
    """
    if not qids:
        return {}
    data = _get_json_with_retry(
        WIKIDATA_SEARCH_API,
        {"action": "wbgetentities", "ids": "|".join(qids), "props": "sitelinks", "format": "json"},
    )
    if data is None:
        return {}
    return {qid: len(ent.get("sitelinks", {})) for qid, ent in data.get("entities", {}).items()}


def get_wikipedia_extracts(qids: list[str], lang: str, max_chars: int = 400) -> dict[str, str]:
    """Fetch a real Wikipedia intro-paragraph extract per QID (in `lang`'s
    Wikipedia), truncated to `max_chars`. Much richer disambiguation context
    than Wikidata's one-line description. Two-step: batch-fetch each QID's
    Wikipedia article title via Wikidata's sitelinks, then call Wikipedia's
    REST summary API per title (that API has no batch endpoint). Skips QIDs
    with no article in this language; returns {} entirely on failure — the
    caller just keeps the shorter Wikidata description in that case.
    """
    if not qids:
        return {}
    sitekey = f"{lang}wiki"
    data = _get_json_with_retry(
        WIKIDATA_SEARCH_API,
        {"action": "wbgetentities", "ids": "|".join(qids), "props": "sitelinks", "sitefilter": sitekey, "format": "json"},
    )
    if data is None:
        return {}

    titles = {
        qid: ent["sitelinks"][sitekey]["title"]
        for qid, ent in data.get("entities", {}).items()
        if sitekey in ent.get("sitelinks", {})
    }

    extracts = {}
    for qid, title in titles.items():
        url = WIKIPEDIA_SUMMARY_API.format(lang=lang, title=urllib.parse.quote(title.replace(" ", "_")))
        summary = _get_json_with_retry(url, {}, max_retries=1, retry_wait_seconds=2)
        if summary and summary.get("extract"):
            extracts[qid] = summary["extract"][:max_chars]
    return extracts


# Curated subset of common Wikidata properties worth surfacing in a
# "Relations" view — covers people, places, and organizations without
# overwhelming the UI. Values that are entity references (not plain
# numbers/strings/dates) get resolved to labels; unlisted property types
# (dates, quantities, coordinates) are skipped for simplicity.
RELATION_PROPERTIES = {
    "P31": "instance of",
    "P21": "sex or gender",
    "P27": "country of citizenship",
    "P106": "occupation",
    "P17": "country",
    "P159": "headquarters location",
    "P112": "founded by",
    "P169": "chief executive officer",
    "P571": "inception",
    "P36": "capital",
}


COORDINATE_PROPERTY = "P625"  # "coordinate location" — only meaningful for LOC-type entities (cities, countries, etc.)


def get_entity_relations(qid: str, lang: str, max_relations: int = 8) -> dict:
    """Fetch a curated set of Wikidata relations (claims) for one entity,
    e.g. Messi -> country of citizenship -> Argentina, plus its coordinate
    location if it has one (P625 — a "globecoordinate" value, not an entity
    reference, so it's pulled separately from the entity-reference relations
    below). Only called lazily (when a user opens the Relations tab for a
    specific entity), not for every candidate, to keep request volume down.

    Returns {"relations": [{property, value, value_qid}], "coordinates":
    {"lat", "lon"} | None}. Relation property/value are labeled in `lang`
    (falling back to English label resolution isn't attempted here — keep it
    simple, Wikidata's own label service handles most languages).
    """
    data = _get_json_with_retry(WIKIDATA_SEARCH_API, {"action": "wbgetentities", "ids": qid, "props": "claims", "format": "json"})
    if data is None:
        return {"relations": [], "coordinates": None}

    claims = data.get("entities", {}).get(qid, {}).get("claims", {})

    coordinates = None
    coord_claim = claims.get(COORDINATE_PROPERTY, [])
    if coord_claim:
        value = coord_claim[0].get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(value, dict) and "latitude" in value and "longitude" in value:
            coordinates = {"lat": value["latitude"], "lon": value["longitude"]}

    rows = []  # (prop_id, value_qid) pairs, entity-reference values only
    for prop_id in RELATION_PROPERTIES:
        for claim in claims.get(prop_id, [])[:1]:  # first value only, keep it compact
            snak = claim.get("mainsnak", {})
            value = snak.get("datavalue", {}).get("value")
            if isinstance(value, dict) and "id" in value:  # wikibase-entityid
                rows.append((prop_id, value["id"]))
        if len(rows) >= max_relations:
            break

    if not rows:
        return {"relations": [], "coordinates": coordinates}

    label_ids = list({prop_id for prop_id, _ in rows} | {value_qid for _, value_qid in rows})
    label_data = _get_json_with_retry(
        WIKIDATA_SEARCH_API,
        {"action": "wbgetentities", "ids": "|".join(label_ids), "props": "labels", "languages": lang, "format": "json"},
    )
    labels = {}
    if label_data:
        for eid, ent in label_data.get("entities", {}).items():
            lbl = ent.get("labels", {}).get(lang, {}).get("value")
            labels[eid] = lbl or eid

    relations = [
        {
            "property": RELATION_PROPERTIES.get(prop_id, labels.get(prop_id, prop_id)),
            "value": labels.get(value_qid, value_qid),
            "value_qid": value_qid,
        }
        for prop_id, value_qid in rows
    ]
    return {"relations": relations, "coordinates": coordinates}


def _query_with_retry(sparql: SPARQLWrapper, max_retries: int = 3, retry_wait_seconds: int = 65) -> dict:
    """Run a SPARQL query, retrying on HTTP 429 (rate limit) with a wait long
    enough to respect Wikidata's "1 request / min" outage-mode throttle.
    """
    for attempt in range(max_retries + 1):
        try:
            return sparql.query().convert()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries:
                print(f"Wikidata rate-limited (429); waiting {retry_wait_seconds}s before retry "
                      f"{attempt + 1}/{max_retries}...")
                time.sleep(retry_wait_seconds)
                continue
            raise


def fetch_entity_details(qids: list[str], langs: list[str]) -> pd.DataFrame:
    """Fetch label + all aliases + description for each (qid, lang) pair via SPARQL.

    Returns a long-form DataFrame: columns [qid, lang, label, alias, description],
    with one row per (qid, lang, alias) — an entity with 3 aliases in a language
    yields 3 rows sharing the same label/description.
    """
    values = " ".join(f"wd:{qid}" for qid in qids)
    lang_values = " ".join(f'"{lang}"' for lang in langs)

    sparql = SPARQLWrapper(WIKIDATA_ENDPOINT, agent="mel-project/0.1")
    sparql.setQuery(ENTITY_DETAILS_QUERY.format(values=values, langs=lang_values))
    sparql.setReturnFormat(JSON)
    results = _query_with_retry(sparql)

    rows = []
    for row in results["results"]["bindings"]:
        rows.append(
            {
                "qid": row["item"]["value"].rsplit("/", 1)[-1],
                "lang": row["lang"]["value"],
                "label": row.get("label", {}).get("value", ""),
                "alias": row.get("alias", {}).get("value", ""),
                "description": row.get("description", {}).get("value", ""),
            }
        )
    return pd.DataFrame(rows)


def build_local_index(qids: list[str], langs: list[str], batch_size: int = 10) -> pd.DataFrame:
    """Build the full local alias cache by batching seed QIDs through fetch_entity_details."""
    frames = []
    for i in range(0, len(qids), batch_size):
        batch = qids[i : i + batch_size]
        frames.append(fetch_entity_details(batch, langs))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["qid", "lang", "label", "alias", "description"]
    )


def get_candidates_local(mention: str, lang: str, cache_path: str | Path, top_k: int = 10) -> list[dict]:
    """Look up candidates from the local parquet cache.

    Tries an exact label/alias match first (case-insensitive); if that finds
    nothing, falls back to a substring match (e.g. mention "Apple" against
    label "Apple Inc.") — real alias tables are incomplete, and this avoids
    an unnecessary live-SPARQL fallback for entities we already have cached.
    """
    df = pd.read_parquet(cache_path)
    df = df[df["lang"] == lang]

    mention_lower = mention.lower()
    labels_lower = df["label"].str.lower()
    aliases_lower = df["alias"].str.lower()

    exact_mask = (labels_lower == mention_lower) | (aliases_lower == mention_lower)
    # startswith, not contains: catches "Apple" -> "Apple Inc." (real match),
    # but not "Deutschland" -> an unrelated entity's composite alias like
    # "Berlin, Deutschland" (city-comma-country naming convention) — contains
    # matched that false positive and it beat the correct candidate in
    # disambiguation because Berlin's description also happens to mention
    # "Deutschland" in passing.
    substring_mask = labels_lower.str.startswith(mention_lower) | aliases_lower.str.startswith(mention_lower)
    # Union, not fallback: an exact match on one candidate (e.g. "apple" the
    # fruit) must not hide a substring-only match on another (e.g. "Apple Inc."
    # the company) — both are valid disambiguation candidates for "Apple".
    matches = df[exact_mask | substring_mask].drop_duplicates(subset="qid")

    candidates = [
        {"qid": row["qid"], "label": row["label"], "description": row["description"]}
        for _, row in matches.head(top_k).iterrows()
    ]
    return candidates
