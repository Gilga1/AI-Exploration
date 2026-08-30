# Qwen Agentic Fine-Tuning

Fine-tune **Qwen3.5-2B-Instruct** on LangChain / LangGraph / Deep Agents code patterns.

## Quick start

```bash
# 1. Create venv and install extraction deps
bash scripts/setup_env.sh
source .venv/bin/activate

# 2. Clone Tier-1 repos and extract training JSONL
bash scripts/extract_data.sh

# Outputs:
#   data/processed/train.jsonl
#   data/processed/val.jsonl
#   data/processed/metadata.json
```

## Project layout

```
config/
  repos.yaml          # GitHub repos to clone
  extraction.yaml     # Filters, prompts, output paths
src/qwen_agentic_ft/  # Extraction pipeline
scripts/
  setup_env.sh
  extract_data.sh
data/
  repos/              # Shallow git clones (gitignored)
  processed/          # train/val JSONL (gitignored)
eval/
  golden_prompts.template.jsonl
```

## Semantic Layer Shell

A new **Intelligence Hub pilot** lives under [`semantic-layer-shell/`](semantic-layer-shell/). See that directory's README for backend/frontend setup.

## Training (local CUDA machine)

Install the training stack on a GPU machine:

```bash
pip install -e ".[train]"
```

Use Unsloth + bf16 LoRA with `Qwen/Qwen3.5-2B-Instruct`. See the Notion implementation plan for hyperparameters.

## Notes on context length

Qwen3.5-2B supports very long context at **inference**, but LoRA training seq length is still bounded by local VRAM. Start at 2048–4096 for training; use long context at inference when providing multi-file repo context.
