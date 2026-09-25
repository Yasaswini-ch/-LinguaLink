"""CLI: evaluate NER F1 and linking accuracy per language, write results tables.

Usage:
    python scripts/evaluate.py --config configs/eval.yaml
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
from transformers import AutoModelForTokenClassification, AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mel.data.linking_eval_set import filter_by_language, load_linking_eval_set  # noqa: E402
from mel.data.wikiann import load_wikiann  # noqa: E402
from mel.eval.linking_eval import run_linking_eval  # noqa: E402
from mel.eval.ner_eval import evaluate_ner_on_dataset  # noqa: E402
from mel.linking.disambiguate import Disambiguator  # noqa: E402
from mel.utils.config import load_config  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/eval.yaml")
    args = parser.parse_args()
    cfg = load_config(args.config)

    ner_model_path = cfg["ner"]["model_path"]
    print(f"Loading NER model from {ner_model_path} ...")
    ner_model = AutoModelForTokenClassification.from_pretrained(ner_model_path)
    ner_tokenizer = AutoTokenizer.from_pretrained(ner_model_path)

    linking_cfg = load_config(cfg["linking"]["linking_config"])
    disambiguator = Disambiguator(
        embedding_model=linking_cfg["disambiguation"]["embedding_model"],
        nil_threshold=linking_cfg["disambiguation"]["nil_threshold"],
    )
    kb_cache_path = linking_cfg["candidate_generation"]["local_dump_path"]
    linking_examples = load_linking_eval_set(cfg["linking"]["eval_set_path"])

    rows = []
    for lang in cfg["ner"]["languages"]:
        print(f"\n=== {lang} ===")

        ner_test = load_wikiann(lang)["test"]
        ner_metrics = evaluate_ner_on_dataset(ner_model, ner_tokenizer, ner_test)
        print(f"  NER F1: {ner_metrics['f1']:.4f}")

        lang_examples = filter_by_language(linking_examples, lang)
        linking_metrics = run_linking_eval(disambiguator, lang_examples, kb_cache_path)
        print(f"  Linking accuracy: {linking_metrics['accuracy']:.4f} "
              f"({linking_metrics['correct']}/{linking_metrics['total']})")

        rows.append(
            {
                "language": lang,
                "ner_f1": round(ner_metrics["f1"], 4),
                "linking_accuracy": round(linking_metrics["accuracy"], 4),
                "linking_n": linking_metrics["total"],
            }
        )

    df = pd.DataFrame(rows)
    out_dir = Path(cfg["output"]["results_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    if cfg["output"]["save_combined_table"]:
        df.to_csv(out_dir / "combined_results.csv", index=False)
    if cfg["output"]["save_per_language_csv"]:
        for row in rows:
            pd.DataFrame([row]).to_csv(out_dir / f"results_{row['language']}.csv", index=False)

    print("\n=== Combined results ===")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
