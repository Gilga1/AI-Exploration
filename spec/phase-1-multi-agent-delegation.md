# Phase 1 — Multi-Agent Delegation (MVP)

**Status:** Implemented  
**Goal:** Plan → mandatory HITL approval → sequential task execution → synthesizer agent → partial-success handling + realtime events.

---

## Scope

### In scope

| Feature | Description |
|---------|-------------|
| LLM planner | Decompose user message into `ExecutionPlan` using registry catalog |
| Stub planner | Deterministic plans when `force_stub_models=true` (tests) |
| Complexity gate | `auto` / `single` / `multi` modes |
| Plan HITL | Always require approval before task execution |
| Sequential executor | Run tasks in dependency order (no parallel DAG yet) |
| Agent + skill steps | Reuse existing `spawn_agent` / `dispatch_skill` paths |
| Synthesizer agent | Always run `synthesizer` as final step (registry YAML) |
| Partial success | `continue_on_failure`; user-facing per-task messages |
| Realtime events | `plan_*` and `task_*` events in ledger |
| SSE stream | `GET /v1/runs/{trace_id}/events` |
| API extensions | `orchestration` on request; `plan` + `task_results` on response |

### Out of scope (later phases)

- Parallel DAG execution
- Workflow templates
- Dynamic sub-agent profiles
- Plan edit validation UI schema

---

## Models

### `PlannedTask`

```python
task_id: str
title: str                          # user-visible label
objective: str                        # natural language for agents
assignee_kind: Literal["agent", "skill"]
assignee_name: str
depends_on: list[str]
inputs_from: dict[str, str]         # skill_input field → "task_id.output_key"
skill_input_template: dict | None
status: pending | running | success | failure | skipped | blocked
fallback_hint: str | None           # used in failure user_message
error: str | None
user_message: str | None
```

### `ExecutionPlan`

```python
plan_id: str
tasks: list[PlannedTask]
rationale: str
status: draft | awaiting_approval | approved | executing | completed | partial | failed
```

### `TaskResult`

```python
task_id: str
status: success | failure | skipped
output: dict | None
error: str | None
user_message: str | None
artifacts: list[dict]
```

---

## Orchestrator graph

```
START
  → classify_complexity
  → [single] route → dispatch_skill | spawn_agent → synthesize → END
  → [multi]
      → plan
      → save_plan_approval (interrupt → awaiting_plan_approval)
      → (on resume) execute_tasks (sequential)
      → spawn_synthesizer
      → END
```

**Fast path:** When `orchestration_fast_path_single_task=true` and planner returns exactly one task with high confidence, skip plan HITL and execute directly (dev convenience; production can set `false`).

---

## HITL — plan approval

Stored in `ApprovalStore` with `payload.kind = "plan_approval"`:

```json
{
  "kind": "plan_approval",
  "message": "original user message",
  "plan": { ...ExecutionPlan... },
  "thread_id": "..."
}
```

Resume decisions:

| Decision | Behavior |
|----------|----------|
| `approve` | Execute plan as-is |
| `edit` | Replace plan from `decisions[].plan` then execute |
| `reject` | Cancel; status `failure` |

---

## Task executor

For each task in topological order:

1. Skip if dependency failed → `status: blocked`
2. Emit `task_started` event with `display_message`
3. Build context from `task_results` of dependencies
4. Dispatch:
   - **agent** → `HandoffPacket(objective, context_summary=prior outputs JSON)`
   - **skill** → map `inputs_from` / `skill_input_template` to `skill_input`
5. On success → store `TaskResult`, emit `task_completed`
6. On failure → store failure, set `user_message`, emit `task_failed`, continue if `continue_on_failure`

### Failure message template

```
Could not complete "{title}". {error}
What this means: You might still want to check {fallback_hint} separately.
```

---

## Synthesizer agent

File: `harness/agents/synthesizer.yaml`

- Always invoked after task loop (not planner-selected)
- Input: all `task_results` + plan metadata + failure messages
- Stub config for tests (no LLM)
- Output: `{ "response": "...", "completed_tasks": [...], "failed_tasks": [...] }`

---

## Events

| `event_type` | `action` / fields |
|--------------|-------------------|
| `plan` | `created`, `approved`, `completed` + plan snapshot |
| `task` | `started`, `completed`, `failed` + `display_message` |

---

## API

### Request

```json
POST /v1/handle
{
  "message": "...",
  "orchestration": { "mode": "auto" }
}
```

### Response — awaiting approval

```json
{
  "status": "awaiting_plan_approval",
  "task_id": "<plan_id>",
  "plan": { ... },
  "message": "Review the plan and approve via POST /v1/resume"
}
```

### Resume

```json
POST /v1/resume
{
  "task_id": "<plan_id>",
  "thread_id": "<trace_id>",
  "decisions": [{ "type": "approve" }]
}
```

### Response — partial success

```json
{
  "status": "partial_success",
  "plan": { "status": "partial" },
  "task_results": { ... },
  "output": { "response": "..." }
}
```

### SSE

```
GET /v1/runs/{trace_id}/events
```

Polls ledger every 500ms; emits `data: {json}\n\n` for new events.

---

## Settings (`harness.settings.yaml`)

```yaml
orchestration_mode: auto
orchestration_require_plan_approval: true
orchestration_max_tasks: 5
orchestration_synthesizer_agent: synthesizer
orchestration_continue_on_failure: true
orchestration_fast_path_single_task: true
```

---

## Files to create / modify

| File | Action |
|------|--------|
| `src/harness/orchestrator/plan_models.py` | Create |
| `src/harness/orchestrator/complexity.py` | Create |
| `src/harness/orchestrator/planner.py` | Create |
| `src/harness/orchestrator/task_executor.py` | Create |
| `src/harness/orchestrator/orchestrator.py` | Extend |
| `src/harness/core/request.py` | Extend |
| `src/harness/settings.py` | Extend |
| `src/harness/telemetry/events.py` | Add PlanEvent, TaskEvent |
| `src/harness/hitl/store.py` | Plan approval payload support |
| `src/harness/api/app.py` | SSE endpoint |
| `harness/agents/synthesizer.yaml` | Create |
| `tests/test_plan_orchestration.py` | Create |

---

## Test scenarios

1. Multi-agent message → plan created → `awaiting_plan_approval`
2. Approve plan → both tasks succeed → synthesizer merges → `success`
3. Approve plan → task 2 fails → `partial_success` + caveat in output
4. Reject plan → no tasks run
5. SSE / events show `task_started` → `task_completed` sequence
6. Single-task fast path still works (existing tests unchanged)
7. Plan with skill step (`markdown_to_pdf`) after agent step

---

## Acceptance criteria

- [ ] Planner produces valid plan from registry catalog
- [ ] Plan HITL blocks execution until `/v1/resume` approve
- [ ] Tasks execute sequentially with realtime events
- [ ] Synthesizer always runs last
- [ ] Partial failures return actionable user messages
- [ ] Existing single-agent routes remain backward compatible
- [ ] All tests pass
