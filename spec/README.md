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
| 2 | [phase-2-dag-parallelism.md](./phase-2-dag-parallelism.md) | Planned |
| 3 | [phase-3-observability.md](./phase-3-observability.md) | Planned |
| 4 | [phase-4-workflow-templates.md](./phase-4-workflow-templates.md) | Planned |
| 5 | [phase-5-dynamic-sub-agents.md](./phase-5-dynamic-sub-agents.md) | Planned |

## Related code (Phase 1)

```
src/harness/orchestrator/
  plan_models.py      # ExecutionPlan, PlannedTask, TaskResult
  complexity.py       # simple vs multi gate
  planner.py          # LLM + stub planner
  task_executor.py    # sequential agent/skill dispatch
  orchestrator.py     # extended graph + plan resume
harness/agents/
  synthesizer.yaml    # dedicated merge agent
```
