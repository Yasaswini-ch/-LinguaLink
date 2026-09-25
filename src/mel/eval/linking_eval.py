"""Evaluate linking accuracy: predicted QID vs. gold QID (or NIL) per mention."""
from mel.linking.candidates import generate_candidates
from mel.linking.disambiguate import Disambiguator


def evaluate_linking(predictions: list[str], gold: list[str]) -> dict:
    assert len(predictions) == len(gold), "predictions/gold length mismatch"
    correct = sum(p == g for p, g in zip(predictions, gold))
    total = len(gold)
    return {
        "accuracy": correct / total if total else 0.0,
        "correct": correct,
        "total": total,
    }


def run_linking_eval(disambiguator: Disambiguator, examples: list[dict], cache_path: str) -> dict:
    """Run candidate generation + disambiguation over gold examples and score accuracy.

    Each example: {lang, mention, context, gold_qid}.
    """
    predictions, gold = [], []
    for ex in examples:
        candidates = generate_candidates(ex["mention"], ex["lang"], cache_path=cache_path)
        linked = disambiguator.rank(ex["context"], candidates)
        predictions.append(linked.qid)
        gold.append(ex["gold_qid"])

    return evaluate_linking(predictions, gold)
