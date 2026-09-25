"""CLI: build the multilingual linking eval set from Mewsli-9 (+ Hindi, hand-authored).

Mewsli-9 doesn't cover Hindi (its 9 languages are ar/de/en/es/fa/ja/sr/ta/tr),
so this only replaces the en/es/de portion of the project's gold set; the
existing hand-authored Hindi examples are carried over unchanged.

Usage:
    python scripts/build_mewsli_eval.py --languages en es de --n-per-lang 60
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mel.data.linking_eval_set import load_linking_eval_set  # noqa: E402
from mel.data.mewsli import build_mewsli_eval_examples, download_mewsli9  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--languages", nargs="+", default=["en", "es", "de"],
                         help="Mewsli-9 languages to sample (must be a subset of its 9 languages)")
    parser.add_argument("--n-per-lang", type=int, default=60)
    parser.add_argument("--mewsli-dir", default="data/raw/mewsli-9")
    parser.add_argument("--hi-source", default="data/processed/linking_eval_set.jsonl",
                         help="existing gold set to pull hand-authored Hindi examples from")
    parser.add_argument("--output", default="data/processed/mewsli9_eval.jsonl")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    mewsli_dir = download_mewsli9(args.mewsli_dir)

    print(f"Sampling {args.n_per_lang} examples/language from Mewsli-9 for: {args.languages}")
    examples = build_mewsli_eval_examples(mewsli_dir, args.languages, args.n_per_lang, seed=args.seed)

    hi_source_path = Path(args.hi_source)
    if hi_source_path.exists():
        hi_examples = [ex for ex in load_linking_eval_set(hi_source_path) if ex["lang"] == "hi"]
        print(f"Carrying over {len(hi_examples)} hand-authored Hindi examples from {hi_source_path} "
              f"(Mewsli-9 has no Hindi split)")
        examples.extend(hi_examples)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print(f"Wrote {len(examples)} examples to {out_path}")


if __name__ == "__main__":
    main()
