# Agentic RAG Evaluation Harness

An **LLM-driven** evaluation harness for agentic RAG systems. The architecture keeps the request path (LangGraph/LangChain) separate from telemetry (OpenTelemetry) and evaluation (DeepEval). Every answer and judge score comes from a real LLM — there is no offline deterministic stub.

> 📐 For the full architecture — diagrams, data flow, core concepts, and design decisions — see [`architecture.markdown`](./architecture.markdown).
>
> 🔧 For operations (regressions, CI re-runs, sampling, auth) see [`RUNBOOK.md`](./RUNBOOK.md).

## Key characteristics

- **Fully LLM-driven**: generation and judging require an OpenRouter-compatible API key (`OPENROUTER_API_KEY`). A missing key is a configuration error, not a silent fallback to canned answers.
- **Trace-native**: every agent invocation produces an OpenTelemetry trace with per-invocation identity (safe under concurrent load); traces are scored asynchronously off the hot path and persisted to Postgres.
- **Async eval pipeline**: DeepEval judges run as background tasks after the HTTP response is sent; dashboard reads never block on LLM calls.
- **Production guards**: API-key auth on protected routes (`/eval/*`, `/agent/*`, `/metrics/*`, `/traces/*`), threshold alerting via webhook, head-based judge sampling for cost control.

## Repository layout

| Path | Purpose |
|---|---|
| `backend/` | FastAPI service: LangGraph agent loop, OTel trace capture, DeepEval scoring |
| `frontend/` | Vite + React + TypeScript + Tailwind dashboard |
| `infra/` | Local Postgres 16 and OpenTelemetry Collector (tail sampling) config |

## Prerequisites

- Python ≥ 3.11
- Node.js ≥ 18
- Docker (optional, for Postgres + OTel Collector)
- An **OpenRouter API key** (required — the harness is fully LLM-driven)
- **Postgres** (required — configure `APP_DATABASE_URL`)

## Setup

### 1. Configure environment

```bash
cp backend/.env.example backend/.env
cp infra/.env.example infra/.env
# then edit both files: OPENROUTER_API_KEY, APP_DATABASE_URL, APP_API_KEY, etc.
```

Also copy [`frontend/.env.example`](./frontend/.env.example) to `frontend/.env.local` when using auth (`VITE_API_KEY`).

### 2. Run local infrastructure (optional)

```bash
docker compose -f infra/docker-compose.yml up -d
```

Starts Postgres 16, the backend API, and an OpenTelemetry Collector (OTLP gRPC `4317` / HTTP `4318`). Spans are always persisted to Postgres even when OTLP export is enabled.

### 3. Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -e ".[openai,dev]"   # Linux/macOS: .venv/bin/pip ...
.venv/Scripts/uvicorn app.main:app --reload    # run from backend/ so .env is found
```

The app fails fast at startup if required env vars are missing (`APP_DATABASE_URL`, `OPENROUTER_API_KEY`, `APP_LLM_MODEL`, `APP_LLM_BASE_URL`). Health check: `http://127.0.0.1:8000/health`.

> ⚠️ On Windows/MSYS shells, native tools need forward-slash paths: `.venv/Scripts/python.exe` works, backslash paths may not.

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard at `http://localhost:5173`. Configure `VITE_API_BASE_URL` and `VITE_API_KEY` in `frontend/.env.local` when needed.

## Quick tour

```bash
# Ask the agent something (traces + async scoring happen automatically)
curl -X POST http://localhost:8000/api/v1/agent/invoke \
  -H "Content-Type: application/json" \
  -d '{"question": "What does Acme Orbit sell?"}'

# Read aggregated judge scores
curl http://localhost:8000/api/v1/metrics/rag
```

If you set `APP_API_KEY`, add `-H "X-API-Key: ..."` to every call except `/health`.

## Evaluation

```bash
cd backend
# Offline-style CLI run of the golden dataset (uses your real key; costs tokens)
.venv/Scripts/python -m app.evaluation.runners.ci_runner
```

CI (`.github/workflows/eval.yml`) runs unit tests on every PR and the golden DeepEval suite when the `OPENROUTER_API_KEY` repository secret is configured.

## Load test

```bash
cd backend
./.venv/Scripts/python.exe -m scripts.load_test --concurrency 8 --requests 40
```
