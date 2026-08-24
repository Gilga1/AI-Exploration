# Phase 5 — Dynamic Sub-Agent Profiles

**Status:** Implemented  
**Depends on:** Phase 1, Phase 4

---

## Goal

Runtime-configured agent instances from templates — **not** free-form agent codegen.

The harness already supports fixed agent manifests (`harness/agents/*.yaml`), workflow templates for multi-step plans (Phase 4), and registry-driven routing. Phase 5 closes the gap between those layers: **reusing a base agent with job-specific configuration** without duplicating entire YAML files or writing Python.

### Why this is needed

| Layer | Analogy | Limitation without profiles |
|-------|---------|----------------------------|
| Agent YAML | Class definition | One static config per agent name |
| Workflow template | Multi-step recipe | Tasks reference fixed agent names |
| Planner (LLM/heuristic) | Dispatcher | Cannot vary `max_steps`, `config`, or prompt per job |

Profiles are **configured instances** of existing agents:

```
agentic_analyzer (base class)
  ├── default manifest
  └── advisor_deep_dive (profile instance: +60 steps, AUM collection, extra prompt)
```

This enables domain teams to ship specialized variants (deep dive, quick scan, compliance-strict) as YAML only, while the core stays generic.

---

## Scope

| Feature | Description |
|---------|-------------|
| `harness/agent_profiles/*.yaml` | Profile definitions with validated overrides |
| Profile instantiation | Merged manifest registered as a routable agent |
| Allowed overrides | `max_steps`, `max_tokens_budget`, `timeout_s`, `system_prompt_fragment`, `allowed_tools` (subset only), `config` (deep merge) |
| Sandbox | Profiles cannot add tools outside the base agent's `allowed_tools` |
| Telemetry | Handoff events include `base_agent_name`; task spans include `harness.agent.profile` + `harness.agent.base` |
| Admin API | `GET /admin/agent_profiles` |
| No code generation | YAML composition only |

---

## Example profile

```yaml
# harness/agent_profiles/advisor_deep_dive.yaml
name: advisor_deep_dive
base_agent: agentic_analyzer
description: Extended AUM analysis using agentic_analyzer base.
capability_tags:
  - aum
  - deep-dive
overrides:
  max_steps: 60
  system_prompt_fragment: |
    Prioritize AUM collections and longer historical windows.
  config:
    analysis_defaults:
      collection: Details_FTAUM
```

Planner and workflow tasks reference the profile by name:

```yaml
assignee:
  kind: profile   # or kind: agent — profiles register as agents
  name: advisor_deep_dive
```

The synthesizer still runs automatically after all tasks.

---

## What this is NOT

| Profiles (Phase 5) | Codegen (out of scope) |
|--------------------|------------------------|
| YAML merge of existing agent manifest | Writing new Python at runtime |
| Overrides validated against base agent | Creating new tools/connectors |
| Same registry, different runtime config | Unsandboxed arbitrary code execution |

---

## Acceptance criteria

- [x] Profiles load at bootstrap after base agents
- [x] Overrides validated against base agent manifest (tools subset, positive max_steps)
- [x] Profile agents routable via capability index and executable in plans
- [x] Telemetry attributes runs to profile name + base agent name
- [x] `GET /admin/agent_profiles` lists loaded profiles
