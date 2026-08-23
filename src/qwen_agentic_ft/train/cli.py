from __future__ import annotations

import argparse
import json
from pathlib import Path

from qwen_agentic_ft.config import ROOT
from qwen_agentic_ft.train.data import load_training_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fine-tune Qwen3.5 with Unsloth LoRA")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to training.yaml (default: config/training.yaml)",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="Override num_train_epochs with a fixed step count (useful for smoke tests)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = load_training_config(args.config)
    if args.max_steps is not None:
        config["training"]["max_steps"] = args.max_steps
        config["training"]["num_train_epochs"] = 1

    from qwen_agentic_ft.train.sft import run_training

    result = run_training(config, ROOT)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
