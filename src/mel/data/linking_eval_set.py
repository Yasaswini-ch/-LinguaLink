"""Load the hand-authored multilingual linking evaluation set.

Each line is a JSON object: {lang, mention, context, gold_qid}. This is a
small starter gold set covering the project's worked disambiguation examples
(Apple/Amazon/Modi/Merkel/Berlin across en/es/de/hi) — swap in Mewsli-9 or a
larger weakly-labeled Wikipedia-hyperlink set for a production-scale eval.
"""
import json
from pathlib import Path


def load_linking_eval_set(path: str | Path = "data/processed/linking_eval_set.jsonl") -> list[dict]:
    examples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))
    return examples


def filter_by_language(examples: list[dict], lang: str) -> list[dict]:
    return [ex for ex in examples if ex["lang"] == lang]
