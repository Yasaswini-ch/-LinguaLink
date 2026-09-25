"""Evaluate NER predictions against WikiAnn gold labels (precision/recall/F1)."""
import torch
from seqeval.metrics import classification_report, f1_score

from mel.data.wikiann import LABEL_LIST


def evaluate_ner(pred_labels: list[list[str]], gold_labels: list[list[str]]) -> dict:
    return {
        "f1": f1_score(gold_labels, pred_labels),
        "report": classification_report(gold_labels, pred_labels, output_dict=True),
    }


@torch.no_grad()
def evaluate_ner_on_dataset(model, tokenizer, dataset, max_length: int = 128, batch_size: int = 32) -> dict:
    """Run the token-classification model over a WikiAnn split and score it with seqeval.

    `dataset` rows must have `tokens` (pre-tokenized word list) and `ner_tags`
    (gold label ids, indexing into LABEL_LIST) as produced by mel.data.wikiann.
    """
    device = next(model.parameters()).device
    model.eval()

    all_preds, all_golds = [], []

    for start in range(0, len(dataset), batch_size):
        batch = dataset[start : start + batch_size]
        tokens_batch = batch["tokens"]
        gold_tags_batch = batch["ner_tags"]

        encoded = tokenizer(
            tokens_batch,
            truncation=True,
            max_length=max_length,
            is_split_into_words=True,
            padding=True,
            return_tensors="pt",
        ).to(device)

        logits = model(**encoded).logits
        pred_ids = torch.argmax(logits, dim=-1).cpu().numpy()

        for i, gold_tags in enumerate(gold_tags_batch):
            word_ids = encoded.word_ids(batch_index=i)
            seen = set()
            pred_seq, gold_seq = [], []
            for pos, word_id in enumerate(word_ids):
                if word_id is None or word_id in seen:
                    continue
                seen.add(word_id)
                pred_seq.append(LABEL_LIST[pred_ids[i][pos]])
                gold_seq.append(LABEL_LIST[gold_tags[word_id]])
            all_preds.append(pred_seq)
            all_golds.append(gold_seq)

    return evaluate_ner(all_preds, all_golds)
