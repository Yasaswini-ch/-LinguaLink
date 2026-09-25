"""Load Mewsli-9 (Botha, Shan & Gillick, 2020) for the multilingual linking eval set.

Mewsli-9 ships `docs.tsv` (docid, title, curid, revid, url, text_md5 — no
article body) and `mentions.tsv` (docid, position, length, mention, lang,
qid, ...) per language, joinable on `docid`. It does NOT include Hindi (its
9 languages are ar/de/en/es/fa/ja/sr/ta/tr), so it only replaces the en/de/es
portion of this project's gold set — the hand-authored `hi` examples in
`data/processed/linking_eval_set.jsonl` are kept as-is.

Since `docs.tsv` has no body text, and reproducing the dataset's original
byte-offset extraction exactly would require re-running the same
wikiextractor pipeline used to build it, this loader instead fetches each
doc's current plain-text extract live from Wikinews (via `curid`, the same
action-API pattern used in `wikidata_kb.py` for Wikipedia) and locates the
mention by substring search rather than by the dataset's `position` field.
This is an approximation — a small fraction of articles may have been
edited since the 2019-01-01 dump Mewsli-9 was built from, in which case the
mention substring search simply fails to find it and that example is
skipped — but it avoids re-implementing the original extraction pipeline
just to reproduce exact offsets.
"""
import random
import time
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

import pandas as pd

from mel.utils.http import get_json_with_retry

MEWSLI_LANGUAGES = ["ar", "de", "en", "es", "fa", "ja", "sr", "ta", "tr"]
MEWSLI_ZIP_URL = "https://storage.googleapis.com/gresearch/mewsli/mewsli-9.zip"
WIKINEWS_API = "https://{lang}.wikinews.org/w/api.php"

CONTEXT_WINDOW_CHARS = 200


def download_mewsli9(dest_dir: str | Path) -> Path:
    """Download and unzip Mewsli-9 into `dest_dir` (idempotent: skips if already present)."""
    dest_dir = Path(dest_dir)
    if (dest_dir / "en" / "mentions.tsv").exists():
        return dest_dir
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dest_dir / "mewsli-9.zip"
    print(f"Downloading Mewsli-9 from {MEWSLI_ZIP_URL} ...")
    urlretrieve(MEWSLI_ZIP_URL, zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest_dir)
    zip_path.unlink()
    return dest_dir


def load_mewsli_mentions(mewsli_dir: str | Path, lang: str) -> pd.DataFrame:
    """Load one language's mentions joined with their doc metadata (title, curid, url)."""
    mewsli_dir = Path(mewsli_dir)
    docs = pd.read_csv(mewsli_dir / lang / "docs.tsv", sep="\t")
    mentions = pd.read_csv(mewsli_dir / lang / "mentions.tsv", sep="\t")
    return mentions.merge(docs, on="docid", suffixes=("", "_doc"))


def _fetch_wikinews_extracts(curids: list[int], lang: str) -> dict[int, str]:
    """Batch-fetch current plain-text extracts for a list of Wikinews page ids."""
    if not curids:
        return {}
    extracts = {}
    batch_size = 20
    for i in range(0, len(curids), batch_size):
        batch = curids[i : i + batch_size]
        data = get_json_with_retry(
            WIKINEWS_API.format(lang=lang),
            {
                "action": "query",
                "prop": "extracts",
                "explaintext": 1,
                "pageids": "|".join(str(c) for c in batch),
                "format": "json",
            },
            max_retries=4,
            retry_wait_seconds=8,
        )
        # Anonymous Wikinews action-API requests get throttled under
        # back-to-back batches even when each individual call eventually
        # succeeds via retry — a fixed small delay between batches keeps us
        # under that threshold instead of relying on 429 retries alone.
        time.sleep(1.5)
        if data is None:
            continue
        for pageid, page in data.get("query", {}).get("pages", {}).items():
            extract = page.get("extract")
            if extract:
                extracts[int(pageid)] = extract
    return extracts


def _context_window(text: str, mention: str) -> str | None:
    idx = text.find(mention)
    if idx == -1:
        return None
    start = max(0, idx - CONTEXT_WINDOW_CHARS)
    end = idx + len(mention) + CONTEXT_WINDOW_CHARS
    return text[start:end]


def build_mewsli_eval_examples(
    mewsli_dir: str | Path, languages: list[str], n_per_lang: int, seed: int = 42
) -> list[dict]:
    """Sample `n_per_lang` mentions per language, fetch live context, return
    [{lang, mention, context, gold_qid}] in the project's standard eval format.

    Sampling is capped per unique doc (at most one mention per article) so the
    resulting set isn't dominated by a handful of long articles, then fetches
    each sampled doc's extract in batches and keeps only mentions actually
    findable in that extract.
    """
    rng = random.Random(seed)
    examples = []

    for lang in languages:
        df = load_mewsli_mentions(mewsli_dir, lang)
        df = df.sort_values("docid").drop_duplicates(subset="docid")  # >=1 mention per doc, capped at 1
        sample_n = min(n_per_lang * 4, len(df))  # oversample: some won't resolve via live substring search
        sampled = df.sample(n=sample_n, random_state=rng.randint(0, 2**31))

        extracts = _fetch_wikinews_extracts(sampled["curid"].tolist(), lang)

        kept = 0
        for _, row in sampled.iterrows():
            if kept >= n_per_lang:
                break
            extract = extracts.get(int(row["curid"]))
            if not extract:
                continue
            context = _context_window(extract, row["mention"])
            if context is None:
                continue
            examples.append(
                {"lang": lang, "mention": row["mention"], "context": context, "gold_qid": row["qid"]}
            )
            kept += 1

        print(f"  {lang}: kept {kept}/{n_per_lang} requested (from {sample_n} sampled docs)")

    return examples
