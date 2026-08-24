# Agent Harness — Setup Guide

Complete setup instructions for running the AI Agent Harness locally: real LLM endpoints, multi-agent orchestration, workflow templates, HITL approvals, memory, and observability.

---

## Prerequisites

| Requirement | Windows | macOS / Linux |
|-------------|---------|---------------|
| Python | 3.10+ from [python.org](https://www.python.org/downloads/) — check **Add to PATH** | `python3 --version` |
| Git | [git-scm.com](https://git-scm.com/download/win) | pre-installed or `brew install git` |
| API keys | Anthropic and/or OpenAI, Firecrawl (see below) | same |

> **Branch:** Use `cursor/agentic-harness` for the harness project. Qwen fine-tuning is on a separate branch (`cursor/qwen-agentic-ft-setup-7e0b`).

---

## 1. Clone and checkout

```powershell
git clone https://github.com/Gilga1/AI-Exploration.git
cd AI-Exploration
git checkout cursor/agentic-harness
```

---

## 2. Install (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If activation is blocked:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Install dependencies:

```powershell
python -m pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"
```

Or use the helper script:

```powershell
.\scripts\setup.ps1
```

### macOS / Linux

```bash
bash scripts/setup_env.sh
source .venv/bin/activate
```

---

## 3. Configure API keys

> **Yes, this is a FastAPI backend.** Run with `harness-serve` (Uvicorn). Dependencies are in `pyproject.toml` and `requirements.txt` — install via `pip install -e .` or `pip install -r requirements.txt`.

Copy the example env file:

```powershell
copy .env.example .env
```

Edit `.env` (or set environment variables in PowerShell):

```powershell
$env:HARNESS_SECRET_ANTHROPIC_API_KEY = "sk-ant-..."
$env:HARNESS_SECRET_FIRECRAWL_API_KEY = "fc-..."
# Optional:
$env:HARNESS_SECRET_OPENAI_API_KEY = "sk-..."
```

### Secret naming convention

Secrets in `harness/models/models.yaml` use `${secret:anthropic-api-key}` which resolves to:

```
HARNESS_SECRET_ANTHROPIC_API_KEY
```

| Config reference | Environment variable |
|------------------|---------------------|
| `${secret:anthropic-api-key}` | `HARNESS_SECRET_ANTHROPIC_API_KEY` |
| `${secret:openai-api-key}` | `HARNESS_SECRET_OPENAI_API_KEY` |
| `${secret:firecrawl-api-key}` | `HARNESS_SECRET_FIRECRAWL_API_KEY` |
| `${secret:azure-postgres-password}` | `HARNESS_SECRET_AZURE_POSTGRES_PASSWORD` |
| `${secret:azure-search-api-key}` | `HARNESS_SECRET_AZURE_SEARCH_API_KEY` |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key (OTel traces) |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key |
| `${env:REDIS_HOST}` | `REDIS_HOST` |

Get keys from:
- **Anthropic:** https://console.anthropic.com/
- **OpenAI:** https://platform.openai.com/api-keys
- **Firecrawl:** https://www.firecrawl.dev/
- **Langfuse:** https://langfuse.com/ (Settings → API Keys)

### Langfuse (OpenTelemetry export)

Traces export automatically when Langfuse keys are set:

```powershell
$env:LANGFUSE_PUBLIC_KEY = "pk-lf-..."
$env:LANGFUSE_SECRET_KEY = "sk-lf-..."
$env:LANGFUSE_BASE_URL = "https://cloud.langfuse.com"   # or US: https://us.cloud.langfuse.com
```

Verify at `GET /admin/capabilities` — `langfuse_enabled` should be `true`.

Spans use OTel GenAI conventions (`gen_ai.operation.name`, `gen_ai.agent.name`, etc.) and appear in your Langfuse project dashboard.

### Data connectors (Postgres, Snowflake, Azure AI Search)

See **[CONNECTORS.md](CONNECTORS.md)** for full configuration of Azure Postgres, Azure AI Search, Snowflake, and MCP.

Quick install for optional backends:

```powershell
pip install -r requirements-azure.txt      # Azure AI Search
pip install -r requirements-snowflake.txt  # Snowflake
```

---

## 4. Verify installation

```powershell
pytest -q
```

Expected: **43 passed**.

---

## 5. Start the server

```powershell
harness-serve
```

Server: **http://localhost:8000**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Liveness |
| `/admin/capabilities` | GET | List tools, skills, agents, connectors |
| `/admin/workflows` | GET | Loaded workflow templates |
| `/admin/plans` | GET | Recent execution plan snapshots |
| `/admin/plans/{plan_id}` | GET | Plan detail + task results |
| `/admin/plans/{plan_id}/waterfall` | GET | Event hierarchy for a plan run |
| `/admin/metrics` | GET | Plan metrics + registry counts |
| `/admin/events` | GET | Telemetry event ledger |
| `/admin/approvals` | GET | Pending HITL approvals |
| `/v1/handle` | POST | Route, plan, or dispatch request |
| `/v1/resume` | POST | Resume after HITL approval |
| `/v1/runs/{trace_id}/events` | GET | SSE stream of run events |

---

## 6. How requests are handled

### Single-agent path

For simple requests (or when `orchestration.mode` is `single`):

1. **Router** scores registered skills/agents via the capability index
2. **Dispatch** runs the top match (skill `execute()` or agent `run()`)
3. **Response** includes output, artifacts, and trace events

### Multi-agent path

For complex or cross-domain requests (or when `orchestration.mode` is `multi`):

1. **Planner** builds an `ExecutionPlan`:
   - `auto` — workflow template match first, then LLM/heuristic
   - `template` — YAML workflows only
   - `hybrid` — template structure + LLM-refined objectives
   - `llm` — LLM plans from capability catalog
2. **Plan HITL** — response status `awaiting_plan_approval`; human must approve before tasks run
3. **DAG executor** runs tasks in parallel batches respecting `depends_on`, concurrency limits, and failure policy
4. **Synthesizer** agent merges task outputs into a final response (always runs last, not in the plan)
5. **Observability** — plan snapshot stored, per-task events with `duration_ms`, waterfall available via admin API

### Orchestration settings (`harness.settings.yaml`)

```yaml
orchestration_mode: auto              # auto | single | multi
orchestration_require_plan_approval: true
orchestration_planner: auto           # auto | llm | template | hybrid
orchestration_workflow_match_threshold: 0.6
orchestration_max_tasks: 5
orchestration_synthesizer_agent: synthesizer
orchestration_parallel: true
orchestration_max_parallel: 3
orchestration_failure_policy: continue   # continue | fail_fast | retry_once
orchestration_continue_on_failure: true
```

Override per request:

```json
{
  "message": "Research competitor Acme and analyze advisor Jane Doe sales.",
  "orchestration": { "mode": "multi" }
}
```

---

## 7. Test with real endpoints

### Skill: Markdown → PDF (real PDF rendering via fpdf2)

```powershell
$body = @{
  message = "Turn my meeting notes into a PDF"
  skill_input = @{
    markdown = "# Q3 Pipeline Review`n`n- Closed 3 deals`n- Follow up with Acme"
    title = "Pipeline Sync"
  }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method POST -Uri http://localhost:8000/v1/handle `
  -ContentType "application/json" -Body $body
```

### Multi-agent: competitive sales brief (workflow template)

When the message matches tags in `harness/workflows/competitive_sales_brief.yaml`, the planner uses the template instead of LLM planning:

```powershell
$body = @{
  message = "Research competitor Acme Corp and analyze advisor Jane Doe product sales."
  orchestration = @{ mode = "multi" }
} | ConvertTo-Json -Depth 5

$result = Invoke-RestMethod -Method POST -Uri http://localhost:8000/v1/handle `
  -ContentType "application/json" -Body $body
# $result.status → awaiting_plan_approval
# $result.plan.tasks → competitor_research + agentic_analyzer

$resume = @{
  task_id = $result.task_id
  thread_id = $result.thread_id
  decisions = @(@{ type = "approve" })
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method POST -Uri http://localhost:8000/v1/resume `
  -ContentType "application/json" -Body $resume
```

### Agent: Competitor research (single-agent, Firecrawl + LLM)

Requires `HARNESS_SECRET_ANTHROPIC_API_KEY` and `HARNESS_SECRET_FIRECRAWL_API_KEY`.

```powershell
$body = @{
  message = "Research competitor Acme Corp and draft a positioning brief."
  orchestration = @{ mode = "single" }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method POST -Uri http://localhost:8000/v1/handle `
  -ContentType "application/json" -Body $body
```

### Stub mode (no API keys)

For offline testing, set in `harness.settings.yaml`:

```yaml
force_stub_models: true
```

Or in PowerShell for one session:

```powershell
$env:HARNESS_FORCE_STUB_MODELS = "true"
```

Stub mode uses deterministic responses; Firecrawl falls back to placeholder search results when no API key is set.

---

## 8. Human-in-the-loop (HITL)

There are two HITL gates:

### Plan approval (multi-agent)

Every multi-step plan requires approval before tasks execute. The approval `task_id` is the plan ID.

1. Send a multi-agent request → `status: awaiting_plan_approval`
2. Review `plan.tasks` in the response
3. Resume with `decisions: [{ "type": "approve" }]` or `"reject"`

### Tool approval (per-agent)

Tools listed in an agent's `interrupt_tools` pause execution mid-run.

Example in `harness/agents/competitor_research.yaml`:

```yaml
interrupt_tools:
  - render_pdf_from_html
```

Flow:

1. Agent tries an interrupt tool → `status: awaiting_approval`
2. List pending: `GET /admin/approvals`
3. Resume with `approve`, `edit`, or `reject`

```powershell
$resume = @{
  task_id = "<task_id from response>"
  thread_id = "<thread_id from response>"
  decisions = @(@{ type = "approve" })
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method POST -Uri http://localhost:8000/v1/resume `
  -ContentType "application/json" -Body $resume
```

---

## 9. Workflow templates

Add repeatable multi-agent plans under **`harness/workflows/`** as YAML files. Templates are loaded at bootstrap and matched by tags/patterns in the user message.

Example: `harness/workflows/competitive_sales_brief.yaml`

```yaml
name: competitive_sales_brief
description: Research a competitor and analyze advisor sales, then synthesize.
match_tags: [competitor, sales, advisor]
variables:
  competitor:
    extract: "competitor\\s+([A-Za-z0-9][\\w .'-]+?)(?=\\s+and\\b|...)"
    default: "the competitor"
  advisor_name:
    extract: "advisor\\s+([A-Za-z][A-Za-z .'-]+?)(?=\\s+sales\\b|...)"
    default: "the advisor"
tasks:
  - task_id: t1
    title: "Research {{competitor}}"
    assignee: { kind: agent, name: competitor_research }
    objective: "Research competitor {{competitor}}"
  - task_id: t2
    title: "Analyze {{advisor_name}} sales"
    assignee: { kind: agent, name: agentic_analyzer }
    objective: "Analyze advisor {{advisor_name}} product sales"
```

List loaded templates: `GET /admin/workflows`

The synthesizer agent is appended automatically — do not include it in workflow tasks.

---

## 10. Business context

Add domain knowledge under **`harness/context/`** as YAML files.

Example: `harness/context/glossary.yaml`

```yaml
name: sales_glossary
description: Core business terms for the sales/CRM domain
scope:
  agent_tags: ["sales", "crm"]
always_inject: true
entries:
  - term: "AUM"
    definition: "Assets Under Management — total market value..."
rules:
  - "Never quote a specific AUM figure without citing the source."
```

Wire to an agent:

```yaml
context_packs:
  - sales_glossary
```

Restart the server after changes.

---

## 11. Adding capabilities

### New tool (`harness/tools/my_tool.py`)

```python
from pydantic import BaseModel
from harness.core.models import ExecutionMode, ToolSpec
from harness.core.context import RunContext
from harness.registry import register_tool

class MyInput(BaseModel):
    query: str

class MyOutput(BaseModel):
    result: str

@register_tool
class MyTool:
    spec = ToolSpec(
        name="my_tool",
        description="Does something useful.",
        input_schema=MyInput,
        output_schema=MyOutput,
        side_effects=False,
        execution_mode=ExecutionMode.IN_PROCESS,
    )

    async def run(self, args: MyInput, *, context: RunContext) -> MyOutput:
        return MyOutput(result=args.query)
```

### New skill (`harness/skills/my_skill.py`)

Use `@register_skill`, declare `required_tools`, implement `execute()`. See `harness/skills/markdown_to_pdf.py`.

### New agent (`harness/agents/my_agent.yaml`)

```yaml
name: my_agent
description: What this agent does.
capability_tags: [tag1]
system_prompt: |
  You are a helpful agent.
context_packs: [sales_glossary]
allowed_tools: [web_search]
model_config_ref: primary_reasoner
max_steps: 20
max_tokens_budget: 40000
interrupt_tools: []   # tools requiring HITL
```

### New workflow (`harness/workflows/my_workflow.yaml`)

Define `match_tags`, `variables`, and `tasks` as shown in section 9. Restart `harness-serve` after any plugin change.

---

## 12. LLM models (`harness/models/models.yaml`)

```yaml
models:
  - name: primary_reasoner
    provider: anthropic          # anthropic | openai | stub
    model: claude-sonnet-4-20250514
    max_tokens: 8192
    api_key: ${secret:anthropic-api-key}
  - name: fast_router
    provider: anthropic
    model: claude-haiku-4-5-20251001
    max_tokens: 1024
    api_key: ${secret:anthropic-api-key}
```

- `primary_reasoner` — agent reasoning
- `fast_router` — planner and routing disambiguation

Enable LLM-based routing disambiguation in `harness.settings.yaml`:

```yaml
routing_use_llm: true
```

---

## 13. MCP connectors (`harness/mcp/servers.yaml`)

Enable external tool servers (Jira, Confluence, etc.):

```yaml
servers:
  jira:
    transport: stdio
    command: "npx"
    args: ["-y", "@yourorg/jira-mcp-server"]
    enabled: true
```

MCP tools are registered at bootstrap with `requires_approval: true` by default.

---

## 14. Observability

### Realtime event stream

```bash
curl -N http://localhost:8000/v1/runs/<trace_id>/events
```

### Plan waterfall (after a multi-agent run)

```bash
curl http://localhost:8000/admin/plans/<plan_id>/waterfall
```

### Langfuse

Set `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` for OTel export to Langfuse dashboard.

---

## 15. Data persistence

| Store | Path (default) | Purpose |
|-------|----------------|---------|
| Event ledger | `data/harness_events.db` | Telemetry / waterfall UI |
| Episodic memory | `data/harness_episodic.db` | Cross-session recall |
| HITL approvals | `data/harness_approvals.db` | Pending interrupts |
| Plan snapshots | `data/harness_plans.db` | Execution plans + task results |

Configure paths in `harness.settings.yaml`:

```yaml
telemetry_ledger_db_path: data/harness_events.db
episodic_db_path: data/harness_episodic.db
approvals_db_path: data/harness_approvals.db
orchestration_plans_db_path: data/harness_plans.db
```

---

## 16. What's still pending

| Feature | Status |
|---------|--------|
| Phase 5 — dynamic sub-agent profiles | Planned (see `spec/phase-5-dynamic-sub-agents.md`) |
| Reflective / nightly memory curation | Not implemented |
| Async agent workers (Celery/queue) | Not implemented |
| Sandbox microVM execution | Not implemented |
| OTel export to Datadog/Honeycomb | Not yet implemented |
| Hot reload of plugins | Restart required |

---

## 17. Troubleshooting

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError: harness` | Activate venv: `.\.venv\Scripts\Activate.ps1` |
| Firecrawl returns stub message | Set `HARNESS_SECRET_FIRECRAWL_API_KEY` |
| Agent fails with provider error | Set `HARNESS_SECRET_ANTHROPIC_API_KEY` or use `force_stub_models: true` |
| Connector health check fails | Set `connector_health_check: false` in `harness.settings.yaml` |
| Port 8000 in use | Change `port: 8001` in `harness.settings.yaml` |
| Plan not matching workflow | Check `GET /admin/workflows`; lower `orchestration_workflow_match_threshold` or add `match_patterns` |

---

## Project layout

```
harness/                  # Plugin drop-zones (your code + config)
  tools/                  # @register_tool
  skills/                 # @register_skill
  agents/                 # YAML agents
  workflows/              # YAML multi-agent plan templates
  context/                # Business context packs
  models/                 # LLM endpoints
  connectors/             # Data sources
  mcp/                    # MCP servers
src/harness/              # Core engine (rarely edit)
spec/                     # Orchestration phase specs
harness.settings.yaml     # Runtime settings
.env                      # API keys (gitignored)
SETUP.md                  # This file
```
