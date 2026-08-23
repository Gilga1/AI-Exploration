# AI Agent Harness

Plugin-based agent orchestration harness where the core engine only knows interfaces. Tools, skills, agents, and connectors self-register at import time via decorators or YAML manifests.

## Quick start

```bash
bash scripts/setup_env.sh
source .venv/bin/activate

# Run tests
pytest -q

# Start API server
harness-serve
```

## API

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Liveness |
| `GET /admin/capabilities` | Registry + config plane introspection |
| `GET /admin/events` | Event ledger (waterfall UI feed) |
| `POST /v1/handle` | Orchestrator — route and dispatch skills or agents |

Example:

```bash
curl -X POST http://localhost:8000/v1/handle \
  -H 'Content-Type: application/json' \
  -d '{"message":"Turn my meeting notes into a PDF","skill_input":{"markdown":"# Notes\nHello","title":"Sync"}}'
```

## Layout

```
src/harness/           # Core library
  agents/              # DeclarativeAgent (YAML → deepagents)
  config/              # YAML config plane loader
  memory/              # MemoryManager + artifacts
  routing/             # Capability index + tiered router
  orchestrator/        # LangGraph dispatch + sub-agent spawning
  telemetry/           # OTel spans, event ledger, routing/tool/LLM events
harness/               # Plugin + config drop-zones
  tools/               # @register_tool
  skills/              # @register_skill
  agents/              # YAML agent manifests
  connectors/          # connector.yaml per data source
  context/             # business context packs
  models/              # LLM endpoint registry
  mcp/                 # MCP server registry
harness.settings.yaml
```

## Phases implemented

- **Phase 1** — Core interfaces, registries, bootstrap discovery
- **Phase 2** — YAML config plane, secret resolution, connector loading
- **Phase 3** — MemoryManager (working/checkpointer), RunContext, request models
- **Phase 4** — Tiered routing, LangGraph orchestrator, skill dispatch
- **Phase 5** — OTel GenAI spans, event ledger, operational vs content-capture sampling
- **Phase 7** — Sub-agent spawning via DeclarativeAgent + HandoffPacket/AgentResult

## Related project

Qwen agentic fine-tuning lives on a separate branch (`cursor/qwen-agentic-ft-setup-7e0b`) — not part of this harness codebase.
