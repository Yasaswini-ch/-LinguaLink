"""Hand-labeled casual/conversational NER examples used to augment WikiAnn training data.

WikiAnn is derived entirely from Wikipedia — third-person, fully punctuated,
formal prose. A model trained only on that distribution can fail badly on
casual text (e.g. an unpunctuated first-person sentence like "I live in
Brazil" gets misclassified as a single ORG span; see the "I live in Brazil"
vs "I live in Brazil." diagnostic that motivated this file). These examples
are English-only for now — extending to hi/es/de is a natural next step.
"""
import json
from pathlib import Path

from datasets import ClassLabel, Dataset, Features, Sequence, Value

from mel.data.wikiann import LABEL_LIST

DEFAULT_PATH = Path("data/processed/casual_ner_augmentation_en.jsonl")

# Must match WikiAnn's ner_tags feature type (ClassLabel, not plain int) or
# concatenate_datasets refuses to align the two datasets' schemas.
FEATURES = Features(
    {
        "tokens": Sequence(Value("string")),
        "ner_tags": Sequence(ClassLabel(names=LABEL_LIST)),
    }
)


def load_casual_augmentation(path: str | Path = DEFAULT_PATH) -> Dataset:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return Dataset.from_list(rows, features=FEATURES)
