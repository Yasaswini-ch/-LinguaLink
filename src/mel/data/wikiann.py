"""Load and preprocess the WikiAnn multilingual NER dataset.

Uses the `unimelb-nlp/wikiann` mirror on the HF Hub — the original `wikiann`
dataset script path was deprecated (HF Hub stopped resolving bare, namespace-
less repo ids for script-based datasets), so `load_dataset("wikiann", lang)`
now fails with an HfUriError.
"""
from datasets import load_dataset, DatasetDict

LABEL_LIST = ["O", "B-PER", "I-PER", "B-ORG", "I-ORG", "B-LOC", "I-LOC"]

WIKIANN_REPO = "unimelb-nlp/wikiann"


def load_wikiann(language: str) -> DatasetDict:
    """Load WikiAnn for a single language code (e.g. 'en', 'hi', 'es', 'de')."""
    return load_dataset(WIKIANN_REPO, language)


def load_wikiann_multilingual(languages: list[str]) -> dict[str, DatasetDict]:
    """Load WikiAnn for each language, keyed by language code."""
    return {lang: load_wikiann(lang) for lang in languages}
