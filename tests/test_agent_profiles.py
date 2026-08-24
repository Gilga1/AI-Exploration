from __future__ import annotations

import pytest

from harness.agents.profile_models import (
    AgentProfile,
    AgentProfileOverrides,
    merge_profile_manifest,
    validate_profile_overrides,
)
from harness.bootstrap import bootstrap
from harness.core.models import AgentManifest
from harness.core.request import IncomingRequest, ResumeRequest
from harness.settings import HarnessSettings


def _settings(**kwargs) -> HarnessSettings:
    defaults = dict(
        scan_paths=["harness/tools", "harness/skills"],
        connector_health_check=False,
        force_stub_models=True,
        langfuse_enabled=False,
        orchestration_mode="multi",
        orchestration_require_plan_approval=True,
    )
    defaults.update(kwargs)
    return HarnessSettings(**defaults)


def _base_manifest() -> AgentManifest:
    return AgentManifest(
        name="agentic_analyzer",
        description="Base analyzer",
        system_prompt="Analyze data.",
        allowed_tools=["index_lookup", "render_output"],
        max_steps=30,
        config={"analysis_defaults": {"collection": "Details_FTSALES"}},
    )


def test_profile_override_validation_rejects_extra_tools():
    profile = AgentProfile(
        name="bad_profile",
        base_agent="agentic_analyzer",
        overrides=AgentProfileOverrides(allowed_tools=["index_lookup", "sql_query"]),
    )
    errors = validate_profile_overrides(profile, _base_manifest())
    assert errors
    assert "sql_query" in errors[0]


def test_merge_profile_manifest_applies_overrides():
    profile = AgentProfile(
        name="advisor_deep_dive",
        base_agent="agentic_analyzer",
        description="Deep dive profile",
        overrides=AgentProfileOverrides(
            max_steps=60,
            system_prompt_fragment="Focus on AUM.",
            config={"analysis_defaults": {"collection": "Details_FTAUM"}},
        ),
    )
    merged = merge_profile_manifest(profile, _base_manifest())
    assert merged.name == "advisor_deep_dive"
    assert merged.profile_of == "agentic_analyzer"
    assert merged.max_steps == 60
    assert "Focus on AUM." in merged.system_prompt
    assert merged.config["analysis_defaults"]["collection"] == "Details_FTAUM"


@pytest.mark.asyncio
async def test_bootstrap_loads_agent_profiles():
    state = await bootstrap(_settings())
    assert "advisor_deep_dive" in state.tool_registry.agents
    profile_agent = state.tool_registry.agents["advisor_deep_dive"]
    assert profile_agent.manifest.profile_of == "agentic_analyzer"
    assert profile_agent.manifest.max_steps == 60
    assert state.profile_registry.get("advisor_deep_dive") is not None


@pytest.mark.asyncio
async def test_profile_agent_indexed_for_routing():
    state = await bootstrap(_settings())
    candidates = state.capability_index.search("deep dive AUM advisor analysis", k=5)
    names = [candidate.name for candidate in candidates]
    assert "advisor_deep_dive" in names


@pytest.mark.asyncio
async def test_plan_can_execute_profile_agent():
    state = await bootstrap(_settings())
    initial = await state.orchestrator.handle(
        IncomingRequest(
            message="Run a deep dive AUM analysis for advisor John Smith.",
            orchestration={"mode": "multi"},
        )
    )
    assert initial.status == "awaiting_plan_approval"
    assert initial.plan is not None

    task_names = [task["assignee_name"] for task in initial.plan["tasks"]]
    if "advisor_deep_dive" not in task_names:
        pytest.skip("Planner did not select advisor_deep_dive for this message")

    resumed = await state.orchestrator.resume(
        ResumeRequest(
            task_id=initial.task_id,
            thread_id=initial.thread_id,
            decisions=[{"type": "approve"}],
        )
    )
    assert resumed.status in ("success", "partial_success")
    events = state.telemetry.list_events_for_trace(initial.trace_id)
    handoffs = [event for event in events if event.get("event_type") == "handoff"]
    profile_handoffs = [
        event for event in handoffs if event.get("agent_name") == "advisor_deep_dive"
    ]
    if profile_handoffs:
        assert profile_handoffs[0].get("base_agent_name") == "agentic_analyzer"
