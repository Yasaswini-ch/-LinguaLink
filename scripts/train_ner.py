"""CLI: fine-tune the multilingual NER model.

Usage:
    python scripts/train_ner.py --config configs/ner_xlmr.yaml
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mel.ner.train import train  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/ner_xlmr.yaml")
    args = parser.parse_args()
    train(args.config)


if __name__ == "__main__":
    main()
