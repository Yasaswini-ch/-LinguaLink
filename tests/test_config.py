import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mel.utils.config import load_config, load_languages


def test_load_languages():
    langs = load_languages("configs/languages.yaml")
    codes = [l["code"] for l in langs]
    assert codes == ["en", "hi", "es", "de"]


def test_load_ner_config():
    cfg = load_config("configs/ner_xlmr.yaml")
    assert cfg["model"]["base_checkpoint"] == "xlm-roberta-base"
    assert cfg["data"]["languages"] == ["en", "hi", "es", "de"]


def test_load_linking_config():
    cfg = load_config("configs/linking.yaml")
    assert cfg["disambiguation"]["nil_threshold"] == 0.1
    assert cfg["candidate_generation"]["top_k"] == 10
