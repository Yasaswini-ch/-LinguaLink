"""Disambiguation: rank candidate entities by cross-lingual context similarity."""
from dataclasses import dataclass, field

import numpy as np
from sentence_transformers import SentenceTransformer, util


@dataclass
class RankedCandidate:
    qid: str
    label: str
    confidence: float  # raw cosine similarity (context vs. candidate description)
    description: str = ""
    popularity: int = 0            # raw Wikidata sitelink count
    popularity_norm: float = 0.0   # log1p(popularity), normalized 0-1 within this candidate set
    blended_score: float = 0.0     # confidence + POPULARITY_WEIGHT * popularity_norm — what ranking order is sorted by
    source: str = ""               # "local_cache" or "live_search" — see mel.linking.candidates.generate_candidates


@dataclass
class LinkedEntity:
    qid: str
    label: str
    confidence: float
    is_nil: bool = False
    ranked_candidates: list[RankedCandidate] = field(default_factory=list)


class Disambiguator:
    # How much a candidate's notability (Wikidata sitelink count, log-scaled
    # and normalized 0-1 within the candidate set) can shift the RANKING
    # ORDER. Small on purpose: it should only decide close ties (e.g. an
    # obscure same-named entity edging out the famous one by a hair on pure
    # semantic similarity), never override a clear semantic winner. Reported
    # `confidence` stays the raw cosine similarity either way — popularity
    # affects ordering, not the displayed/NIL-thresholded score.
    POPULARITY_WEIGHT = 0.08

    def __init__(self, embedding_model: str = "sentence-transformers/LaBSE", nil_threshold: float = 0.4):
        self.encoder = SentenceTransformer(embedding_model)
        self.nil_threshold = nil_threshold

    def rank(self, mention_context: str, candidates: list[dict]) -> LinkedEntity:
        """Embed the mention's local context and each candidate description,
        rank by cosine similarity (with a small notability-based tiebreak),
        and return the top match (or NIL) along with the full ranked
        candidate list (for UI candidate-ranking views)."""
        if not candidates:
            return LinkedEntity(qid="", label="", confidence=0.0, is_nil=True)

        context_emb = self.encoder.encode(mention_context, convert_to_tensor=True)
        candidate_texts = [c["description"] or c["label"] for c in candidates]
        candidate_embs = self.encoder.encode(candidate_texts, convert_to_tensor=True)

        scores = util.cos_sim(context_emb, candidate_embs)[0].cpu().numpy()

        popularity = np.array([c.get("popularity", 0) for c in candidates], dtype=float)
        max_pop = popularity.max()
        popularity_norm = np.log1p(popularity) / np.log1p(max_pop) if max_pop > 0 else np.zeros_like(popularity)

        blended = scores + self.POPULARITY_WEIGHT * popularity_norm
        order = np.argsort(-blended)

        ranked = [
            RankedCandidate(
                qid=candidates[i]["qid"],
                label=candidates[i]["label"],
                confidence=float(scores[i]),
                description=candidates[i].get("description", ""),
                popularity=int(popularity[i]),
                popularity_norm=float(popularity_norm[i]),
                blended_score=float(blended[i]),
                source=candidates[i].get("source", ""),
            )
            for i in order
        ]

        best = ranked[0]
        if best.confidence < self.nil_threshold:
            return LinkedEntity(qid="", label="", confidence=best.confidence, is_nil=True, ranked_candidates=ranked)

        return LinkedEntity(qid=best.qid, label=best.label, confidence=best.confidence, ranked_candidates=ranked)
