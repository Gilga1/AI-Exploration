# Agent Harness — Setup Guide

Complete setup instructions for running the AI Agent Harness locally with real LLM endpoints, Firecrawl search, and human-in-the-loop (HITL) approvals.

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
| `${env:REDIS_HOST}` | `REDIS_HOST` |

Get keys from:
- **Anthropic:** https://console.anthropic.com/
- **OpenAI:** https://platform.openai.com/api-keys
- **Firecrawl:** https://www.firecrawl.dev/

---

## 4. Verify installation

```powershell
pytest -q
```

Expected: **14 passed**.

---

## 5. Start the server

```powershell
harness-serve
```

Server: **http://localhost:8000**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Liveness |
| `/admin/capabilities` | GET | List tools, skills, agents |
| `/admin/events` | GET | Telemetry event ledger |
| `/admin/approvals` | GET | Pending HITL approvals |
| `/v1/handle` | POST | Route and dispatch request |
| `/v1/resume` | POST | Resume after HITL approval |

---

## 6. Test with real endpoints

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

### Agent: Competitor research (Firecrawl + LLM)

Requires `HARNESS_SECRET_ANTHROPIC_API_KEY` and `HARNESS_SECRET_FIRECRAWL_API_KEY`.

The default agent `competitor_research` uses `primary_reasoner` (Claude). Ensure `harness/agents/competitor_research.yaml` has:

```yaml
model_config_ref: primary_reasoner
```

```powershell
$body = @{
  message = "Research competitor Acme Corp and draft a positioning brief."
} | ConvertTo-Json

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

## 7. Human-in-the-loop (HITL)

Tools listed in an agent's `interrupt_tools` pause execution and require approval.

Example in `harness/agents/competitor_research.yaml`:

```yaml
interrupt_tools:
  - render_pdf_from_html
```

### Flow

1. Send a request that triggers the agent and causes an interrupt (e.g. agent tries to render a PDF).
2. Response status: `awaiting_approval` with `task_id` and `interrupts`.
3. List pending approvals:

```powershell
Invoke-RestMethod http://localhost:8000/admin/approvals
```

4. Resume with approval:

```powershell
$resume = @{
  task_id = "<task_id from response>"
  thread_id = "<thread_id from response>"
  decisions = @(@{ type = "approve" })
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method POST -Uri http://localhost:8000/v1/resume `
  -ContentType "application/json" -Body $resume
```

Decision types: `approve`, `edit`, `reject`.

---

## 8. Business context

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

## 9. Adding capabilities

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

Restart `harness-serve` after any plugin change.

---

## 10. LLM models (`harness/models/models.yaml`)

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

Enable LLM-based routing disambiguation in `harness.settings.yaml`:

```yaml
routing_use_llm: true
```

---

## 11. MCP connectors (`harness/mcp/servers.yaml`)

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

## 12. Data persistence

| Store | Path (default) | Purpose |
|-------|----------------|---------|
| Event ledger | `data/harness_events.db` | Telemetry / waterfall UI |
| Episodic memory | `data/harness_episodic.db` | Cross-session recall |
| HITL approvals | `data/harness_approvals.db` | Pending interrupts |

Configure paths in `harness.settings.yaml`:

```yaml
telemetry_ledger_db_path: data/harness_events.db
episodic_db_path: data/harness_episodic.db
approvals_db_path: data/harness_approvals.db
```

---

## 13. What's still pending

| Feature | Status |
|---------|--------|
| Reflective / nightly memory curation | Not implemented |
| Async agent workers (Celery/queue) | Not implemented |
| Sandbox microVM execution | Not implemented |
| OTel export to Datadog/Honeycomb | In-memory only |
| Hot reload of plugins | Restart required |

---

## 14. Troubleshooting

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError: harness` | Activate venv: `.\.venv\Scripts\Activate.ps1` |
| Firecrawl returns stub message | Set `HARNESS_SECRET_FIRECRAWL_API_KEY` |
| Agent fails with provider error | Set `HARNESS_SECRET_ANTHROPIC_API_KEY` or use `force_stub_models: true` |
| Connector health check fails | Set `connector_health_check: false` in `harness.settings.yaml` |
| Port 8000 in use | Change `port: 8001` in `harness.settings.yaml` |

---

## Project layout

```
harness/                  # Plugin drop-zones (your code + config)
  tools/                  # @register_tool
  skills/                 # @register_skill
  agents/                 # YAML agents
  context/                # Business context packs
  models/                 # LLM endpoints
  connectors/             # Data sources
  mcp/                    # MCP servers
src/harness/              # Core engine (rarely edit)
harness.settings.yaml     # Runtime settings
.env                      # API keys (gitignored)
SETUP.md                  # This file
```
