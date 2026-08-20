# Qwen Agentic Fine-Tuning

Fine-tune **Qwen3.5-2B-Instruct** on LangChain / LangGraph / Deep Agents code patterns.

Works on **Windows, macOS, and Linux** via Python entry points (no bash required).

## Quick start

### Windows (PowerShell)

```powershell
python scripts/setup_env.py --extra dev
.\.venv\Scripts\Activate.ps1

# Extract training data
python scripts/extract_data.py
# or: .\scripts\extract_data.ps1

# Train (CUDA GPU required)
python scripts/setup_env.py --extra train
python scripts/train.py
# or: .\scripts\train.ps1
```

### Windows (CMD)

```bat
python scripts\setup_env.py --extra dev
.venv\Scripts\activate.bat
python scripts\extract_data.py
python scripts\setup_env.py --extra train
python scripts\train.py
```

### macOS / Linux

```bash
python3 scripts/setup_env.py --extra dev
source .venv/bin/activate
python scripts/extract_data.py
python scripts/setup_env.py --extra train
python scripts/train.py
```

## Outputs

**Extraction**
- `data/processed/train.jsonl`
- `data/processed/val.jsonl`
- `data/processed/metadata.json`

**Training**
- `outputs/qwen-agentic-lora/final/` — LoRA adapter
- `outputs/qwen-agentic-merged/` — optional merged model

## Project layout

```
config/
  repos.yaml          # GitHub repos to clone
  extraction.yaml     # Extraction filters and prompts
  training.yaml       # LoRA + SFT hyperparameters
scripts/
  setup_env.py        # Cross-platform setup (use this)
  extract_data.py
  train.py
  *.bat / *.ps1       # Windows wrappers
src/qwen_agentic_ft/
  extract/            # GitHub → JSONL pipeline
  train/              # Unsloth LoRA training
```

## Training notes

- Requires an **NVIDIA GPU** with CUDA for Unsloth
- Default: bf16 LoRA on `Qwen/Qwen3.5-2B-Instruct`, ~5 GB VRAM at r=16, seq 2048
- Edit `config/training.yaml` to tune batch size, learning rate, epochs
- Smoke test: `python scripts/train.py --max-steps 10`

On Windows, if `unsloth` install fails, follow [Unsloth install docs](https://github.com/unslothai/unsloth) for your CUDA version, then rerun `python scripts/setup_env.py --extra train`.

## Context length

Qwen3.5-2B supports very long context at **inference**, but LoRA training seq length is bounded by VRAM. Start at 2048; increase `max_seq_length` in `config/training.yaml` if your GPU allows.
