from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from qwen_agentic_ft.config import load_yaml


def load_training_config(path: Path | None = None) -> dict[str, Any]:
    if path is None:
        from qwen_agentic_ft.config import CONFIG_DIR

        path = CONFIG_DIR / "training.yaml"
    return load_yaml(path)


def load_jsonl_dataset(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows
