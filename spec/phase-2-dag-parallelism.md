# Phase 2 — DAG + Parallelism

**Status:** Planned  
**Depends on:** Phase 1

---

## Goal

Execute independent plan tasks in parallel while respecting `depends_on` DAG edges.

---

## Scope

| Feature | Description |
|---------|-------------|
| Topological sort | Order tasks by DAG |
| Parallel batch | Run all tasks whose deps are satisfied concurrently |
| Per-task budgets | `max_steps`, `timeout_s` overrides per `PlannedTask` |
| Failure policies | `fail_fast` \| `continue` \| `retry_once` (configurable per plan) |
| Concurrency limit | `orchestration_max_parallel: 3` setting |

---

## Executor changes

```python
async def execute_plan_dag(plan, executor, max_parallel=3):
    ready = tasks_with_satisfied_deps()
    while ready or running:
        batch = ready[:max_parallel]
        results = await asyncio.gather(*[run_task(t) for t in batch], return_exceptions=True)
        ready = next_ready_tasks()
```

---

## Events

- `task_started` may overlap timestamps for parallel tasks
- `plan_progress` event: `{ completed: 2, total: 4, running: ["t2", "t3"] }`

---

## Tests

- Diamond DAG: A → B, A → C, B+C → D
- Parallel tasks don't share mutable state
- One parallel failure doesn't kill unrelated branch

---

## Acceptance criteria

- [ ] Independent tasks run concurrently
- [ ] Dependent tasks wait for all upstream success
- [ ] Failure policy honored per configuration
