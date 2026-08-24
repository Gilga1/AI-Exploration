# Agentic RAG Evaluation Harness

An evaluation harness for agentic RAG systems. The architecture keeps the request path (LangGraph/LangChain) separate from telemetry (OpenTelemetry) and offline evaluation (DeepEval).

This repository currently contains **Phase 0: Repo & Infra Scaffolding** only.

## Repository layout

- `backend/` — FastAPI service and Python project
- `frontend/` — Vite, React, TypeScript, and Tailwind dashboard shell
- `infra/` — local Postgres and OpenTelemetry Collector configuration

## Run the backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e .
.venv/Scripts/uvicorn app.main:app --reload
```

The health endpoint is available at `http://127.0.0.1:8000/health`.

## Run the frontend

```bash
cd frontend
npm install
npm run dev
```

## Run local infrastructure

```bash
docker compose -f infra/docker-compose.yml up
```

This starts Postgres 16 and an OpenTelemetry Collector. The collector accepts OTLP on ports `4317` (gRPC) and `4318` (HTTP) and writes received spans to its debug exporter; application wiring is intentionally deferred to a later phase.
