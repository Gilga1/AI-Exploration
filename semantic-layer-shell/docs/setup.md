# Setup Guide

Step-by-step instructions for running Semantic Layer Shell locally.

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Docker | 20+ | Runs Neo4j via `docker compose` |
| Python | 3.11+ | Backend API |
| Node.js | 18+ | Frontend dev server |
| OpenAI API key | — | LLM decompose / reason / answer + embeddings |
| Snowflake account | — | SQL execution (optional for SQL-preview-only dev) |

## 1. Clone and enter the project

```bash
git clone <repo-url>
cd semantic-layer-shell
```

## 2. Configure environment

Copy the example env file and fill in your credentials:

```bash
cp .env.example .env
```

### Environment variables

#### Neo4j (Docker)

| Variable | Default | Description |
|---|---|---|
| `NEO4J_URI` | `bolt://localhost:7687` | Bolt connection string |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | `password` | Neo4j password (must match `docker-compose.yml`) |
| `AUTO_PUBLISH_REGISTRY` | `true` | Publish `registry/` YAML on backend startup if graph is empty |

#### OpenAI (LLM + embeddings)

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | **Required** for LLM stages and vector embeddings |
| `OPENAI_MODEL` | `gpt-4o-mini` | Chat model for decompose / reason / answer |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model for registry publish |
| `OPENAI_BASE_URL` | — | Optional — Azure OpenAI or local proxy |

#### Snowflake (warehouse execution)

| Variable | Required | Description |
|---|---|---|
| `SNOWFLAKE_ACCOUNT` | Yes | Account identifier (e.g. `xy12345.us-east-1`) |
| `SNOWFLAKE_USER` | Yes | Username |
| `SNOWFLAKE_PASSWORD` | Yes | Password |
| `SNOWFLAKE_WAREHOUSE` | Yes | Warehouse name |
| `SNOWFLAKE_DATABASE` | Yes | Database name |
| `SNOWFLAKE_SCHEMA` | Yes | Schema name |
| `SNOWFLAKE_ROLE` | No | Optional role override |

> Without Snowflake env vars the pipeline still runs through SQL assembly and preview, but the execute stage returns empty rows with a warning.

## 3. One-shot setup

```bash
bash scripts/setup.sh
```

This script:

1. Creates `.env` from `.env.example` (if missing)
2. Starts Neo4j: `docker compose up -d neo4j`
3. Waits for Neo4j health check
4. Creates a Python venv and installs backend dependencies
5. Bootstraps the bundled `registry/` YAML into Neo4j
6. Installs frontend npm dependencies

### Manual Neo4j start

```bash
docker compose up -d neo4j
```

Neo4j Browser: http://localhost:7474 (login `neo4j` / `password`)

### Manual graph bootstrap

```bash
cd backend
source .venv/bin/activate
python -m scripts.bootstrap_graph           # skip if graph already has data
python -m scripts.bootstrap_graph --force   # re-publish registry
```

## 4. Run the backend

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### Verify services

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/graph
curl http://localhost:8000/health/warehouse
curl http://localhost:8000/health/llm
```

Expected when fully configured:

```json
{"status": "ok", "neo4j_connected": true, "last_graph_version_id": "v-..."}
{"status": "ok", "snowflake_configured": true, "snowflake_connected": true}
{"status": "ok", "llm_enabled": true, "model": "gpt-4o-mini"}
```

### Test SQL preview (no Snowflake needed)

```bash
curl -X POST http://localhost:8000/api/v1/sql/preview \
  -H 'Content-Type: application/json' \
  -H 'X-User-Role: developer' \
  -d '{"metric_id": "net_flow_ratio"}'
```

## 5. Run the frontend

```bash
cd frontend
npm install   # if not done by setup.sh
npm run dev
```

Open http://localhost:5173

The Vite dev server proxies `/api` and `/health` to `localhost:8000`.

## 6. Run tests

```bash
cd semantic-layer-shell
source backend/.venv/bin/activate
pytest tests/ -q
```

## Daily development workflow

```bash
# Terminal 1 — infrastructure
cd semantic-layer-shell
docker compose up -d neo4j

# Terminal 2 — backend
cd semantic-layer-shell/backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 3 — frontend
cd semantic-layer-shell/frontend
npm run dev
```

### Editing registry YAML

1. Edit files in `registry/`
2. Re-publish: `python -m scripts.bootstrap_graph --force` (from `backend/` with venv active)
3. Or use the **Registry** tab in the UI to upload, validate, and publish

### RBAC headers (pilot)

The API reads role from the `X-User-Role` header:

| Value | Access |
|---|---|
| `viewer` | Query + graph read |
| `developer` | + registry, SQL preview |
| `admin` | + role management, registry rollback |

## Troubleshooting

### Neo4j not connecting

```bash
docker compose ps
docker compose logs neo4j
```

- Confirm `NEO4J_URI=bolt://localhost:7687` in `.env`
- Confirm `NEO4J_PASSWORD` matches `NEO4J_AUTH` in `docker-compose.yml`
- Wait for health check: `docker compose ps` should show `(healthy)`

### Graph bootstrap failed

```bash
cd backend && source .venv/bin/activate
python -m scripts.bootstrap_graph --force
```

Check validation errors in the output. Common issue: YAML `on` field for joins must be quoted (`"on": "fund_id = fund_id"`) because bare `on` parses as boolean in YAML.

### Snowflake connection failed

- Verify all `SNOWFLAKE_*` env vars are set in `.env`
- Check `/health/warehouse` for the error message
- Confirm warehouse is running and user has access to the target database/schema

### LLM not active

- Set `OPENAI_API_KEY` in `.env` and restart the backend
- Check `GET /health/llm` — when unconfigured, the pipeline falls back to heuristic decompose/reason

### Frontend cannot reach API

- Ensure backend is running on port 8000
- Check Vite proxy in `frontend/vite.config.ts`
- Or set `API_BASE` in `frontend/src/services/api.ts` if deploying separately

## Stopping services

```bash
docker compose down        # stop Neo4j (data persists in volume)
docker compose down -v     # stop Neo4j and delete data volume
```
