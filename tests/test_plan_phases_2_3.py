from __future__ import annotations

import asyncio
import time

import pytest
from httpx import ASGITransport, AsyncClient

from harness.api import create_app
from harness.bootstrap import bootstrap
from harness.core.request import IncomingRequest, ResumeRequest
from harness.orchestrator.dag_executor import DagExecutor
from harness.orchestrator.plan_models import ExecutionPlan, PlannedTask, TaskResult
from harness.orchestrator.waterfall import build_waterfall
from harness.settings import HarnessSettings
from harness.telemetry.bus import TelemetryBus


def _settings(**kwargs) -> HarnessSettings:
    defaults = dict(
        scan_paths=["harness/tools", "harness/skills"],
        connector_health_check=False,
        force_stub_models=True,
        langfuse_enabled=False,
        orchestration_mode="multi",
        orchestration_parallel=True,
        orchestration_max_parallel=3,
    )
    defaults.update(kwargs)
    return HarnessSettings(**defaults)


@pytest.mark.asyncio
async def test_parallel_dag_runs_independent_tasks_concurrently():
    telemetry = TelemetryBus(enable_otel=False, enable_ledger=False)
    settings = _settings()
    active = 0
    peak = 0
    lock = asyncio.Lock()

    async def mock_run_task(task, **kwargs):
        nonlocal active, peak
        async with lock:
            active += 1
            peak = max(peak, active)
        await asyncio.sleep(0.15)
        async with lock:
            active -= 1
        return TaskResult(
            task_id=task.task_id,
            title=task.title,
            assignee_kind=task.assignee_kind,
            assignee_name=task.assignee_name,
            status="success",
            output={"ok": True},
        )

    plan = ExecutionPlan(
        plan_id="parallel-test",
        tasks=[
            PlannedTask(task_id="a", title="A", assignee_kind="agent", assignee_name="x"),
            PlannedTask(task_id="b", title="B", assignee_kind="agent", assignee_name="x"),
            PlannedTask(
                task_id="c",
                title="C",
                assignee_kind="agent",
                assignee_name="x",
                depends_on=["a", "b"],
            ),
        ],
        failure_policy="continue",
    )

    executor = DagExecutor(telemetry=telemetry, settings=settings, run_task=mock_run_task)
    results, final_plan = await executor.execute(
        plan,
        trace_id="trace-parallel",
        thread_id="thread-parallel",
        original_message="test",
        root_span_id=None,
    )

    assert peak >= 2
    assert final_plan.status == "completed"
    assert len(results) == 3
    assert all(r.status == "success" for r in results.values())


@pytest.mark.asyncio
async def test_diamond_dag_respects_dependencies():
    telemetry = TelemetryBus(enable_otel=False, enable_ledger=False)
    settings = _settings(orchestration_parallel=True)
    order: list[str] = []

    async def mock_run_task(task, **kwargs):
        order.append(task.task_id)
        return TaskResult(
            task_id=task.task_id,
            title=task.title,
            assignee_kind=task.assignee_kind,
            assignee_name=task.assignee_name,
            status="success",
        )

    plan = ExecutionPlan(
        plan_id="diamond",
        tasks=[
            PlannedTask(task_id="a", title="A", assignee_kind="agent", assignee_name="x"),
            PlannedTask(task_id="b", title="B", assignee_kind="agent", assignee_name="x", depends_on=["a"]),
            PlannedTask(task_id="c", title="C", assignee_kind="agent", assignee_name="x", depends_on=["a"]),
            PlannedTask(
                task_id="d",
                title="D",
                assignee_kind="agent",
                assignee_name="x",
                depends_on=["b", "c"],
            ),
        ],
    )
    executor = DagExecutor(telemetry=telemetry, settings=settings, run_task=mock_run_task)
    results, final_plan = await executor.execute(
        plan,
        trace_id="trace-diamond",
        thread_id="thread-diamond",
        original_message="test",
        root_span_id=None,
    )
    assert order.index("a") < order.index("b")
    assert order.index("a") < order.index("c")
    assert order.index("b") < order.index("d")
    assert order.index("c") < order.index("d")
    assert final_plan.status == "completed"
    assert len(results) == 4


