# Semantic Layer Shell

**Intelligence Hub pilot** — deterministic SQL assembly from a Neo4j-backed semantic registry.

## What it does

1. Developers author **YAML metadata** (data sources, measures, metrics) and publish to Neo4j.
2. Users ask **natural-language questions** in the Query Console.
3. An **LLM** decomposes the question and picks a metric from graph-defined candidates.
4. Python **assembles SQL** from stored fragments — the LLM never writes JOINs or aggregations.
5. **Snowflake** executes the assembled SQL and returns results.

## Documentation

- **[Setup guide](docs/setup.md)** — install, configure, run, troubleshoot
- **[Architecture](docs/architecture.md)** — design principles, graph schema, API, roadmap

## Quick start

```bash
cp .env.example .env          # edit with your credentials
bash scripts/setup.sh         # Neo4j + deps + graph bootstrap

cd backend && source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend && npm run dev    # http://localhost:5173
```

## Health checks

| Endpoint | Checks |
|---|---|
| `GET /health` | API liveness |
| `GET /health/graph` | Neo4j connectivity + last graph version |
| `GET /health/warehouse` | Snowflake credentials + connection |
| `GET /health/llm` | OpenAI API key configured |

## Tests

```bash
source backend/.venv/bin/activate
pytest tests/ -q
```

## Project layout

```
semantic-layer-shell/
├── .env.example
├── docker-compose.yml
├── scripts/setup.sh
├── backend/app/
│   ├── api/            # REST routes
│   ├── registry/       # YAML parser, validator, ingestor
│   ├── graph/          # Neo4j client, discovery, resolver
│   ├── llm/            # OpenAI decompose / reason / answer + embeddings
│   ├── agents/         # Query pipeline (streaming + LangGraph)
│   ├── sql_gen/        # Deterministic SQL assembler
│   ├── warehouse/      # Snowflake client
│   └── bootstrap.py    # Startup graph publish
├── frontend/src/
├── registry/           # Pilot YAML files
└── tests/
```
