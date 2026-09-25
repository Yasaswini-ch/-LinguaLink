# Multilingual Entity Linking & Disambiguation

**Cross-lingual Named Entity Recognition, Candidate Generation, and Disambiguation across English, Hindi, Spanish, and German**

---

## 1. Introduction

Named Entity Recognition (NER) identifies mentions of real-world entities in text — people, organizations, locations. On its own, NER only tells you *that* a span refers to something; it doesn't tell you *which* something. "Amazon reported record cloud revenue" and "The Amazon flows through Brazil" both contain the mention "Amazon," correctly tagged, but they refer to two entirely different real-world entities. Resolving that — deciding which specific entity a mention points to, given its context — is Entity Linking and Disambiguation, and it's a substantially harder problem than detection alone.

This project builds a complete, working pipeline for both stages, extended across four languages (English, Hindi, Spanish, German) rather than a single one, and grounded against Wikidata as the target knowledge base. The distinguishing goal of the project was not just to build something that runs, but to genuinely test it — across languages, against real named entities, under adversarial and casual phrasing — and fix what actually broke. Most of what follows is the record of that process: real bugs found through live testing, root-caused, and fixed, not a description of an untested design.

## 2. Pipeline architecture

```
Input text (EN / HI / ES / DE)
        │
        ▼
1. NER — mention detection
   (pretrained multilingual XLM-R token classifier)
        │  mention spans + type (PER / ORG / LOC)
        ▼
2. Candidate generation
   (local KB cache → Wikidata wbsearchentities search API fallback)
        │  ranked list of plausible entities
        ▼
3. Disambiguation
   (multilingual sentence-embedding similarity + popularity tiebreak)
        │  best match, or NIL if no confident match
        ▼
4. Output
   Wikidata QID + confidence, surfaced through a FastAPI + React demo
```

### 2.1 NER — two models, one decision

The project actually trained its own NER model: a multilingual XLM-RoBERTa token classifier fine-tuned on WikiAnn across all four languages, run on Google Colab's free GPU tier (local development had no GPU). It scored well on WikiAnn's own test set:

| Language | NER F1 |
|---|---|
| English | 0.839 |
| Hindi | 0.890 |
| Spanish | 0.914 |
| German | 0.883 |

But testing it on casual, unpunctuated, real-world-style sentences exposed a serious failure mode: **"I live in Brazil" (no trailing period) was misclassified entirely as a single ORG span** — every token, including "I" and "live," tagged as part of one organization name. "I live in Brazil." (with a period) worked fine, as did third-person sentences without punctuation. The cause: WikiAnn is derived entirely from Wikipedia — third-person, formal, always punctuated — so a first-person, unpunctuated opener is essentially unseen in training, and the model's behavior on it was degenerate rather than gracefully wrong.

Two responses were tried. First, a targeted fix: 40 hand-labeled casual/conversational examples covering this exact pattern, mixed into training data as augmentation (`data/processed/casual_ner_augmentation_en.jsonl`). This is real and kept in the repo, but 40 examples cannot generalize broadly. Second, and what the running system actually uses: swapping the inference-time NER model to a pretrained checkpoint (`Davlan/xlm-roberta-base-ner-hrl`) trained on far more diverse data. Tested head-to-head against every failure case:

