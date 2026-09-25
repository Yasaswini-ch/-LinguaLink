# Late-Stage Testing Findings

**Supplementary to [`PROJECT_REPORT.md`](PROJECT_REPORT.md) — results from a final round of out-of-box testing and the translation-context experiment, kept separate because they were found after the main report was written and include a self-correction.**

---

## 1. Fresh out-of-box generalization test

The report's examples were re-tested repeatedly during development. To check the fixes (truecasing, pretrained NER, `lookup_text`/display-text split) actually generalize rather than being tuned to familiar cases, six sentences were run using entities never touched earlier in the project — Isaac Newton, Cleopatra, Pablo Picasso, Mozart/Salzburg, Sachin Tendulkar, Taj Mahal/Agra — across all four languages.

Raw output:

```
=== en ===
Isaac Newton formulated the laws of motion in the 17th century.
  Isaac Newton [PER] -> Isaac Newton (Q935) 0.6

=== en ===
Cleopatra ruled Egypt as its last active pharaoh.
  Cleopatra [PER] -> Cleopatra (Q635) 0.645
  Egypt [LOC] -> Egypt (Q79) 0.204
  phar [PER] -> NIL
  aoh [PER] -> Al Omooma Hospital (Q30280924) 0.157

=== es ===
Pablo Picasso nació en Málaga y revolucionó el arte moderno.
  Pablo Picasso [PER] -> Pablo Picasso (Q5593) 0.767
  Málaga [LOC] -> NIL

=== de ===
Wolfgang Amadeus Mozart wurde in Salzburg geboren.
  Wolfgang Amadeus Mozart [PER] -> NIL
  Salzburg [LOC] -> Salzburg (Q43325) 0.619

=== hi ===
सचिन तेंदुलकर को क्रिकेट का भगवान कहा जाता है।
  सचिन तेंदुलकर [PER] -> Sachin Tendulkar (Q9488) 0.602

=== hi ===
ताजमहल आगरा में स्थित है।
  ताजमहल [LOC] -> NIL
  आगरा [LOC] -> NIL
```

### Verdict: generalizes, with two new bugs found

**Correct and new (proof of generalization):** Isaac Newton, Cleopatra, Egypt, Pablo Picasso, and Sachin Tendulkar all resolved correctly on the first try, in three different scripts (Latin, Devanagari) and two languages beyond English (Spanish, Hindi) — none of these were used to develop or tune the pipeline. This is real evidence the fixes aren't overfit to the handful of examples used during development.

**FIXED — "pharaoh" fragmentation was a truecasing bug, not a tokenizer artifact.** Root-caused after this table was first written: truecasing was applied unconditionally to every English input, and on this already-properly-cased sentence it wrongly capitalized the common noun "pharaoh" → "Pharaoh" (`truecase.get_true_case` does this even on well-formed sentences — verified directly). The now-improperly-capitalized "Pharaoh" was then split by the NER model into two spurious PER spans, `Phar` (0.95 confidence) and `aoh` (0.52 confidence) — both high enough that a confidence floor would not have reliably suppressed them. Since a NER-score floor wasn't a real fix, [`infer.py`](../src/mel/ner/infer.py)'s `_truecase_if_helpful` was changed to only run truecasing on text that is **entirely lowercase** (`text == text.lower()`), which is exactly the original casual-input case truecasing was added for. Verified after the fix: the pharaoh sentence now tags only `Cleopatra` and `Egypt` (no fragments), and the original casual-text case (`"i live in brazil"` → `Brazil` [LOC]) still works correctly.

**Mozart resolved to the wrong Mozart, not a rate-limit failure.** The original run showed Mozart as NIL. Wikidata's action API had been rate-limiting heavily during this test batch (see the `429 Too Many Requests` in the raw pipeline log below), so NIL was initially assumed to be infrastructure noise. Retesting in isolation confirmed it resolves, but to **Q156023** — not the composer Wolfgang Amadeus Mozart (the world-famous father), but his son of the same name. This is a genuine disambiguation miss: the candidate ranking picked the less notable of two same-named entities. Likely cause: the popularity signal (Wikidata sitelink count) should favor the father heavily, so this may be a candidate-generation issue (the father not appearing in the local KB cache / search results with this exact mention string) rather than a ranking issue — not root-caused before time ran out on this session.

