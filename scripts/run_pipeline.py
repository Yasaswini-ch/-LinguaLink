"""CLI: run the full NER -> linking pipeline on a single input sentence.

Usage:
    python scripts/run_pipeline.py --lang hi --text "मोदी ने बर्लिन में मर्केल से मुलाकात की।"
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mel.linking.pipeline import EntityLinkingPipeline  # noqa: E402
from mel.utils.config import load_config  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", required=True, choices=["en", "hi", "es", "de"])
    parser.add_argument("--text", required=True)
    parser.add_argument("--ner-config", default="configs/ner_xlmr.yaml")
    parser.add_argument("--linking-config", default="configs/linking.yaml")
    args = parser.parse_args()

    ner_cfg = load_config(args.ner_config)
    linking_cfg = load_config(args.linking_config)

    pipeline = EntityLinkingPipeline(
        ner_model_path=ner_cfg["inference_model_path"],
        embedding_model=linking_cfg["disambiguation"]["embedding_model"],
        nil_threshold=linking_cfg["disambiguation"]["nil_threshold"],
        context_window_tokens=linking_cfg["disambiguation"]["context_window_tokens"],
        kb_cache_path=linking_cfg["candidate_generation"]["local_dump_path"],
    )

    results = pipeline.run(args.text, args.lang)
    for r in results:
        entity = r.linked_entity
        if entity.is_nil:
            print(f"{r.mention.text:20s} [{r.mention.label}]  -> NIL (score={entity.confidence:.2f})")
        else:
            print(
                f"{r.mention.text:20s} [{r.mention.label}]  -> {entity.qid} "
                f"({entity.label}, confidence={entity.confidence:.2f})"
            )


if __name__ == "__main__":
    main()
