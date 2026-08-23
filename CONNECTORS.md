# Connectors, MCP, and Data Access in the Agent Harness

The harness is a **FastAPI backend** (`harness-serve` → Uvicorn). Dependencies live in `pyproject.toml` and `requirements.txt` — there is no separate requirements file for FastAPI because the project uses modern Python packaging (`pip install -e .`).

This guide explains how agents, skills, and tools reach **Postgres**, **Snowflake**, **Azure AI Search**, and **MCP** data sources.

---

## Architecture: three ways to access data

```
                    POST /v1/handle
                          │
                    Orchestrator
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
       Agent            Skill           Tool
          │               │               │
          └───────────────┴───────────────┘
                          │
                   RunContext
              ┌───────────┴───────────┐
              ▼                       ▼
        context.tools           context.connectors
     (registered @tool)    (YAML data connectors)
              │                       │
              ▼                       ▼
         MCP tools              Postgres / Snowflake
    (from mcp/servers.yaml)    Azure AI Search / Redis
```

| Mechanism | Config location | Runtime access | Best for |
|-----------|-----------------|----------------|----------|
| **Data connectors** | `harness/connectors/*/connector.yaml` | `context.connectors["name"]` | Postgres, Snowflake, Azure AI Search, Redis |
| **Native tools** | `harness/tools/*.py` | `context.tools["name"]` | Custom logic wrapping connectors or APIs |
| **MCP servers** | `harness/mcp/servers.yaml` | `context.tools["server_tool"]` | Jira, Confluence, external SaaS |

---

## 1. Data connectors (Postgres, Snowflake, Azure AI Search)

Each connector is a folder under `harness/connectors/`:

```
harness/connectors/
  sales_postgres/
    connector.yaml      # connection config
    schema.yaml         # optional table/field definitions for agents
  product_docs_index/
    connector.yaml
    schema.yaml
  analytics_snowflake/
    connector.yaml
```

### Azure Database for PostgreSQL

`harness/connectors/sales_postgres/connector.yaml`:

```yaml
name: sales_postgres
kind: postgres
host: ${env:AZURE_POSTGRES_HOST}
database: ${env:AZURE_POSTGRES_DB}
user: ${env:AZURE_POSTGRES_USER}
password: ${secret:azure-postgres-password}
extra:
  provider: azure_postgres
  port: 5432
  ssl_mode: require
```

Environment variables (Windows PowerShell):

```powershell
$env:AZURE_POSTGRES_HOST = "myserver.postgres.database.azure.com"
$env:AZURE_POSTGRES_DB = "sales"
$env:AZURE_POSTGRES_USER = "harness_reader"
$env:HARNESS_SECRET_AZURE_POSTGRES_PASSWORD = "..."
```

### Azure AI Search

`harness/connectors/product_docs_index/connector.yaml`:

```yaml
name: product_docs_index
kind: azure_ai_search
extra:
  provider: azure_ai_search
  endpoint: ${env:AZURE_SEARCH_ENDPOINT}
  index_name: product-docs
  api_key: ${secret:azure-search-api-key}
```

```powershell
$env:AZURE_SEARCH_ENDPOINT = "https://my-search.search.windows.net"
$env:HARNESS_SECRET_AZURE_SEARCH_API_KEY = "..."
pip install -r requirements-azure.txt
```

### Snowflake

`harness/connectors/analytics_snowflake/connector.yaml`:

```yaml
name: analytics_snowflake
kind: snowflake
database: ${env:SNOWFLAKE_DATABASE}
user: ${env:SNOWFLAKE_USER}
password: ${secret:snowflake-password}
extra:
  account: ${env:SNOWFLAKE_ACCOUNT}
  warehouse: ${env:SNOWFLAKE_WAREHOUSE}
  schema: PUBLIC
```

```powershell
pip install -r requirements-snowflake.txt
```

---

## 2. How tools and skills use connectors

At runtime, the orchestrator injects all registered connectors into `RunContext.connectors`.

### Built-in SQL tool

`sql_query` runs read queries against Postgres or Snowflake connectors:

