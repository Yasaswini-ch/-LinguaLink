"""Full pipeline: NER -> candidate generation -> disambiguation -> linked output."""
from dataclasses import dataclass

from mel.ner.infer import NERTagger, Mention
from mel.linking.candidates import generate_candidates
from mel.linking.disambiguate import Disambiguator, LinkedEntity
from mel.data.translate import translate_to_english


@dataclass
class LinkedMention:
    mention: Mention
    linked_entity: LinkedEntity


class EntityLinkingPipeline:
    def __init__(
        self,
        ner_model_path: str,
        embedding_model: str,
        nil_threshold: float,
        context_window_tokens: int = 20,
        kb_cache_path: str = "data/kb/wikidata_aliases.parquet",
    ):
        self.tagger = NERTagger(ner_model_path)
        self.disambiguator = Disambiguator(embedding_model, nil_threshold)
        self.context_window_tokens = context_window_tokens
        self.kb_cache_path = kb_cache_path

    def _local_context(self, text: str, mention: Mention) -> str:
        words = text.split()
        # crude token-window context; refine with proper span-to-word mapping if needed
        return " ".join(words[: self.context_window_tokens * 2])

    def run(self, text: str, lang: str) -> list[LinkedMention]:
        mentions = self.tagger.extract_mentions(text, lang)

        # Translate once per request (not per mention) and reuse. NOTE: this
        # was tried as a fix for a Hindi "गुजरात" mention resolving to the
        # wrong candidate (Gujarati the language, not Gujarat the state) and
        # does NOT fix that case — tested against the real pipeline, Gujarati
        # still outranks Gujarat even with fully English context and
        # candidate descriptions. See docs/LATE_STAGE_FINDINGS.md; the
        # real cause is lexical overlap in the candidate descriptions
        # themselves, not context language. Kept because it's a harmless,
        # gracefully-degrading no-op on failure and may still help other
        # untested cases — not because it's a confirmed fix.
        translated_text = translate_to_english(text, lang) if lang != "en" else text

        linked = []
        for mention in mentions:
            candidates = generate_candidates(mention.lookup_text, lang, cache_path=self.kb_cache_path)
            context = self._local_context(translated_text, mention)
            entity = self.disambiguator.rank(context, candidates)
            linked.append(LinkedMention(mention=mention, linked_entity=entity))
        return linked
