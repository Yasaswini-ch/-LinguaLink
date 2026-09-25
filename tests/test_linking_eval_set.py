import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mel.data.linking_eval_set import filter_by_language, load_linking_eval_set


def test_load_linking_eval_set():
    examples = load_linking_eval_set("data/processed/linking_eval_set.jsonl")
    assert len(examples) > 0
    for ex in examples:
        assert set(ex.keys()) == {"lang", "mention", "context", "gold_qid"}


def test_filter_by_language_covers_all_four():
    examples = load_linking_eval_set("data/processed/linking_eval_set.jsonl")
    for lang in ["en", "hi", "es", "de"]:
        subset = filter_by_language(examples, lang)
        assert len(subset) > 0, f"no eval examples for {lang}"
