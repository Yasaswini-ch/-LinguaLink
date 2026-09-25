"""Shared HTTP-with-retry helper for MediaWiki-family action APIs (Wikidata, Wikinews, Wikipedia)."""
import time

import requests


def get_json_with_retry(url: str, params: dict, max_retries: int = 2, retry_wait_seconds: int = 3) -> dict | None:
    """GET a MediaWiki action API endpoint, retrying briefly on 429.

    Returns None on any unrecovered failure so callers can degrade gracefully
    (e.g. skip an example, fall back to a shorter description) instead of
    crashing a whole batch run.
    """
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(url, params=params, headers={"User-Agent": "mel-project/0.1"}, timeout=10)
            if resp.status_code == 429 and attempt < max_retries:
                time.sleep(retry_wait_seconds)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            if getattr(e.response, "status_code", None) == 429 and attempt < max_retries:
                time.sleep(retry_wait_seconds)
                continue
            print(f"MediaWiki API request failed: {e}")
            return None
        except Exception as e:
            print(f"MediaWiki API request failed: {e}")
            return None
    return None
