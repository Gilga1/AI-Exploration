# Semantic Layer Shell

**Intelligence Hub pilot** — deterministic SQL assembly from a Neo4j-backed semantic registry with grounded entity resolution, structured insights, and YAML-driven validation.

## What it does

1. Developers author **YAML metadata** (data sources, measures, metrics, entities, validation policies) and publish to Neo4j.
2. Users ask **natural-language questions** in the Query Console.
3. The pipeline **decomposes** mentions (entities, time ranges) and **discovers** metrics from the graph.
4. **Entity resolution** runs deterministic lookup SQL (name → ID); **time predicates** and **global filters** are injected into assembled SQL.
5. Post-SQL agents produce **structured insights**, **charts**, and **validation confidence** labels (high / medium / low).
6. **Snowflake** executes the assembled SQL (up to 1,000 rows).

## Documentation

- **[Setup guide](docs/setup.md)** — install, configure, run, troubleshoot
- **[Architecture](docs/architecture.md)** — design principles, graph schema, API, roadmap
- **[Grounded query spec](docs/implementation-spec-grounded-query.md)** — entity resolution, validation policies, pipeline stages

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
│   ├── agents/         # Query pipeline, entity/time resolution, insights, validator
│   ├── sql_gen/        # SQL assembler, lookup assembler, filter assembler
│   ├── warehouse/      # Snowflake client
│   └── bootstrap.py    # Startup graph publish
├── frontend/src/
├── registry/           # Pilot YAML (data sources, measures, metrics, entities, validation policies)
└── tests/
```
