# Agentic RAG Evaluation Harness

An **LLM-driven** evaluation harness for agentic RAG systems. The architecture keeps the request path (LangGraph/LangChain) separate from telemetry (OpenTelemetry) and evaluation (DeepEval). Every answer and judge score comes from a real LLM — there is no offline deterministic stub.

> 📐 For the full architecture — diagrams, data flow, core concepts, and design decisions — see [`architecture.markdown`](./architecture.markdown).
>
> 🔧 For operations (regressions, CI re-runs, sampling, auth) see [`RUNBOOK.md`](./RUNBOOK.md).

## Key characteristics

- **Fully LLM-driven**: generation and judging require `OPENAI_API_KEY`. A missing key is a startup error, not a silent fallback to canned answers.
- **Trace-native**: every agent invocation produces an OpenTelemetry trace with per-invocation identity (safe under concurrent load); traces are scored asynchronously off the hot path.
- **Async eval pipeline**: DeepEval judges run as background tasks after the HTTP response is sent; dashboard reads never block on LLM calls.
- **Production guards**: API-key auth on all mutating/LLM endpoints (`/eval/run`, `/agent/invoke`, `/metrics/*`), threshold alerting via Slack webhook, head-based judge sampling for cost control.

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
- An **OpenAI API key** (required — the harness is fully LLM-driven)

## Setup

### 1. Configure environment

```bash
cp backend/.env.example backend/.env
# then edit backend/.env and set APP_OPENAI_API_KEY=sk-...
```

All keys are documented in [`backend/.env.example`](./backend/.env.example).

### 2. Run local infrastructure (optional)

```bash
docker compose -f infra/docker-compose.yml up -d
```

Starts Postgres 16 and an OpenTelemetry Collector (OTLP gRPC `4317` / HTTP `4318`) with tail sampling that always keeps error and >2s traces. Without this, the backend persists spans locally to SQLite and still works fully.

### 3. Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -e ".[openai,dev]"   # Linux/macOS: .venv/bin/pip ...
.venv/Scripts/uvicorn app.main:app --reload    # run from backend/ so .env is found
```

The app fails fast at first use if `APP_OPENAI_API_KEY` is missing. Health check: `http://127.0.0.1:8000/health`.

> ⚠️ On Windows/MSYS shells, native tools need forward-slash paths: `.venv/Scripts/python.exe` works, backslash paths may not.

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard at `http://localhost:5173`. Set `VITE_API_BASE_URL` in `frontend/.env.local` if the backend runs elsewhere.

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

CI (`.github/workflows/eval.yml`) runs the same suite on PRs touching `backend/**` when the `OPENAI_API_KEY` repository secret is configured; without it the suite skips safely.

## Load test

```bash
cd backend
./.venv/Scripts/python.exe -m scripts.load_test --concurrency 8 --requests 40
```