```python
# Agent YAML
allowed_tools:
  - sql_query
```

The agent calls:

```json
{
  "connector": "sales_postgres",
  "sql": "SELECT stage, SUM(amount_usd) FROM opportunities GROUP BY stage",
  "limit": 100
}
```

`sql_query` requires HITL approval (`requires_approval: true`).

### Built-in Azure Search tool

`azure_index_search` queries an Azure AI Search connector:

```json
{
  "connector": "product_docs_index",
  "query": "retirement plan rollover rules",
  "top": 5,
  "filter": "product_line eq 'retirement'"
}
```

### Custom tool accessing a connector

```python
from harness.registry import register_tool

@register_tool
class MyPipelineTool:
    async def run(self, args, *, context):
        pg = context.connectors["sales_postgres"]
        result = await pg.query(QuerySpec(sql="SELECT COUNT(*) AS n FROM opportunities"))
        return MyOutput(count=result.rows[0]["n"])
```

### Custom skill

Skills call tools via `context.tools` or connectors directly:

```python
@register_skill
class DocsResearchSkill(BaseSkill):
    manifest = SkillManifest(
        name="docs_research",
        required_tools=["azure_index_search"],
        ...
    )

    async def execute(self, payload, *, context):
        tool = context.tools["azure_index_search"]
        hits = await tool.run(tool.spec.input_schema(query=payload.query), context=context)
        return MyOutput(hits=hits.hits)
```

---

## 3. Wiring connectors to agents

**Option A — Tool-mediated (recommended)**

Add tools that wrap connectors to the agent's `allowed_tools`:

```yaml
# harness/agents/product_research.yaml
name: product_research
description: Answers product questions using internal documentation.
allowed_tools:
  - azure_index_search
  - sql_query
context_packs:
  - sales_glossary
model_config_ref: primary_reasoner
```

**Option B — MCP tools**

Enable MCP servers in `harness/mcp/servers.yaml`. MCP tools appear in `context.tools` automatically:

```yaml
servers:
  jira:
    transport: stdio
    command: "npx"
    args: ["-y", "@yourorg/jira-mcp-server"]
    enabled: true
```

Reference MCP tool names in `allowed_tools` (often prefixed with server name).

---

## 4. Schema files (for agent context)

`schema.yaml` beside a connector documents tables or index fields. Bootstrap loads it into `connector.config.extra["schema"]`.

Agents don't auto-read schema yet — reference it in context packs or tool descriptions. Example `harness/connectors/sales_postgres/schema.yaml` ships with the repo.

---

## 5. Bootstrap and health checks

On startup, bootstrap:

1. Loads all `harness/connectors/*/connector.yaml`
2. Instantiates the correct connector class (Postgres, Snowflake, Azure AI Search, Redis)
3. Registers them in `DataSourceRegistry`
4. Optionally runs health checks (`connector_health_check: true` in `harness.settings.yaml`)

View registered connectors:

```powershell
Invoke-RestMethod http://localhost:8000/admin/capabilities
```

---

## 6. Secret resolution

| YAML syntax | Resolves to |
|-------------|-------------|
| `${secret:azure-postgres-password}` | `HARNESS_SECRET_AZURE_POSTGRES_PASSWORD` |
| `${env:AZURE_POSTGRES_HOST}` | `AZURE_POSTGRES_HOST` |

Set secrets in `.env` (loaded via `python-dotenv` at startup) or PowerShell environment variables.

---

## Quick reference

| I want to… | Do this |
|------------|---------|
| Query Azure Postgres | Add `sales_postgres` connector + use `sql_query` tool |
| Search Azure AI index | Add `product_docs_index` connector + use `azure_index_search` tool |
| Query Snowflake | Add `analytics_snowflake` connector + `pip install -r requirements-snowflake.txt` + `sql_query` |
| Use Jira/Confluence | Enable MCP server in `harness/mcp/servers.yaml` |
| Custom data access | Write a `@register_tool` that reads `context.connectors["name"]` |

See also: [SETUP.md](SETUP.md) for installation and API keys.
