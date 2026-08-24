# Multi-Agent Delegation — Implementation Specs

This folder contains phased implementation specifications for the harness **multi-agent delegation orchestrator**.

## Overview

Evolve the orchestrator from single-shot routing:

```
User → pick ONE skill/agent → done
```

To plan-driven delegation:

```
User → Planner → HITL plan approval → Execute tasks (agents/skills) → Synthesizer agent → done
```

## Principles

- **Generic core** — planner, executor, and synthesizer dispatch are domain-agnostic
- **Registry-driven** — tasks assign to pre-registered agents and skills only (no dynamic agent codegen in early phases)
- **Mandatory plan HITL** — multi-step plans require human approval before execution
- **Realtime visibility** — task status events streamed to the client
- **Partial success** — failed tasks return user-facing impact messages; synthesizer merges what succeeded

## Phases

| Phase | Spec | Status |
|-------|------|--------|
| 1 | [phase-1-multi-agent-delegation.md](./phase-1-multi-agent-delegation.md) | **Implemented** |
| 2 | [phase-2-dag-parallelism.md](./phase-2-dag-parallelism.md) | **Implemented** |
| 3 | [phase-3-observability.md](./phase-3-observability.md) | **Implemented** |
| 4 | [phase-4-workflow-templates.md](./phase-4-workflow-templates.md) | **Implemented** |
| 5 | [phase-5-dynamic-sub-agents.md](./phase-5-dynamic-sub-agents.md) | **Implemented** |

## Related code

```
src/harness/orchestrator/
  plan_models.py        # ExecutionPlan, PlannedTask, TaskResult
  complexity.py         # simple vs multi gate
  planner.py            # LLM + workflow + stub planner
  workflow_*.py         # Template loader, matcher, slot filling
  task_executor.py      # Agent/skill dispatch
  dag_executor.py       # Parallel batches, depends_on
  plan_store.py         # Plan snapshots (SQLite)
  waterfall.py          # Event hierarchy builder
  plan_runner.py        # Plan lifecycle + synthesizer
  orchestrator.py       # Extended graph + plan resume
harness/
  agents/synthesizer.yaml
  workflows/*.yaml      # Declarative plan templates
```
