# Architecture — Agentic RAG Evaluation Harness

This document describes the system end to end: core concepts, component diagram, runtime data flow, the evaluation pipeline, and the design decisions (with their trade-offs) behind each choice.

---

## 1. Core concepts

| Concept | Meaning in this harness |
|---|---|
| **Trace** | One root invocation (agent loop or RAG chain), identified by its OpenTelemetry trace id. Stored in the `traces` table with aggregated attributes. |
| **Span** | A completed OTel span belonging to a trace (`chain`, `llm`, `retriever`, `tool` kinds). Spans carry GenAI semantic-convention attributes: inputs, outputs, model, token usage, retrieved document ids. |
| **Golden dataset** | 15 curated question/answer/expected-context examples over a fixed fictional corpus ("Acme Orbit"), plus 4 agent-loop scenarios with expected tool sequences and iteration budgets. |
| **Judge** | A DeepEval LLM metric (Faithfulness, ContextualPrecision, ContextualRecall, Hallucination) run against a reconstructed test case. Requires `OPENAI_API_KEY`. |
| **EvalResult** | One persisted score row keyed to `(trace_id, metric_name)` — the unit dashboards aggregate. |
| **Sampling** | Head-based, deterministic per trace id (`should_sample`): bounds judge cost in prod while keeping dev at rate 1.0. The OTel Collector separately applies tail sampling to exported traces (always keeps ERROR / >2s traces). |

**The central invariant:** evaluation never runs on the request/response hot path. Tracing is synchronous and cheap; judging is asynchronous and expensive.

---

## 2. Component diagram

```
┌────────────────────────────────────────────────────────────────────────────┐
│                                CLIENTS                                     │
│            React dashboard (Vite)          curl / CI / load_test.py        │
└──────────────┬─────────────────────────────────────┬───────────────────────┘
               │ http://localhost:5173                │ :8000/api/v1/*
               ▼                                      ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                         FASTAPI BACKEND (app.main)                         │
│                                                                            │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  ┌──────────────────────┐   │
│  │ /agent   │  │ /eval    │  │ /metrics/*    │  │ /traces/*            │   │
│  │ invoke   │  │ run      │  │ rag | agent   │  │ read-only            │   │
│  └────┬─────┘  └────┬─────┘  └───────┬───────┘  └──────────┬───────────┘   │
│       │             │                │                     │               │
│       │  require_api_key guards all four routers     │              │
│       ▼             ▼                ▼                     ▼               │
│  ┌────────────────────────────┐   ┌──────────────────────────────────┐    │
│  │ LangGraph agent loop       │   │ Read paths (pure DB queries +     │    │
│  │ planner→decide→retrieve/   │   │ threshold alerting; NO LLM calls) │    │
│  │ tool→generate              │   └──────────────────────────────────┘    │
│  └────┬───────────────────────┘                                            │
│       │ emits callbacks                                                    │
│       ▼                                                                    │
│  ┌────────────────────────────────────────────┐                            │
│  │ LangChainOTelCallbackHandler               │                            │
│  │ (the only LangChain↔OTel coupling)         │                            │
│  └────┬───────────────────────────┬───────────┘                            │
│       │ real-time export          │ local persistence fallback             │
│       ▼                           ▼                                        │
│  ┌─────────────────┐   ┌──────────────────────────┐                         │
│  │ OTLP exporter   │   │ persist_completed_span() │                         │
│  │ (BatchSpan      │   │ → SQLAlchemy upsert      │                         │
│  │  Processor)     │   │ (traces/spans tables)    │                         │
│  └───────┬─────────┘   └────────────┬─────────────┘                         │
│          │                          │                                       │
│          │            ┌─────────────▼───────────────┐                       │
│          │            │ BackgroundTasks (async eval)│                       │
│          │            │ score_trace(trace_id):      │                       │
│          │            │  reconstruct → DeepEval →   │                       │
│          │            │  persist EvalResults        │                       │
│          │            └─────────────┬───────────────┘                       │
└──────────┼──────────────────────────┼────────────────────────────────────────┘
           ▼                          ▼
┌───────────────────────┐   ┌───────────────────────────────────────────────┐
│ OTel Collector        │   │ Storage: SQLite (dev, WAL) or Postgres        │
│ tail sampling:        │   │   traces │ spans │ eval_results               │
│ keep ERROR/>2s,       │   └───────────────────────────────────────────────┘
│ sample healthy @15%   │
└───────────────────────┘
```

### Frontend pages

- `/` Dashboard — RAG metric summary cards + agent efficiency chart (efficient vs thrashing classification)
- `/traces` + `/traces/:id` — trace list and span timeline with GenAI attributes
- `/evaluations` — golden-dataset scorecard from `POST /eval/run`

---

## 3. Runtime data flow

### 3.1 Agent invocation (`POST /api/v1/agent/invoke`)

```
request {question}
   │
   ├─► get_agent_app()            # compiled graph, once per process
   │
   ├─► graph.invoke(initial_state)
   │      │
   │      │  PLANNER (deterministic routing guardrail)
   │      │   ├─ first visit: opens root chain span "agent.loop"
   │      │   │  captures per-invocation (root_run_id, trace_id) INTO STATE
   │      │   └─ decides: retrieve | tool | generate | done
   │      │
   │      │  RETRIEVER node ──► hash/SentenceTransformer embeddings ─► in-memory store
   │      │  TOOL_EXECUTOR  ──► calculator (AST-walk sandboxed)
   │      │                     document_lookup (corpus grep)
   │      │  GENERATOR node ──► ChatOpenAI(prompt = question + context)
   │      │                      answer returned; root span closed
   │      ▼
   │  final_state.trace_id        # THIS invocation's trace, no global queries
   │
   ├─► should_sample(trace_id, APP_EVAL_SAMPLING_RATE)?
   │      └─ yes ► BackgroundTasks.add(score_trace)   # AFTER response is sent
   │
   └─► response {answer, iterations, tool_calls, source_ids, trace_id}
```

