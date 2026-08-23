# AI Exploration

This repository contains two related projects:

1. **AI Agent Harness** — plugin-based orchestration layer (Phase 1 scaffold)
2. **Qwen Agentic Fine-Tuning** — data extraction pipeline for model training

---

## AI Agent Harness (Phases 1–4)

Plugin-based agent harness where the core engine only knows interfaces. Concrete tools, skills, agents, and connectors self-register at import time via decorators.

### Quick start

```bash
bash scripts/setup_env.sh
source .venv/bin/activate

# Run tests
pytest -q

# Start API server
harness-serve
```

### API

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Liveness |
| `GET /admin/capabilities` | Registry + config plane introspection |
| `POST /v1/handle` | Orchestrator — route and dispatch skills |

Example:

```bash
curl -X POST http://localhost:8000/v1/handle \
  -H 'Content-Type: application/json' \
  -d '{"message":"Turn my meeting notes into a PDF","skill_input":{"markdown":"# Notes\nHello","title":"Sync"}}'
```

### Layout

```
src/harness/           # Core library
  config/              # YAML config plane loader (Phase 2)
  memory/              # MemoryManager + artifacts (Phase 3)
  routing/             # Capability index + tiered router (Phase 4)
  orchestrator/        # LangGraph skill dispatch (Phase 4)
  telemetry/           # RoutingDecisionEvent emission
harness/               # Plugin + config drop-zones
  tools/               # @register_tool
  skills/              # @register_skill (e.g. markdown_to_pdf)
  agents/              # @register_agent
  connectors/          # connector.yaml per data source
  context/             # business context packs
  models/              # LLM endpoint registry
  mcp/                 # MCP server registry
harness.settings.yaml
```

### Phases implemented

- **Phase 1** — Core interfaces, registries, bootstrap discovery
- **Phase 2** — YAML config plane, secret resolution, connector loading
- **Phase 3** — MemoryManager (working/checkpointer), RunContext, request models
- **Phase 4** — Tiered routing, LangGraph orchestrator, skill-only dispatch

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
