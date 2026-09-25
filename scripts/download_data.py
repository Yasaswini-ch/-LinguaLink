"""CLI: download WikiAnn NER data for the configured languages.

Usage:
    python scripts/download_data.py --languages en hi es de
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mel.data.wikiann import load_wikiann_multilingual  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--languages", nargs="+", default=["en", "hi", "es", "de"])
    args = parser.parse_args()

    print(f"Downloading WikiAnn for: {args.languages}")
    datasets = load_wikiann_multilingual(args.languages)
    for lang, ds in datasets.items():
        print(f"  {lang}: train={len(ds['train'])} val={len(ds['validation'])} test={len(ds['test'])}")


if __name__ == "__main__":
    main()