Key correctness property: **trace identity lives in graph state**, not on shared node objects. Two concurrent invocations open independent root spans; the response's `trace_id` can never be another request's trace.

### 3.2 Telemetry capture (dual mode)

The callback bridge mirrors every chain/retriever/LLM/tool callback into an OTel span:

1. **Collector configured** (`APP_OTEL_EXPORTER_OTLP_ENDPOINT` set) → spans stream via gRPC BatchSpanProcessor to the Collector → tail sampling → debug exporter (or ClickHouse when enabled).
2. **No collector** → the bridge persists each *completed* span directly to SQL via `persist_completed_span()` — an upsert that creates the trace row lazily and finalizes it when the root span closes.

Both modes produce the same database shape, so the eval worker and dashboards are agnostic to which path ran.

### 3.3 Async scoring (`score_trace(trace_id)`)

Runs as a FastAPI BackgroundTask after the HTTP response:

```
spans (ordered) ─► reconstruct_test_case() ─► ReconstructedCase {
                   input, actual_output, retrieval_context,
                   document_ids, tools_called, iterations, is_agent_trace }
                        │
                        ├── RAG traces ──► 4 DeepEval judges (Faithfulness,
                        │                  ContextualPrecision/Recall, Hallucination)
                        ├── Agent traces ► ToolCorrectness (set comparison),
                        │                 TaskCompletion (GEval or heuristic),
                        │                 LoopEfficiency (GEval vs iteration budget)
                        └── missing key/context ► status="skipped" rows
                        ▼
                EvalResult rows persisted (never raises into the caller)
```

Agent expectations (expected tools, max iterations) are matched from the question text via `AGENT_EXPECTATIONS`.

### 3.4 Metrics & alerting

`GET /metrics/rag` and `GET /metrics/agent` are **read-only**: they aggregate `eval_results` and classify pass/fail against thresholds. Threshold breaches return an `alerts[]` array and fire a Slack-compatible webhook (5s timeout, 30-min cooldown per metric). Alerting failures never break the endpoint.

---

## 4. Why it's built this way (design decisions)

| Decision | Rationale | Trade-off accepted |
|---|---|---|
| **Fail fast without `OPENAI_API_KEY`** | The harness exists to measure LLM behaviour; a silent deterministic stub would make every score meaningless while looking green. | No zero-cost demo mode; local runs need a key. |
| **Deterministic planner, LLM generator** | Routing (retrieve/tool/generate/done) must be reproducible so iteration budgets and ToolCorrectness are stable signals; only the answer itself needs model intelligence. | Planner doesn't handle arbitrary multi-step plans — it's a fixed policy. |
| **Trace identity in state, not globals** | The graph compiles once per process; any per-request state on the node object corrupts concurrent traces (verified: cross-attribution under load). | Slightly larger state dict. |
| **Async eval off the hot path** | Judges cost seconds and cents; the RUNBOOK's load test proves p50/p95 don't move between sampling rates 0 and 1. Judge calls were deliberately removed from GET /metrics for the same reason. | Scores appear shortly after the response, not during it. |
| **Dual telemetry mode (OTLP or SQL)** | Dev works air-gapped; prod scales through the Collector without changing application code — the bridge is the only coupling point. | Two persistence paths to maintain. |
| **Hash embeddings by default** | Deterministic across processes, download-free, CI-safe; adequate for a 9-document corpus. Lexical rerank (75%) dominates vector score (25%). | Not semantically robust — swap via `APP_RAG_EMBEDDING_MODEL` for real corpora. |
| **AST-walk calculator, not `eval()`** | Only numeric literals + arithmetic operators parse; names/calls/attributes are structurally impossible. | Supports a small expression grammar only. |
| **API key on all paid surfaces** | `/eval/run` fans out to ~15 generations plus judges; unauthenticated access is a cost-abuse hole, not just a data leak. | Slightly more friction locally once `APP_API_KEY` is set. |
| **SQLite WAL + busy_timeout + one-shot init** | FastAPI sync endpoints run in a threadpool; without WAL/timeouts, concurrent span writes hit "database is locked" and spans were silently dropped (13/16 lost at concurrency 8 before the fix). | Postgres still recommended for multi-process deploys. |

## 5. Data model

```
traces (id=otel_trace_id PK) ──┬──< spans (id=span_id PK, parent_span_id, kind, attributes JSON)
                               └──< eval_results (metric_name, score, status, reasoning)
```

- `traces.attributes` mirrors the root span (question, answer, tool call list, iteration count).
- `eval_results.status`: `passed | failed | partial | skipped`.
- Aggregations never mutate rows; alerting reads the same tables.

## 6. Extending the harness

- **New metric**: implement in `app/evaluation/metrics/`, add to `realtime_worker._run_rag_judges` or `run_agent_metrics`, add its name to `metrics_routes` summaries and `alerting.DEFAULT_THRESHOLDS`.
- **Real embeddings**: `pip install -e ".[local-embeddings]"` and set `APP_RAG_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2`.
- **Bigger corpus**: replace `app/rag/corpus.CORPUS`; the vector store rebuilds per process.
- **Queue-backed scoring in prod**: `score_trace(trace_id)` has exactly one argument — wrap it in Celery/RQ/consumer without touching anything else.
