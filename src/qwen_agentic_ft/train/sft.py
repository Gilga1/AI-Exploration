from __future__ import annotations

from pathlib import Path
from typing import Any

from qwen_agentic_ft.train.data import load_jsonl_dataset


def run_training(config: dict[str, Any], root: Path) -> dict[str, Any]:
    try:
        from unsloth import FastLanguageModel
    except ImportError as exc:
        raise ImportError(
            "Training dependencies are not installed. Run: python scripts/setup_env.py --extra train"
        ) from exc

    from trl import SFTConfig, SFTTrainer

    from qwen_agentic_ft.train.datasets import (
        build_hf_dataset,
        formatting_func_builder,
        resolve_data_paths,
    )

    train_path, val_path = resolve_data_paths(config, root)
    train_rows = load_jsonl_dataset(train_path)
    train_dataset = build_hf_dataset(train_rows)
    eval_dataset = None
    if val_path is not None:
        eval_dataset = build_hf_dataset(load_jsonl_dataset(val_path))

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=config["model_name"],
        max_seq_length=config["max_seq_length"],
        load_in_4bit=config.get("load_in_4bit", False),
        load_in_16bit=config.get("load_in_16bit", True),
        full_finetuning=config.get("full_finetuning", False),
    )

    lora_cfg = config["lora"]
    model = FastLanguageModel.get_peft_model(
        model,
        r=lora_cfg["r"],
        target_modules=lora_cfg["target_modules"],
        lora_alpha=lora_cfg["lora_alpha"],
        lora_dropout=lora_cfg.get("lora_dropout", 0),
        bias="none",
        use_gradient_checkpointing=lora_cfg.get("use_gradient_checkpointing", "unsloth"),
    )

    training_cfg = config["training"]
    output_dir = root / training_cfg["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    sft_args = SFTConfig(
        output_dir=str(output_dir),
        per_device_train_batch_size=training_cfg["per_device_train_batch_size"],
        per_device_eval_batch_size=training_cfg.get("per_device_eval_batch_size", 2),
        gradient_accumulation_steps=training_cfg["gradient_accumulation_steps"],
        learning_rate=training_cfg["learning_rate"],
        num_train_epochs=training_cfg["num_train_epochs"],
        warmup_ratio=training_cfg.get("warmup_ratio", 0.05),
        lr_scheduler_type=training_cfg.get("lr_scheduler_type", "cosine"),
        logging_steps=training_cfg.get("logging_steps", 10),
        save_steps=training_cfg.get("save_steps", 200),
        eval_steps=training_cfg.get("eval_steps", 200),
        eval_strategy=training_cfg.get("eval_strategy", "steps") if eval_dataset else "no",
        save_total_limit=training_cfg.get("save_total_limit", 3),
        bf16=training_cfg.get("bf16", True),
        optim=training_cfg.get("optim", "adamw_8bit"),
        seed=training_cfg.get("seed", 3407),
        report_to=training_cfg.get("report_to", "none"),
        max_steps=training_cfg.get("max_steps", -1),
        dataset_text_field=None,
        max_seq_length=config["max_seq_length"],
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        formatting_func=formatting_func_builder(tokenizer),
        args=sft_args,
    )

    train_result = trainer.train()
    trainer.save_model(str(output_dir / "final"))

    export_cfg = config.get("export", {})
    merged_dir = None
    if export_cfg.get("save_merged", False):
        merged_dir = root / export_cfg.get("merged_dir", output_dir / "merged")
        merged_dir.mkdir(parents=True, exist_ok=True)
        model.save_pretrained_merged(str(merged_dir), tokenizer, save_method="merged_16bit")

    return {
        "output_dir": str(output_dir),
        "merged_dir": str(merged_dir) if merged_dir else None,
        "train_samples": len(train_dataset),
        "eval_samples": len(eval_dataset) if eval_dataset else 0,
        "metrics": train_result.metrics,
    }
