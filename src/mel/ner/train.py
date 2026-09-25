"""Fine-tune a multilingual token-classification model (XLM-R/mBERT) on WikiAnn."""
import inspect

import numpy as np
from datasets import concatenate_datasets, DatasetDict
from seqeval.metrics import f1_score, precision_score, recall_score
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    DataCollatorForTokenClassification,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
)

from mel.data.casual_augmentation import load_casual_augmentation
from mel.data.wikiann import LABEL_LIST, load_wikiann_multilingual
from mel.utils.config import load_config


def build_model_and_tokenizer(checkpoint: str, num_labels: int):
    tokenizer = AutoTokenizer.from_pretrained(checkpoint)
    id2label = {i: label for i, label in enumerate(LABEL_LIST)}
    label2id = {label: i for i, label in enumerate(LABEL_LIST)}
    model = AutoModelForTokenClassification.from_pretrained(
        checkpoint, num_labels=num_labels, id2label=id2label, label2id=label2id
    )
    return model, tokenizer


def tokenize_and_align_labels(examples, tokenizer, max_length: int):
    tokenized = tokenizer(
        examples["tokens"],
        truncation=True,
        max_length=max_length,
        is_split_into_words=True,
    )
    all_labels = []
    for i, labels in enumerate(examples["ner_tags"]):
        word_ids = tokenized.word_ids(batch_index=i)
        prev_word_id = None
        label_ids = []
        for word_id in word_ids:
            if word_id is None:
                label_ids.append(-100)
            elif word_id != prev_word_id:
                label_ids.append(labels[word_id])
            else:
                label_ids.append(-100)
            prev_word_id = word_id
        all_labels.append(label_ids)
    tokenized["labels"] = all_labels
    return tokenized


def build_multilingual_splits(
    languages: list[str],
    train_split: str,
    val_split: str,
    test_split: str,
    max_train_examples: int | None = None,
    max_eval_examples: int | None = None,
    augmentation_path: str | None = None,
) -> DatasetDict:
    """Load WikiAnn for each language and concatenate splits into one multilingual dataset.

    `max_train_examples`/`max_eval_examples` cap the (post-concatenation, shuffled)
    dataset size — used for quick local smoke tests; leave unset for real training runs.

    `augmentation_path`, if given, points to a JSONL file of extra hand-labeled
    {tokens, ner_tags} examples (see mel.data.casual_augmentation) that get
    mixed into the *training* split only — used to cover casual/conversational
    text patterns WikiAnn's Wikipedia-derived data doesn't contain.
    """
    per_lang = load_wikiann_multilingual(languages)

    train = concatenate_datasets([per_lang[lang][train_split] for lang in languages]).shuffle(seed=42)
    val = concatenate_datasets([per_lang[lang][val_split] for lang in languages]).shuffle(seed=42)
    test = concatenate_datasets([per_lang[lang][test_split] for lang in languages]).shuffle(seed=42)

    if max_train_examples:
        train = train.select(range(min(max_train_examples, len(train))))
    if max_eval_examples:
        val = val.select(range(min(max_eval_examples, len(val))))
        test = test.select(range(min(max_eval_examples, len(test))))

    if augmentation_path:
        augmentation = load_casual_augmentation(augmentation_path)
        # Align schemas before concatenating: WikiAnn carries extra langs/spans
        # columns the augmentation set doesn't have.
        train = concatenate_datasets(
            [train.select_columns(["tokens", "ner_tags"]), augmentation]
        ).shuffle(seed=42)

    return DatasetDict(train=train, validation=val, test=test)


def make_compute_metrics(label_list: list[str]):
    def compute_metrics(eval_pred):
        predictions, labels = eval_pred
        predictions = np.argmax(predictions, axis=2)

        true_predictions = [
            [label_list[p] for p, l in zip(pred_row, label_row) if l != -100]
            for pred_row, label_row in zip(predictions, labels)
        ]
        true_labels = [
            [label_list[l] for p, l in zip(pred_row, label_row) if l != -100]
            for pred_row, label_row in zip(predictions, labels)
        ]

        return {
            "precision": precision_score(true_labels, true_predictions),
            "recall": recall_score(true_labels, true_predictions),
            "f1": f1_score(true_labels, true_predictions),
        }

    return compute_metrics


def train(config_path: str = "configs/ner_xlmr.yaml") -> None:
    cfg = load_config(config_path)
    model_cfg = cfg["model"]
    data_cfg = cfg["data"]
    train_cfg = cfg["training"]

    model, tokenizer = build_model_and_tokenizer(
        model_cfg["base_checkpoint"], model_cfg["num_labels"]
    )

    raw_datasets = build_multilingual_splits(
        data_cfg["languages"],
        data_cfg["train_split"],
        data_cfg["val_split"],
        data_cfg["test_split"],
        max_train_examples=data_cfg.get("max_train_examples"),
        max_eval_examples=data_cfg.get("max_eval_examples"),
        augmentation_path=data_cfg.get("augmentation_path"),
    )

    tokenized_datasets = raw_datasets.map(
        lambda examples: tokenize_and_align_labels(examples, tokenizer, model_cfg["max_seq_length"]),
        batched=True,
        remove_columns=raw_datasets["train"].column_names,
    )

    data_collator = DataCollatorForTokenClassification(tokenizer)

    # transformers has renamed/restructured a handful of TrainingArguments
    # fields across releases (e.g. eval_strategy/evaluation_strategy,
    # warmup_ratio placement). Rather than pin an exact version, build the
    # full desired kwarg set and drop anything the installed TrainingArguments
    # doesn't accept, so this keeps working across reasonable version drift.
    desired_args = dict(
        output_dir=train_cfg["output_dir"],
        learning_rate=train_cfg["learning_rate"],
        per_device_train_batch_size=train_cfg["train_batch_size"],
        per_device_eval_batch_size=train_cfg["eval_batch_size"],
        num_train_epochs=train_cfg["num_epochs"],
        warmup_ratio=train_cfg["warmup_ratio"],
        weight_decay=train_cfg["weight_decay"],
        eval_strategy=train_cfg["eval_strategy"],
        evaluation_strategy=train_cfg["eval_strategy"],  # older transformers name
        save_strategy=train_cfg["save_strategy"],
        metric_for_best_model=train_cfg["metric_for_best_model"],
        load_best_model_at_end=True,
        seed=train_cfg["seed"],
        report_to=[],
    )

    supported_params = set(inspect.signature(TrainingArguments.__init__).parameters)
    dropped = [k for k in desired_args if k not in supported_params]
    if dropped:
        print(f"TrainingArguments in this transformers version doesn't support {dropped}; skipping.")
    args = TrainingArguments(**{k: v for k, v in desired_args.items() if k in supported_params})

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=tokenized_datasets["train"],
        eval_dataset=tokenized_datasets["validation"],
        data_collator=data_collator,
        processing_class=tokenizer,
        compute_metrics=make_compute_metrics(LABEL_LIST),
        callbacks=[EarlyStoppingCallback(early_stopping_patience=train_cfg["early_stopping_patience"])],
    )

    trainer.train()

    test_metrics = trainer.evaluate(tokenized_datasets["test"])
    print("Test metrics:", test_metrics)

    trainer.save_model(train_cfg["output_dir"])
    tokenizer.save_pretrained(train_cfg["output_dir"])


if __name__ == "__main__":
    train()
