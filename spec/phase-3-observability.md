# Phase 3 — Observability & Operations

**Status:** Planned  
**Depends on:** Phase 1 (partially delivered in Phase 1)

---

## Goal

Production-grade visibility into plan runs for PMs, operators, and the UI waterfall.

---

## Scope

| Feature | Description |
|---------|-------------|
| `/admin/plans` | List active and recent plans with status |
| `/admin/plans/{plan_id}` | Full plan + task results snapshot |
| Dashboard waterfall | Plan → Task → Tool → LLM hierarchy in events |
| Langfuse integration | Plan and task spans as OTel children of root trace |
| Metrics | Plan duration, task success rate, approval latency |
| Alerting hooks | Webhook on `plan_failed` or `partial_success` |

---

## Event enrichment

```json
{
  "event_type": "task",
  "action": "failed",
  "display_message": "Could not retrieve sales figures for John Smith",
  "plan_id": "...",
  "task_id": "t2",
  "assignee": { "kind": "agent", "name": "agentic_analyzer" },
  "duration_ms": 4200
}
```

---

## Acceptance criteria

- [ ] Admin can introspect any plan by trace_id or plan_id
- [ ] Langfuse shows plan/task hierarchy
- [ ] Waterfall UI can render without custom parsing
