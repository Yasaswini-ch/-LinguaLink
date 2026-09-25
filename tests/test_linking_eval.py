import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mel.eval.linking_eval import evaluate_linking


def test_evaluate_linking_all_correct():
    result = evaluate_linking(["Q1", "Q2", "Q3"], ["Q1", "Q2", "Q3"])
    assert result["accuracy"] == 1.0
    assert result["correct"] == 3


def test_evaluate_linking_partial():
    result = evaluate_linking(["Q1", "Q9", "Q3"], ["Q1", "Q2", "Q3"])
    assert result["correct"] == 2
    assert result["total"] == 3
    assert abs(result["accuracy"] - 2 / 3) < 1e-9