**Málaga and Taj Mahal/Agra NIL — inconclusive, likely rate-limit noise, not re-verified.** These NILs occurred in the same batch as the confirmed `429` errors on the Wikidata API. Given the Mozart case turned out to be resolvable on retry, these are suspected to be transient rate-limiting rather than genuine pipeline failures, but that was not directly confirmed by an isolated retest the way Mozart was. Flagged as unverified rather than claimed as either a bug or a non-issue.

---

## 2. The translation-to-English experiment: an honest account, including a walked-back claim

This is the most important finding of this final round, and it required correcting something reported as validated a step earlier in the same session.

### 2.1 The hypothesis

The user's own idea: disambiguation runs on a multilingual sentence-embedding model, but that model may be more discriminative in English than in other languages. If so, translating non-English context text to English before embedding it (while candidate descriptions are already fetched in English) should improve ranking accuracy on non-English input.

### 2.2 What was initially claimed

Using hand-written test context strings (not run through the live pipeline), translating both the context and candidate descriptions to English appeared to fix a specific case: Hindi "गुजरात" (Gujarat) disambiguating against "Gujarati" (the language) — reported at the time as failing 0.564 (wrong) vs 0.474 (right) with native-language context, and fixed to 0.65 (right) vs 0.622 (wrong) with both sides translated to English. This was reported to the user as a confirmed fix, and the user approved implementing it in the real pipeline.

### 2.3 What the real pipeline actually showed

After wiring `translate_to_english()` into [`pipeline.py`](../src/mel/linking/pipeline.py) and running it against real data (not hand-written test strings), the Hindi Gujarat case was retested in isolation:

```
context: Mahatma Gandhi was born in Gujarat.
Top: Q5137 Gujarati 0.574
 - Q5137 Gujarati 0.574
 - Q1061 Gujarat 0.508
 - Q507349 Gujarat University 0.471
 - Q3180306 Gujarati Wikipedia 0.427
```

Even with English context ("Mahatma Gandhi was born in Gujarat" — translated correctly) and English candidate descriptions, **Gujarati (the language) still outranks Gujarat (the state), 0.574 to 0.508.** Running it through the actual live pipeline end-to-end confirmed the same outcome:

```
महात्मा गांधी -> Mahatma Gandhi Q111826790 0.723
गुजरात -> Gujarati Q5137 0.574
```

This directly contradicts the earlier claim. The translation fix, as implemented, **does not fix this case.**

### 2.4 Root cause of the original (wrong) validation

The hand-written test candidate description used to validate the fix earlier in the session was not representative of the real data. Wikidata's actual English-language description/extract for Q1061 (Gujarat, the state) contains the literal substring **"Gujarat"** — e.g. *"Gujarat is a state along the western coast of India..."* — which is exactly what the candidate-enrichment step (`get_wikipedia_extracts`) fetches and feeds to the embedding model. The Q5137 (Gujarati, the language) description does too, by nature of sharing the root word. So the ranking is dominated by shared-token lexical overlap in the *candidate descriptions themselves*, which translating the *context* has no leverage over — the language axis was never the actual source of the ambiguity, the descriptions' text was, and both candidates' descriptions share the ambiguous root word regardless of what language the context is in.

In short: the earlier validation used unrepresentative hand-written data, got lucky (or was constructed in a way that happened to isolate a different variable than the one actually tested), and the conclusion drawn from it did not hold up once tested against the real pipeline. That correction was surfaced to the user directly, in the same session, as soon as it was found — the report was not adjusted quietly to hide the reversal.

### 2.5 Net effect of the translation change