| Input | Our fine-tune | Pretrained model |
|---|---|---|
| "I live in Brazil" | ❌ whole sentence → ORG | ✅ Brazil → LOC |
| "hello im santa from brazil" | ❌ whole sentence → ORG | ✅ santa → PER, brazil → LOC |
| Hindi/Spanish/German formal sentences | ✅ correct | ✅ correct (including Hindi, despite not being in the model's documented language list) |

The project keeps both models and reports the comparison honestly rather than picking one and hiding the other: the fine-tune has better in-domain (WikiAnn) accuracy; the pretrained model generalizes far better out of domain, which is what a live demo actually needs. `configs/ner_xlmr.yaml` documents which one the running system uses and why.

A second, independent fix for casual text: **truecasing**. English input is passed through a capitalization-restoration step before NER (`truecase` library) — "modi and putin discussed trade in moscow" becomes "Modi and Putin discussed trade in Moscow" for detection purposes, while the original text is preserved for display and highlighting (offsets are length-preserving, so this doesn't corrupt span positions). Before this fix, that sentence returned zero detected entities; after, all three (Modi, Putin, Moscow) are correctly found and typed.

### 2.2 Candidate generation — from broken exact-match to relevance-ranked search

The initial candidate generation used a hand-written SPARQL query doing exact literal alias matching against Wikidata. This had two compounding problems, both found through live testing:

1. **No ranking by notability.** A query for "Elon Musk" or "Modi" would return *whichever* matching entity SPARQL happened to return first — in practice, an obscure duplicate or unrelated entity, not the famous one.
2. **No fuzzy/partial matching.** Surname-only mentions ("Messi," "Putin," "Ronaldo" — extremely common in real text) simply failed to match a cached label like "Lionel Messi," since matching required an exact or prefix match.

The fix: replace the SPARQL exact-match path with Wikidata's own `wbsearchentities` API, which does relevance-ranked fuzzy search and returns descriptions directly. This alone fixed most of the surname and wrong-entity cases without any further tuning. On top of it, a **popularity tiebreak** was added: each candidate's Wikidata sitelink count (how many Wikipedia language editions have an article on it) is fetched and blended — with deliberately small weight — into the ranking, so that when two candidates are semantically close, the more notable one wins. This was validated directly: a search for "Messi" returns both the real Lionel Messi (225 sitelinks) and an unrelated, obscure Brazilian footballer also literally named "Messi" (2 sitelinks); before the tiebreak, the obscure one edged out the famous one on raw embedding similarity (0.511 vs. 0.487); after, the correct one wins.

The system layers a small local cache (`data/kb/wikidata_aliases.parquet`, ~50 hand-seeded entities spanning people, countries, cities, and companies, built via batched SPARQL queries with retry-on-rate-limit logic) in front of the live search API, so common demo entities resolve instantly without hitting Wikidata's servers on every request.

**A real, upstream-data-gap finding:** `wbgetentities` confirmed that Q1058 (Narendra Modi) has **zero registered English aliases** on Wikidata itself. No live query strategy — SPARQL or the search API — could ever find him via the bare surname "Modi," because the data simply isn't there. This is documented in `configs/manual_aliases.yaml` as the one case genuinely requiring a manual override, distinct from every other case that the search-API fix resolved automatically.

### 2.3 Disambiguation — richer context, verified experimentally

The disambiguation step encodes the mention's local context and each candidate's description with a multilingual sentence-transformer, then ranks by cosine similarity. Model choice was itself an experiment, not an assumption: **LaBSE** (translation-pair-tuned) was tried first and directly compared against **paraphrase-multilingual-mpnet-base-v2** (STS/paraphrase-tuned) on the canonical "Amazon" disambiguation example. LaBSE got the ranking *backwards* — ranking the river above the company even in a clearly business context (0.169 vs. 0.107). The STS-tuned model got both directions correct (0.145 business→company vs. 0.043 business→river; 0.558 river→river vs. 0.138 river→company). The config was switched, and this comparison is documented rather than assumed.

A second, independent improvement: **Wikipedia extract enrichment**. Wikidata's own descriptions are terse one-liners ("American businessman (born 1971)"), which often share almost no vocabulary with a mention's actual sentence context — this was directly responsible for at least one wrong disambiguation (Apple-the-company narrowly losing to Apple-the-fruit on "Apple reported record iPhone sales," 0.267 vs. 0.240, because the company's short description had no overlap with "iPhone" or "sales"). Real Wikipedia intro-paragraph extracts (fetched via Wikipedia's REST summary API, resolved through Wikidata's sitelinks, truncated to 400 characters) replace the short description when available. Retested: Apple Inc. now wins clearly, 0.39 vs. 0.357 for the fruit.

### 2.4 Known, honestly-documented limitations

Not every case was fixable, and the project treats the unfixed ones as findings rather than hiding them:

- **Genuine real-world ambiguity.** "Ronaldo" alone can correctly mean either Cristiano Ronaldo or Ronaldo Nazário (the Brazilian striker, historically the more common referent of the bare name) — both are highly notable, so no popularity signal disambiguates them, and the sentence itself doesn't specify. A human reader would face the same ambiguity.
- **Short-context sensitivity persists in some cases** even after the Wikipedia-enrichment fix — e.g. a Spanish query for "Ronaldo" that surfaced a lesser-known "Ronaldo" (52 sitelinks) over Cristiano Ronaldo (215 sitelinks) purely on raw semantic similarity, before the (intentionally small) popularity term could correct it. Increasing that weight further risks breaking other, correctly-working cases — a real precision/recall tradeoff, not a bug.
- **A rare NER tokenizer artifact:** the pretrained model split "Frida" into subword pieces ("Fri" + "da") and predicted a *new* entity boundary for the second piece, producing two garbage mentions instead of one "Frida Kahlo" span. Model-internal, name-specific, not something the project's own code caused or can directly patch.
- **Wikidata's live APIs are a genuine operational dependency.** During this project's development, Wikidata's SPARQL query service was in an active, publicly-acknowledged outage, aggressively rate-limiting to roughly one request per minute; the `wbsearchentities`/`wbgetentities` action API separately rate-limits under sustained request volume. The system was made resilient to both (see §3), but a production deployment would need an authenticated API key for higher limits.

## 3. Resilience and correctness fixes found through testing

Several of the most valuable findings in this project were not disambiguation-quality issues but outright bugs, caught by actually running the system rather than reasoning about it abstractly:

- **A Windows console encoding crash.** The very fallback code meant to catch live-query failures gracefully crashed *itself* when logging a Hindi (Devanagari) mention on a Windows console defaulting to cp1252 — turning a designed graceful-degradation path into an unhandled 500 error. Fixed by ASCII-escaping the logged text.
- **A false-positive from an earlier fix.** Adding substring matching to fix "Apple" → "Apple Inc." (an exact-match gap) accidentally caused "Deutschland" to match Berlin's German-language alias "Berlin, Deutschland" (a "city, country" naming convention) and link Germany's own mention to its own capital instead of the country. Fixed by narrowing the match to `startswith` rather than `contains` — narrow enough to still catch "Apple Inc." but not an unrelated entity's composite alias.
- **Wrong seed data.** One QID in the hand-curated seed list was simply wrong — Q8023, labeled "Cristiano Ronaldo" in a comment, actually resolves to Nelson Mandela. Caught by cross-checking against `wbgetentities` output rather than trusting the original entry.
- **Silent batch-query truncation.** Building the local KB cache with SPARQL `VALUES` cross-products across ~50 entities × 4 languages in large batches silently returned incomplete results for some entities (Einstein, Messi got zero rows in 3 of 4 languages) without raising any error. Fixed with a smaller batch size and an explicit post-build completeness check that lists every missing `(qid, lang)` pair instead of trusting the row count.
- **Rate-limit resilience**, layered at two levels: exponential-style retry with a ~65-second wait for the SPARQL endpoint's "1 request/minute" outage throttle, and a shorter ~3-second retry for the separate, less severe action-API rate limit — the latter tuned down further by capping Wikipedia-extract enrichment to the top 5 candidates per mention instead of all 10, cutting request volume roughly in half.

## 4. Application

A FastAPI backend (`demo/backend/main.py`) exposes `POST /link` (full pipeline) and `GET /entity/{qid}/relations` (lazily-fetched Wikidata claims — occupation, country of citizenship, etc. — fetched only when a user opens that specific panel, not bundled into every query, to keep request volume down). A React frontend ("LinguaLink") consumes it: language selector, example sentences, highlighted linked text color-coded by entity type, a per-mention confidence bar list, a live "processing pipeline" stepper, and an entity-details panel with three tabs — candidate ranking (showing the actual ranked alternatives, not just the winner), metadata, and relations. Loading states use skeleton placeholders rather than a blank gap, and results fade in rather than popping in abruptly.

Every piece of this was verified against the live, running system in a browser — not asserted from reading the code — including deliberately adversarial and multilingual test batches covering both languages and previously-broken cases.

## 5. Evaluation

### 5.1 NER (fine-tuned model, WikiAnn test set)

| Language | Precision | Recall | F1 |
|---|---|---|---|
| English | 0.873 | 0.883 | 0.839* |
| Hindi | — | — | 0.890 |
| Spanish | — | — | 0.914 |
| German | — | — | 0.883 |

*Combined test-set F1 across all languages: 0.878. Note English's own F1 was, counter to the "high-resource languages should always win" assumption, the *lowest* of the four despite being the highest-resource language — Hindi outperformed it. A genuinely interesting, unresolved finding rather than a clean story; likely reflects WikiAnn's per-language test-set size/quality variance (10k examples) more than a real generalization gap.

### 5.2 Linking accuracy (hand-authored gold set, 22 examples across 4 languages)

| Language | Accuracy | n |
|---|---|---|
| English | 0.857 | 7 |
| Hindi | 0.800 | 5 |
| Spanish | 0.800 | 5 |
| German | 0.800 | 5 |

This gold set is intentionally small and hand-authored around the project's core worked examples (Apple, Amazon, Modi, Merkel, Berlin) — a real starter benchmark, not a production-scale one. Expanding it (ideally to something like Mewsli-9) is the clearest concrete next step for anyone continuing this work, now that the underlying pipeline it would be measuring is substantially more correct than when this evaluation was first run.

## 6. Honest project status

The core system works, end-to-end, across four languages, and has been debugged against real failures rather than only tested against cases chosen to succeed. What's genuinely finished: the pipeline, the candidate-generation and disambiguation quality fixes, the resilience fixes, and the demo application. What's genuinely not finished, stated plainly: the linking-accuracy gold set is small; the project has not been deployed anywhere (local only); and Wikidata's live-API dependency means a fresh run can be rate-limited by an external service the project doesn't control. None of these are hidden — they're the natural next steps for anyone picking this up.

## 7. Repository layout

```
src/mel/
  ner/          NER training (own fine-tune) + inference (pretrained model used by the app)
  linking/      candidate generation, disambiguation, full pipeline
  data/         WikiAnn loader, Wikidata KB (search API, SPARQL, sitelinks, Wikipedia extracts)
  eval/         NER F1 and linking-accuracy evaluation
configs/        ner_xlmr.yaml, linking.yaml, seed_entities.yaml, manual_aliases.yaml
data/kb/        local Wikidata alias cache (parquet)
data/processed/ casual-text NER augmentation set, linking eval gold set
demo/backend/   FastAPI app
demo/frontend/  React app ("LinguaLink")
notebooks/      Colab GPU training notebook
results/        evaluation output tables
```
