"""YAML config loading helper shared across scripts."""
from pathlib import Path
import yaml


def load_config(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_languages(path: str | Path = "configs/languages.yaml") -> list[dict]:
    return load_config(path)["languages"]
