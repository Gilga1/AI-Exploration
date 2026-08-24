# Phase 5 — Dynamic Sub-Agent Profiles

**Status:** Planned (optional)  
**Depends on:** Phase 1, Phase 4

---

## Goal

Runtime-configured agent instances from templates — **not** free-form agent codegen.

---

## Scope

| Feature | Description |
|---------|-------------|
| `harness/agent_profiles/*.yaml` | Base profiles with overridable fields |
| Profile instantiation | Planner assigns `profile:advisor_deep_dive` with runtime `config` overrides |
| Allowed overrides | `allowed_tools`, `system_prompt_fragment`, `config`, `max_steps` |
| Sandbox | Profiles cannot add tools/connectors not in base profile |
| No code generation | YAML composition only |

---

## Example profile

```yaml
name: advisor_deep_dive
base_agent: agentic_analyzer
overrides:
  max_steps: 60
  config:
    analysis_defaults:
      collection: Details_FTAUM
description: Extended AUM analysis using agentic_analyzer base.
```

---

## What this is NOT

- Generating Python at runtime
- Creating connectors or tools not in registry
- Unsandboxed arbitrary system prompts from end users

---

## Acceptance criteria

- [ ] Planner can assign profile-based agents
- [ ] Overrides validated against base agent manifest
- [ ] Telemetry attributes runs to base agent + profile name
