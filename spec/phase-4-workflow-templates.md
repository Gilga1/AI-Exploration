# Phase 4 — Workflow Templates

**Status:** Implemented  
**Depends on:** Phase 1

---

## Goal

Predefined multi-agent workflows for repeatable jobs — faster, cheaper, and more predictable than LLM planning every time.

---

## Scope

| Feature | Description |
|---------|-------------|
| `harness/workflows/*.yaml` | Declarative plan templates |
| Template planner mode | `orchestration_planner: template` |
| Slot filling | User message fills template variables (`{{advisor_name}}`, `{{competitor}}`) |
| Template + LLM hybrid | Template structure, LLM fills objectives |
| Override rules | Specific workflows bypass LLM planner when intent matches |

---

## Example template

```yaml
# harness/workflows/competitive_sales_brief.yaml
name: competitive_sales_brief
description: Research a competitor and analyze advisor sales, then synthesize.
match_tags: [competitor, sales, advisor]
variables:
  - competitor
  - advisor_name
tasks:
  - task_id: t1
    title: "Research {{competitor}}"
    assignee: { kind: agent, name: competitor_research }
    objective: "Research competitor {{competitor}}"
  - task_id: t2
    title: "Analyze {{advisor_name}} sales"
    assignee: { kind: agent, name: agentic_analyzer }
    objective: "Analyze advisor {{advisor_name}} product sales"
    depends_on: []
```

Note: `synthesizer` is still appended automatically by the orchestrator.

---

## Acceptance criteria

- [x] Templates load at bootstrap
- [x] Matcher selects template when tags align
- [x] Variables extracted from user message (regex or LLM)
- [x] Plan HITL still required before execution