The context-translation change (`src/mel/data/translate.py`, wired into `pipeline.py`) is still in the codebase because it is not harmful (graceful degradation to original text on any translation failure, per its own docstring) and it may still help other cases not yet tested. Its docstring and the `pipeline.py` comment have been **corrected** (no longer cite the original incorrect 0.65-vs-0.622 numbers as a confirmed fix) to state plainly that translation does not resolve the Gujarat/Gujarati case and that the real root cause is lexical overlap in candidate description text, not context language.

---

## 3. Quantitative linking accuracy — expanded eval set (142 examples)

The original hand-authored gold set (`data/processed/linking_eval_set.jsonl`) had only 22 examples (5–7 per language) — too small to trust as an accuracy number, and the concern raised directly: if it had come in under 50%, the fix would have been to expand it before drawing any conclusion. It came in at 80–85% on 22 examples, but that was reason to get a bigger, more defensible number, not to stop.

120 additional sentences (30 per language, 4 languages) were added, built from the already-verified QIDs in [`configs/seed_entities.yaml`](../configs/seed_entities.yaml) (people, countries, cities, companies) rather than freshly guessed QIDs, to avoid introducing incorrect gold labels. The full 142-example set was run end-to-end through the actual production `Disambiguator` (`configs/linking.yaml`'s mpnet model + 0.1 NIL threshold) via `scripts/evaluate.py`.

| Language | Linking accuracy | n |
|---|---|---|
| English | 91.9% | 34/37 |
| Hindi | 88.6% | 31/35 |
| Spanish | 77.1% | 27/35 |
| German | 80.0% | 28/35 |
| **Overall** | **84.5%** | 120/142 |

**Caveat, now checked:** this run hit heavy Wikidata `429` rate-limiting throughout, most visibly during the Spanish and German batches, which degrades candidate enrichment (missing sitelink/popularity and description data for some candidates mid-run). To check whether that explained the lower es/de scores, es and de were rerun in isolation (35 examples each, no en/hi in the same run, to cut total request volume roughly in half). The rerun **still hit heavy 429s** despite the existing 3-second/2-retry backoff — this appears to be a sustained throttle on the current IP/session rather than a short transient burst, so retrying with the existing backoff doesn't clear it. Results held essentially steady:

| Language | Original run | Isolated rerun |
|---|---|---|
| Spanish | 77.1% (27/35) | 80.0% (28/35) |
| German | 80.0% (28/35) | 80.0% (28/35) |

Since the score didn't meaningfully change under a second independent throttled run, **~80% is being treated as the working es/de number** rather than an artifact — the rate-limiting is real and ongoing (it affects reproducibility of any single live test, as noted elsewhere in this project), but it does not appear to be the primary reason es/de trail en/hi by ~10 points. That gap is more likely a genuine, if modest, difference in how well the multilingual embedding model and the available Spanish/German Wikidata candidate data disambiguate compared to English/Hindi — not yet root-caused further. The NER F1 figures printed in the same evaluation run are for the old fine-tuned checkpoint (`configs/eval.yaml` intentionally points at it, see that file's comments) — **not** the pretrained model the demo actually uses at inference time — and should not be read as demo-time NER accuracy.

## 4. Summary of open items from this round

| Item | Status |
|---|---|
| Generalization to fresh entities (Newton, Cleopatra, Picasso, Tendulkar) | **Confirmed working**, first-try, across 3 languages |
| "pharaoh" NER fragmentation | **Fixed** — was a truecasing bug (over-capitalizing an already well-cased sentence), not a tokenizer artifact; truecasing now only runs on fully-lowercase input |
| Mozart father/son disambiguation | New bug, not fixed — resolves to the less notable Q156023 instead of the composer |
| Málaga / Taj Mahal / Agra → NIL | Unverified — likely rate-limit noise, not confirmed by isolated retest |
| Context-translation fix for Gujarat/Gujarati | **Does not work** — real cause is candidate-description lexical overlap, not context language; code comments corrected to stop overstating effectiveness |