@pytest.mark.asyncio
async def test_fail_fast_skips_remaining_tasks():
    telemetry = TelemetryBus(enable_otel=False, enable_ledger=False)
    settings = _settings(orchestration_parallel=False)

    async def mock_run_task(task, **kwargs):
        if task.task_id == "a":
            raise RuntimeError("boom")
        return TaskResult(
            task_id=task.task_id,
            title=task.title,
            assignee_kind=task.assignee_kind,
            assignee_name=task.assignee_name,
            status="success",
        )

    plan = ExecutionPlan(
        plan_id="fail-fast",
        tasks=[
            PlannedTask(task_id="a", title="A", assignee_kind="agent", assignee_name="x"),
            PlannedTask(task_id="b", title="B", assignee_kind="agent", assignee_name="x"),
        ],
        failure_policy="fail_fast",
    )
    executor = DagExecutor(telemetry=telemetry, settings=settings, run_task=mock_run_task)
    results, final_plan = await executor.execute(
        plan,
        trace_id="t",
        thread_id="t",
        original_message="test",
        root_span_id=None,
    )
    assert results["a"].status == "failure"
    assert final_plan.status == "failed"


@pytest.mark.asyncio
async def test_plan_progress_events_emitted():
    state = await bootstrap(_settings())
    initial = await state.orchestrator.handle(
        IncomingRequest(
            message="Research competitor Zeta Corp and analyze advisor John Smith sales.",
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
    events = state.telemetry.list_events_for_trace(initial.trace_id)
    assert any(e.get("event_type") == "plan_progress" for e in events)
    assert any(e.get("event_type") == "task" and e.get("duration_ms") is not None for e in events if e.get("action") == "completed")


@pytest.mark.asyncio
async def test_admin_plans_endpoints():
    settings = _settings()
    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            handle_resp = await client.post(
                "/v1/handle",
                json={
                    "message": "Research competitor Omega LLC and analyze advisor Jane Doe sales.",
                    "orchestration": {"mode": "multi"},
                },
            )
            plan_id = handle_resp.json()["task_id"]
            plans_resp = await client.get("/admin/plans")
            assert plans_resp.status_code == 200
            assert plans_resp.json()["count"] >= 1

            detail_resp = await client.get(f"/admin/plans/{plan_id}")
            assert detail_resp.status_code == 200
            assert detail_resp.json()["plan_id"] == plan_id

            await client.post(
                "/v1/resume",
                json={
                    "task_id": plan_id,
                    "thread_id": handle_resp.json()["thread_id"],
                    "decisions": [{"type": "approve"}],
                },
            )
            waterfall_resp = await client.get(f"/admin/plans/{plan_id}/waterfall")
            assert waterfall_resp.status_code == 200
            body = waterfall_resp.json()
            assert "waterfall" in body
            assert body["waterfall"]

            metrics_resp = await client.get("/admin/metrics")
            assert metrics_resp.status_code == 200
            assert "plans" in metrics_resp.json()


def test_waterfall_builder_groups_plan_and_tasks():
    events = [
        {
            "event_type": "plan",
            "plan_id": "p1",
            "action": "created",
            "display_message": "plan created",
            "timestamp": "2026-01-01T00:00:00Z",
        },
        {
            "event_type": "task",
            "plan_id": "p1",
            "task_id": "t1",
            "title": "Task 1",
            "assignee_kind": "agent",
            "assignee_name": "agentic_analyzer",
            "action": "completed",
            "duration_ms": 120,
            "timestamp": "2026-01-01T00:00:01Z",
        },
        {
            "event_type": "tool",
            "tool_name": "index_lookup",
            "timestamp": "2026-01-01T00:00:02Z",
        },
    ]
    waterfall = build_waterfall(events)
    assert waterfall
    assert waterfall[0]["kind"] == "plan"
    assert waterfall[0]["children"]
