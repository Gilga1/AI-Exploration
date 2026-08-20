from __future__ import annotations

from pathlib import Path
from typing import Any


def build_hf_dataset(rows: list[dict[str, Any]]):
    from datasets import Dataset

    messages = [row["messages"] for row in rows]
    metadata = {
        key: [row.get(key) for row in rows]
        for key in ("repo", "framework", "source_file", "patterns")
        if any(key in row for row in rows)
    }
    return Dataset.from_dict({"messages": messages, **metadata})


def formatting_func_builder(tokenizer):
    def formatting_func(examples: dict[str, list]) -> list[str]:
        texts: list[str] = []
        for messages in examples["messages"]:
            texts.append(
                tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=False,
                )
            )
        return texts

    return formatting_func


def resolve_data_paths(config: dict[str, Any], root: Path) -> tuple[Path, Path | None]:
    data_cfg = config["data"]
    train_path = root / data_cfg["train_file"]
    val_path = root / data_cfg["val_file"]
    if not train_path.exists():
        raise FileNotFoundError(f"Training file not found: {train_path}")
    if not val_path.exists():
        return train_path, None
    return train_path, val_path
