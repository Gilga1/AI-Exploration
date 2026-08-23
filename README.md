# AI Exploration

This repository contains two related projects:

1. **AI Agent Harness** — plugin-based orchestration layer (Phase 1 scaffold)
2. **Qwen Agentic Fine-Tuning** — data extraction pipeline for model training

---

## AI Agent Harness (Phase 1)

Plugin-based agent harness where the core engine only knows interfaces. Concrete tools, skills, agents, and connectors self-register at import time via decorators.

### Quick start

```bash
bash scripts/setup_env.sh
source .venv/bin/activate

# Run tests
pytest -q

# Start API server (health + /admin/capabilities)
harness-serve
```

### Layout

```
src/harness/           # Core library (registry, bootstrap, API)
harness/               # Plugin drop-zones (code plane)
  tools/               # @register_tool implementations
  skills/              # @register_skill implementations
  agents/              # @register_agent implementations
  connectors/          # @register_connector implementations
harness.settings.yaml  # Scan paths and bootstrap config
```

### Adding a tool

Drop a file in `harness/tools/`, restart the server:

```python
from harness.registry import register_tool

@register_tool
class MyTool:
    spec = ToolSpec(...)
    async def run(self, args, *, context): ...
```

Verify registration: `GET /admin/capabilities`

---

## Qwen Agentic Fine-Tuning

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

## Training (local CUDA machine)

Install the training stack on a GPU machine:

```bash
pip install -e ".[train]"
```

Use Unsloth + bf16 LoRA with `Qwen/Qwen3.5-2B-Instruct`. See the Notion implementation plan for hyperparameters.

## Notes on context length

Qwen3.5-2B supports very long context at **inference**, but LoRA training seq length is still bounded by local VRAM. Start at 2048–4096 for training; use long context at inference when providing multi-file repo context.
