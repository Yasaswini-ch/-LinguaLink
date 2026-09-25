"""Translate mention context to English before disambiguation.

Tested against the Hindi "गुजरात" case (Gujarat the state vs. Gujarati the
language): translating both the context AND the candidate descriptions to
English does NOT fix it. Gujarati still outranks Gujarat (0.574 vs 0.508)
even with fully English context and descriptions — see
docs/LATE_STAGE_FINDINGS.md for the full, corrected writeup, including an
earlier claim (made from unrepresentative hand-written test data, not the
real pipeline) that this fixed the case. It didn't. The real cause: Wikidata's
English description for Gujarat literally contains the word "Gujarat" (and
Gujarati's description shares the same root), so the two candidates'
descriptions overlap lexically regardless of what language the context is
translated to — the ambiguity was never a context-language problem.

This module is kept in the pipeline because it's harmless (translation
failures degrade gracefully to the original text, see below) and untested
cases may still benefit, but it should not be presented as a fix for the
Gujarat/Gujarati case specifically.

Uses MyMemory's free translation API (no key required) rather than adding a
heavier translation library — this project has already leaned hard on free,
unauthenticated APIs and hit their rate limits more than once, so this is
kept as a single lightweight, gracefully-degrading call: on any failure, the
original (untranslated) text is returned rather than raising, so a
translation outage degrades disambiguation quality, not availability.
"""
import requests

MYMEMORY_API = "https://api.mymemory.translated.net/get"


def translate_to_english(text: str, source_lang: str) -> str:
    if source_lang == "en" or not text.strip():
        return text
    try:
        resp = requests.get(
            MYMEMORY_API,
            params={"q": text, "langpair": f"{source_lang}|en"},
            headers={"User-Agent": "mel-project/0.1"},
            timeout=8,
        )
        resp.raise_for_status()
        translated = resp.json().get("responseData", {}).get("translatedText", "")
        return translated if translated else text
    except Exception as e:
        print(f"Translation failed for lang={source_lang!r}: {e}")
        return text
