from __future__ import annotations

import json
import time
import uuid
from typing import Any

from harness.config.models import ConfigPlane
from harness.core.models import ExecutionBudget, HandoffPacket
from harness.core.request import IncomingRequest, OrchestratorResult, ResumeRequest
from harness.hitl.store import ApprovalStore, PendingApproval
from harness.orchestrator.alerts import maybe_send_plan_alert
from harness.orchestrator.plan_models import ExecutionPlan, TaskResult
from harness.orchestrator.plan_store import PlanRecord, PlanStore
from harness.orchestrator.planner import Planner
from harness.orchestrator.task_executor import TaskExecutor
from harness.registry.registry import ToolRegistry
from harness.settings import HarnessSettings
from harness.telemetry.bus import TelemetryBus
from harness.telemetry.events import PlanEvent


class PlanRunner:
    def __init__(
        self,
        *,
        registry: ToolRegistry,
        planner: Planner,
        task_executor: TaskExecutor,
        approval_store: ApprovalStore | None,
        telemetry: TelemetryBus,
        settings: HarnessSettings,
        config: ConfigPlane,
        plan_store: PlanStore | None = None,
    ) -> None:
        self._registry = registry
        self._planner = planner
        self._task_executor = task_executor
        self._approval_store = approval_store
        self._telemetry = telemetry
        self._settings = settings
        self._config = config
        self._plan_store = plan_store
        self._plan_timings: dict[str, float] = {}

    async def start(
        self,
        request: IncomingRequest,
        *,
        trace_id: str,
        thread_id: str,
        root_span_id: str | None = None,
    ) -> OrchestratorResult:
        plan = self._planner.create_plan(request)
        plan.status = "awaiting_approval"

        if (
            self._settings.orchestration_fast_path_single_task
            and len(plan.tasks) == 1
            and not self._settings.orchestration_require_plan_approval
        ):
            return await self._execute_approved_plan(
                plan,
                message=request.message,
                trace_id=trace_id,
                thread_id=thread_id,
                root_span_id=root_span_id,
            )

        if self._approval_store is None:
            return OrchestratorResult(
                trace_id=trace_id,
                thread_id=thread_id,
                status="failure",
                message="Plan approval required but approval store is not configured.",
            )

        self._approval_store.save(
            PendingApproval(
                thread_id=thread_id,
                task_id=plan.plan_id,
                agent_name="__plan__",
                trace_id=trace_id,
                interrupt_payload={
                    "kind": "plan_approval",
                    "message": request.message,
                    "plan": plan.model_dump(),
                    "thread_id": thread_id,
                },
            )
        )
        self._emit_plan(trace_id, plan, action="created", parent_span_id=root_span_id)
        self._persist_plan(
            plan,
            trace_id=trace_id,
            thread_id=thread_id,
            status="awaiting_approval",
            message=request.message,
        )

        return OrchestratorResult(
            trace_id=trace_id,
            thread_id=thread_id,
            status="awaiting_plan_approval",
            message="Review the plan and approve via POST /v1/resume.",
            task_id=plan.plan_id,
            plan=plan.model_dump(),
            route={"mode": "multi_agent", "planner": "llm" if not self._settings.force_stub_models else "stub"},
            events=self._telemetry.list_events_for_trace(trace_id),
        )

    async def resume(
        self,
        request: ResumeRequest,
        approval: PendingApproval,
        *,
        root_span_id: str | None = None,
    ) -> OrchestratorResult:
        payload = approval.interrupt_payload
        decision = request.decisions[0] if request.decisions else {"type": "reject"}
        decision_type = decision.get("type", "reject")

        if decision_type == "reject":
            if self._approval_store:
                self._approval_store.resolve(request.task_id)
            self._emit_plan(
                approval.trace_id,
                ExecutionPlan.model_validate(payload.get("plan", {})),
                action="rejected",
                parent_span_id=root_span_id,
                display_message="Plan rejected by user.",
            )
            return OrchestratorResult(
                trace_id=approval.trace_id,
                thread_id=request.thread_id,
                status="failure",
                message="Plan rejected.",
                task_id=request.task_id,
                events=self._telemetry.list_events_for_trace(approval.trace_id),
            )

        plan_data = payload.get("plan", {})
        if decision_type == "edit" and decision.get("plan"):
            plan_data = decision["plan"]
        plan = ExecutionPlan.model_validate(plan_data)
        plan.status = "approved"

        if self._approval_store:
            self._approval_store.resolve(request.task_id)

        self._emit_plan(
            approval.trace_id,
            plan,
            action="approved",
            parent_span_id=root_span_id,
            display_message="Plan approved. Executing tasks.",
        )

        self._plan_timings[plan.plan_id] = time.perf_counter()
        self._persist_plan(
            plan,
            trace_id=approval.trace_id,
            thread_id=request.thread_id,
            status="approved",
            message=str(payload.get("message") or ""),
        )

        return await self._execute_approved_plan(
            plan,
            message=str(payload.get("message") or ""),
            trace_id=approval.trace_id,
            thread_id=request.thread_id,
            root_span_id=root_span_id,
            task_id=request.task_id,
        )

    async def _execute_approved_plan(
        self,
        plan: ExecutionPlan,
        *,
        message: str,
        trace_id: str,
        thread_id: str,
        root_span_id: str | None = None,
        task_id: str | None = None,
    ) -> OrchestratorResult:
        started = self._plan_timings.get(plan.plan_id, time.perf_counter())
        task_results, plan = await self._task_executor.execute(
            plan,
            trace_id=trace_id,
            thread_id=thread_id,
            original_message=message,
            root_span_id=root_span_id,
        )

        synth_output, synth_artifacts = await self._run_synthesizer(
            plan,
            task_results,
            message=message,
            trace_id=trace_id,
            thread_id=thread_id,
        )

        if plan.status == "partial":
            status = "partial_success"
            plan_action = "partial"
        elif plan.status == "failed":
            status = "failure"
            plan_action = "failed"
        else:
            status = "success"
            plan_action = "completed"

        self._emit_plan(
            trace_id,
            plan,
            action=plan_action,
            parent_span_id=root_span_id,
            display_message=synth_output.get("response", "Plan completed."),
        )

        duration_ms = int((time.perf_counter() - started) * 1000)
        metrics = _plan_metrics(task_results, duration_ms=duration_ms)
        self._persist_plan(
            plan,
            trace_id=trace_id,
            thread_id=thread_id,
            status=plan.status,
            message=str(synth_output.get("response") or ""),
            task_results={k: v.model_dump() for k, v in task_results.items()},
            metrics=metrics,
        )

        await maybe_send_plan_alert(
            settings=self._settings,
            status=status,
            trace_id=trace_id,
            plan_id=plan.plan_id,
            message=str(synth_output.get("response") or ""),
            task_results={k: v.model_dump() for k, v in task_results.items()},
        )

        return OrchestratorResult(
            trace_id=trace_id,
            thread_id=thread_id,
            status=status,
            message=str(synth_output.get("response") or "Plan completed."),
            task_id=task_id or plan.plan_id,
            plan=plan.model_dump(),
            task_results={k: v.model_dump() for k, v in task_results.items()},
            output=synth_output,
            artifacts=synth_artifacts,
            route={"mode": "multi_agent", "plan_status": plan.status},
            events=self._telemetry.list_events_for_trace(trace_id),
        )

    async def _run_synthesizer(
        self,
        plan: ExecutionPlan,
        task_results: dict[str, TaskResult],
        *,
        message: str,
        trace_id: str,
        thread_id: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        synthesizer_name = self._settings.orchestration_synthesizer_agent
        agent = self._registry.agents.get(synthesizer_name)
        completed = [r.title for r in task_results.values() if r.status == "success"]
        failed = [
            {"title": r.title, "user_message": r.user_message}
            for r in task_results.values()
            if r.status in ("failure", "blocked")
        ]

        if agent is None:
            synthesis = _fallback_synthesis(completed, failed)
            return {
                "response": synthesis,
                "completed_tasks": completed,
                "failed_tasks": failed,
            }, []

        stub = agent.manifest.config.get("stub")
        if stub and self._settings.force_stub_models:
            from harness.agents.stub_runner import resolve_template

            variables = {
                "synthesis": _fallback_synthesis(completed, failed),
                "completed_tasks": ", ".join(completed) or "none",
                "failed_tasks": "; ".join(
                    f"{item['title']}: {item.get('user_message', '')}" for item in failed
                )
                or "none",
            }
            output = resolve_template(stub.get("output", {}), variables, {})
            return output, []

        packet = HandoffPacket(
            task_id=uuid.uuid4().hex,
            parent_trace_id=trace_id,
            objective=message,
            context_summary=json.dumps(
                {
                    "plan": plan.model_dump(),
                    "task_results": {k: v.model_dump() for k, v in task_results.items()},
                },
                default=str,
            )[:6000],
            budget=ExecutionBudget(
                max_steps=agent.manifest.max_steps,
                max_tokens=agent.manifest.max_tokens_budget,
                timeout_s=agent.manifest.timeout_s,
            ),
            memory_namespace=("agent", synthesizer_name, "plan", plan.plan_id),
        )
        result = await agent.run(packet)
        output = result.output or {
            "response": _fallback_synthesis(completed, failed),
            "completed_tasks": completed,
            "failed_tasks": failed,
        }
        artifacts = [
            {"url": ref.url, "kind": ref.kind, "metadata": ref.metadata}
            for ref in result.artifacts
        ]
        return output, artifacts

    def _emit_plan(
        self,
        trace_id: str,
        plan: ExecutionPlan,
        *,
        action: str,
        parent_span_id: str | None,
        display_message: str = "",
    ) -> None:
        self._telemetry.emit(
            PlanEvent(
                trace_id=trace_id,
                span_id=self._telemetry.new_span_id(),
                parent_span_id=parent_span_id,
                plan_id=plan.plan_id,
                action=action,  # type: ignore[arg-type]
                display_message=display_message,
                plan_snapshot=plan.model_dump(),
            )
        )

    def _persist_plan(
        self,
        plan: ExecutionPlan,
        *,
        trace_id: str,
        thread_id: str,
        status: str,
        message: str,
        task_results: dict[str, Any] | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        if self._plan_store is None:
            return
        self._plan_store.upsert(
            PlanRecord(
                plan_id=plan.plan_id,
                trace_id=trace_id,
                thread_id=thread_id,
                status=status,
                message=message,
                plan=plan.model_dump(),
                task_results=task_results or {},
                metrics=metrics or {},
            )
        )


def _plan_metrics(task_results: dict[str, TaskResult], *, duration_ms: int) -> dict[str, Any]:
    total = len(task_results)
    succeeded = sum(1 for r in task_results.values() if r.status == "success")
    failed = sum(1 for r in task_results.values() if r.status in ("failure", "blocked", "skipped"))
    return {
        "duration_ms": duration_ms,
        "task_count": total,
        "tasks_succeeded": succeeded,
        "tasks_failed": failed,
        "task_success_rate": succeeded / total if total else 0.0,
    }


def _fallback_synthesis(completed: list[str], failed: list[dict[str, Any]]) -> str:
    parts = []
    if completed:
        parts.append(f"Completed: {', '.join(completed)}.")
    if failed:
        caveats = "; ".join(
            f"{item['title']} ({item.get('user_message', 'failed')})" for item in failed
        )
        parts.append(f"Some steps could not be completed: {caveats}")
    return " ".join(parts) if parts else "Plan completed."
