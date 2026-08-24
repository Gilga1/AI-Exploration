from __future__ import annotations

import pytest

from harness.bootstrap import bootstrap
from harness.core.request import IncomingRequest, ResumeRequest
from harness.orchestrator.plan_models import PlannedTask, build_failure_user_message
from harness.orchestrator.task_executor import TaskExecutor
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


@pytest.mark.asyncio
async def test_multi_agent_request_awaits_plan_approval():
    state = await bootstrap(_settings())
    result = await state.orchestrator.handle(
        IncomingRequest(
            message="Research competitor Beta Inc and analyze advisor John Smith product sales.",
            orchestration={"mode": "multi"},
        )
    )
    assert result.status == "awaiting_plan_approval"
    assert result.plan is not None
    assert len(result.plan["tasks"]) >= 2
    assert result.task_id == result.plan["plan_id"]
    assert any(e.get("event_type") == "plan" for e in result.events)


@pytest.mark.asyncio
async def test_approve_plan_executes_tasks_and_synthesizer():
    state = await bootstrap(_settings())
    initial = await state.orchestrator.handle(
        IncomingRequest(
            message="Research competitor Gamma LLC and analyze advisor John Smith sales by product.",
            orchestration={"mode": "multi"},
        )
    )
    assert initial.status == "awaiting_plan_approval"
    resumed = await state.orchestrator.resume(
        ResumeRequest(
            task_id=initial.task_id,
            thread_id=initial.thread_id,
            decisions=[{"type": "approve"}],
        )
    )
    assert resumed.status in ("success", "partial_success")
    assert resumed.task_results is not None
    assert len(resumed.task_results) >= 2
    assert resumed.output is not None
    assert "response" in resumed.output
    events = state.telemetry.list_events_for_trace(initial.trace_id)
    assert any(e.get("event_type") == "task" and e.get("action") == "started" for e in events)
    assert any(e.get("event_type") == "task" and e.get("action") == "completed" for e in events)


@pytest.mark.asyncio
async def test_reject_plan_does_not_execute_tasks():
    state = await bootstrap(_settings())
    initial = await state.orchestrator.handle(
        IncomingRequest(
            message="Research competitor Delta Co and analyze advisor Jane Doe sales.",
            orchestration={"mode": "multi"},
        )
    )
    resumed = await state.orchestrator.resume(
        ResumeRequest(
            task_id=initial.task_id,
            thread_id=initial.thread_id,
            decisions=[{"type": "reject"}],
        )
    )
    assert resumed.status == "failure"
    assert "rejected" in resumed.message.lower()


@pytest.mark.asyncio
async def test_synthesizer_agent_registered():
    state = await bootstrap(_settings())
    assert "synthesizer" in state.tool_registry.agents


@pytest.mark.asyncio
async def test_partial_success_when_task_fails(monkeypatch):
    state = await bootstrap(_settings())
    agent = state.tool_registry.agents["agentic_analyzer"]
    original_run = agent.run

    async def failing_run(packet, *, resume_decisions=None):
        return await type(agent).run(agent, packet, resume_decisions=resume_decisions)

    async def patched_run(packet, *, resume_decisions=None):
        from harness.core.models import AgentResult

        return AgentResult(
            task_id=packet.task_id,
            status="failure",
            trace_summary="Simulated analyzer failure",
        )

    monkeypatch.setattr(agent, "run", patched_run)

    initial = await state.orchestrator.handle(
        IncomingRequest(
            message="Research competitor Epsilon Ltd and analyze advisor John Smith sales.",
            orchestration={"mode": "multi"},
        )
    )
    resumed = await state.orchestrator.resume(
        ResumeRequest(
            task_id=initial.task_id,
            thread_id=initial.thread_id,
            decisions=[{"type": "approve"}],
        )
    )
    assert resumed.status == "partial_success"
    assert resumed.output is not None
    failed = [r for r in resumed.task_results.values() if r["status"] == "failure"]
    assert failed
    assert resumed.output.get("failed_tasks")


def test_failure_user_message_includes_fallback_hint():
    task = PlannedTask(
        task_id="t2",
        title="Analyze John Smith sales",
        assignee_kind="agent",
        assignee_name="agentic_analyzer",
        fallback_hint="sales figures for John Smith",
    )
    message = build_failure_user_message(task, "Connector unavailable")
    assert "John Smith" in message
    assert "sales figures" in message
