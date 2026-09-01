# Operations Runbook — Agentic RAG Evaluation Harness

## Reading a regression

1. Open the Dashboard (`/`) — RAG and agent panels show averages per metric.
2. If a metric drops below threshold, `GET /api/v1/metrics/rag` returns an
   `alerts[]` array naming the breached metric; a webhook fires to Slack if
   `APP_ALERT_WEBHOOK_URL` is set (30-min cooldown per metric).
3. Find offending traces on `/traces`, open one, inspect span attributes
   (retrieved doc ids, tool calls, token counts) in the timeline.
4. Per-trace judge scores: `GET /api/v1/metrics/rag?per_trace=true`.

## Re-running CI evaluation

- Locally: `python -m app.evaluation.runners.ci_runner` (offline mode skips
  LLM-judge metrics; scores come back as `"skipped"`).
- Against the API: `POST /api/v1/eval/run`.
- In CI: `.github/workflows/eval.yml` runs unit tests on every PR and `deepeval test run` when an `OPENROUTER_API_KEY` secret is configured.

## Sampling & cost control

| Knob | Where | Effect |
|---|---|---|
| `APP_EVAL_SAMPLING_RATE` | backend | Head-based rate for trace *scoring* (1.0 dev, 0.1–0.2 prod). Deterministic per trace id. |
| Collector `tail_sampling` | `infra/otel-collector-config.yaml` | Always keeps ERROR traces and >2s slow traces; samples healthy traffic at 15%. |

## Storage scaling (P6-T4)

Dev and production both use Postgres via `APP_DATABASE_URL`. The collector config ships a commented ClickHouse exporter for high-volume deployments; enable it plus a retention job before switching.

## Auth (P6-T3)

Set `APP_API_KEY` to require `X-API-Key` on `/metrics/*`, `/eval/*`, `/agent/*`, and `/traces/*`. In non-development environments the API refuses to start without `APP_API_KEY` unless `APP_AUTH_DISABLED=true` is explicitly set. Mirror the same key in `frontend/.env.local` as `VITE_API_KEY`.

## Load test (P6-T5)

```bash
cd backend
python -m scripts.load_test --base-url http://localhost:8000 --api-key "$APP_API_KEY" --concurrency 8 --requests 40
```

Compare p50/p95 with `APP_EVAL_SAMPLING_RATE=0` vs `=1` — the gap should be ~0,
proving eval cost stays off the hot path.

## Common issues

| Symptom | Cause | Fix |
|---|---|---|
| Metrics show `no-data` | No traces scored yet | Run `POST /api/v1/eval/run` or invoke `/agent/invoke`. |
| All judges `skipped` | No `OPENROUTER_API_KEY` | Expected offline; agent metrics still score deterministically. |
| Traces page empty after agent call | Postgres unreachable or persistence errors | Check `APP_DATABASE_URL`, backend logs, and Postgres health. |
| 401 on dashboard/API | `APP_API_KEY` set | Send `X-API-Key` header and set matching `VITE_API_KEY` in the frontend. |
