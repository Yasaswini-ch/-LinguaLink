"""Run mention detection (NER) on raw text using a fine-tuned checkpoint."""
from dataclasses import dataclass

import truecase
from transformers import AutoModelForTokenClassification, AutoTokenizer, pipeline


@dataclass
class Mention:
    text: str            # original-cased slice, used for display/highlighting
    label: str            # PER / ORG / LOC
    start_char: int
    end_char: int
    lookup_text: str = ""  # truecased slice, used for KB/candidate-generation lookup


def _truecase_if_helpful(text: str, lang: str) -> str:
    """Restore likely capitalization before NER (helps a lot on lowercase/
    casual input — capitalization is the strongest signal these models use
    for proper nouns). English-only (the `truecase` library's model is
    English-specific); other languages pass through unchanged. Falls back to
    the original text if truecasing changes the string length, since callers
    rely on character offsets staying aligned with the original text.

    Only runs on text that has NO uppercase letters at all. Verified
    (see docs/LATE_STAGE_FINDINGS.md) that running truecase on already
    properly-cased text can wrongly capitalize an ambiguous common noun
    (e.g. "...active pharaoh." -> "...active Pharaoh."), which then gets
    NER-tagged as a spurious PERSON entity. Restricting to all-lowercase
    input keeps the original casual-text fix (truecase is genuinely needed
    there) without touching sentences that were already cased correctly.
    """
    if lang != "en":
        return text
    if text != text.lower():
        return text
    try:
        cased = truecase.get_true_case(text)
    except Exception:
        return text
    return cased if len(cased) == len(text) else text


class NERTagger:
    def __init__(self, model_path: str):
        self.model = AutoModelForTokenClassification.from_pretrained(model_path)
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self._pipe = pipeline(
            "ner",
            model=self.model,
            tokenizer=self.tokenizer,
            aggregation_strategy="simple",
        )

    def extract_mentions(self, text: str, lang: str = "en") -> list[Mention]:
        # Run NER on a truecased copy (better detection on lowercase input).
        # Mention.text is always sliced from the ORIGINAL string (offsets are
        # preserved since truecasing only changes letter case, not length) so
        # highlighting shows exactly what the user typed. Mention.lookup_text
        # is sliced from the truecased copy instead — Wikidata's live SPARQL
        # query does a case-sensitive literal match, so a lowercase "modi"
        # mention needs the properly-cased "Modi" to find its Wikidata alias.
        ner_input = _truecase_if_helpful(text, lang)
        raw = self._pipe(ner_input)
        return [
            Mention(
                text=text[r["start"] : r["end"]],
                label=r["entity_group"],
                start_char=r["start"],
                end_char=r["end"],
                lookup_text=ner_input[r["start"] : r["end"]],
            )
            for r in raw
        ]
