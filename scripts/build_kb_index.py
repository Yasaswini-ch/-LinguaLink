"""CLI: build/cache a local Wikidata alias index for faster candidate generation.

Fetches label + aliases + description for each seed QID (configs/seed_entities.yaml)
in each configured language, and writes the result to a local parquet cache used
by mel.data.wikidata_kb.get_candidates_local at inference time.

Usage:
    python scripts/build_kb_index.py --languages en hi es de
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mel.data.wikidata_kb import build_local_index  # noqa: E402
from mel.utils.config import load_config  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--languages", nargs="+", default=["en", "hi", "es", "de"])
    parser.add_argument("--seeds", default="configs/seed_entities.yaml")
    parser.add_argument("--manual-aliases", default="configs/manual_aliases.yaml")
    parser.add_argument("--output", default="data/kb/wikidata_aliases.parquet")
    args = parser.parse_args()

    seed_cfg = load_config(args.seeds)
    qids = seed_cfg["seed_qids"]

    print(f"Fetching {len(qids)} entities x {len(args.languages)} languages from Wikidata...")
    df = build_local_index(qids, args.languages)

    manual_path = Path(args.manual_aliases)
    if manual_path.exists():
        manual_cfg = load_config(manual_path)
        manual_rows = manual_cfg.get("manual_aliases", [])
        if manual_rows:
            print(f"Merging {len(manual_rows)} manual alias overrides from {manual_path}")
            df = pd.concat([df, pd.DataFrame(manual_rows)], ignore_index=True)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)

    print(f"Wrote {len(df)} rows to {out_path}")

    # SPARQL batch queries can silently return incomplete results (query
    # complexity/timeout truncation) without raising an error — check every
    # (qid, lang) pair we asked for actually got at least one row back.
    missing = [
        (qid, lang)
        for qid in qids
        for lang in args.languages
        if not ((df["qid"] == qid) & (df["lang"] == lang)).any()
    ]
    if missing:
        print(f"WARNING: {len(missing)} (qid, lang) pairs got no data back (likely query truncation):")
        for qid, lang in missing:
            print(f"  - {qid} / {lang}")
    else:
        print("All (qid, lang) pairs present.")


if __name__ == "__main__":
    main()
