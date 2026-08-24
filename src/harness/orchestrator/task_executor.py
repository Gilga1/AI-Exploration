from __future__ import annotations

import json
import uuid
from typing import Any

from harness.core.context import RunContext
from harness.core.models import ExecutionBudget, HandoffPacket
from harness.memory.artifacts import ArtifactStore
from harness.orchestrator.skill_input import infer_skill_input
from harness.orchestrator.plan_models import (
    ExecutionPlan,
    PlannedTask,
    TaskResult,
    build_failure_user_message,
    topological_order,
)
from harness.registry.registry import ToolRegistry
from harness.settings import HarnessSettings
from harness.telemetry.bus import TelemetryBus
from harness.telemetry.events import TaskEvent


class TaskExecutor:
    def __init__(
        self,
        *,
        registry: ToolRegistry,
        connectors: dict[str, Any],
        telemetry: TelemetryBus,
        settings: HarnessSettings,
    ) -> None:
        self._registry = registry
        self._connectors = connectors
        self._telemetry = telemetry
        self._settings = settings

    async def execute(
        self,
        plan: ExecutionPlan,
        *,
        trace_id: str,
        thread_id: str,
        original_message: str,
        root_span_id: str | None = None,
    ) -> tuple[dict[str, TaskResult], ExecutionPlan]:
        plan_id = plan.plan_id
        plan.status = "executing"
        results: dict[str, TaskResult] = {}

        for task in topological_order(plan.tasks):
            if not _dependencies_satisfied(task, results):
                task.status = "blocked"
                result = TaskResult(
                    task_id=task.task_id,
                    title=task.title,
                    assignee_kind=task.assignee_kind,
                    assignee_name=task.assignee_name,
                    status="blocked",
                    user_message=f'Skipped "{task.title}" because an upstream task failed.',
                )
                results[task.task_id] = result
                self._emit_task(
                    trace_id,
                    task,
                    plan_id=plan_id,
                    action="failed",
                    display_message=result.user_message or "",
                    parent_span_id=root_span_id,
                    error="blocked_by_dependency",
                )
                continue

            task.status = "running"
            self._emit_task(
                trace_id,
                task,
                plan_id=plan_id,
                action="started",
                display_message=f"Running: {task.title}",
                parent_span_id=root_span_id,
            )

            try:
                result = await self._run_task(
                    task,
                    results=results,
                    trace_id=trace_id,
                    thread_id=thread_id,
                    original_message=original_message,
                    root_span_id=root_span_id,
                )
                task.status = "success"
                results[task.task_id] = result
                self._emit_task(
                    trace_id,
                    task,
                    plan_id=plan_id,
                    action="completed",
                    display_message=f"Completed: {task.title}",
                    parent_span_id=root_span_id,
                )
            except Exception as exc:
                error = str(exc)
                user_message = build_failure_user_message(task, error)
                task.status = "failure"
                task.error = error
                task.user_message = user_message
                result = TaskResult(
                    task_id=task.task_id,
                    title=task.title,
                    assignee_kind=task.assignee_kind,
                    assignee_name=task.assignee_name,
                    status="failure",
                    error=error,
                    user_message=user_message,
                )
                results[task.task_id] = result
                self._emit_task(
                    trace_id,
                    task,
                    plan_id=plan_id,
                    action="failed",
                    display_message=user_message,
                    parent_span_id=root_span_id,
                    error=error,
                )
                if not self._settings.orchestration_continue_on_failure:
                    break

        successes = [r for r in results.values() if r.status == "success"]
        failures = [r for r in results.values() if r.status == "failure"]
        if failures and successes:
            plan.status = "partial"
        elif failures and not successes:
            plan.status = "failed"
        else:
            plan.status = "completed"
        return results, plan

    async def _run_task(
        self,
        task: PlannedTask,
        *,
        results: dict[str, TaskResult],
        trace_id: str,
        thread_id: str,
        original_message: str,
        root_span_id: str | None,
    ) -> TaskResult:
        artifacts = ArtifactStore()
        context = RunContext(
            trace_id=trace_id,
            thread_id=thread_id,
            tools=self._registry.tools,
            connectors=self._connectors,
            artifacts=artifacts,
            metadata={
                "telemetry": self._telemetry,
                "parent_span_id": root_span_id,
            },
        )

        if task.assignee_kind == "skill":
            skill = self._registry.skills[task.assignee_name]
            payload_data = _build_skill_input(task, results, original_message)
            payload = skill.validate_input(payload_data)
            output_model = await skill.execute(payload, context=context)
            output = output_model.model_dump() if hasattr(output_model, "model_dump") else dict(output_model)
        else:
            agent = self._registry.agents[task.assignee_name]
            packet = HandoffPacket(
                task_id=uuid.uuid4().hex,
                parent_trace_id=trace_id,
                objective=task.objective or original_message,
                context_summary=_build_agent_context(task, results),
                budget=ExecutionBudget(
                    max_steps=agent.manifest.max_steps,
                    max_tokens=agent.manifest.max_tokens_budget,
                    timeout_s=agent.manifest.timeout_s,
                ),
                memory_namespace=("agent", task.assignee_name, "plan", task.task_id),
            )
            agent_result = await agent.run(packet)
            if agent_result.status != "success":
                raise RuntimeError(agent_result.trace_summary or f"Agent {task.assignee_name} failed")
            output = agent_result.output or {}

        stored_artifacts = [
            {"url": ref["url"], "kind": ref["kind"], "metadata": ref.get("metadata", {})}
            for ref in artifacts._artifacts.values()
        ]
        return TaskResult(
            task_id=task.task_id,
            title=task.title,
            assignee_kind=task.assignee_kind,
            assignee_name=task.assignee_name,
            status="success",
            output=output,
            artifacts=stored_artifacts,
        )

    def _emit_task(
        self,
        trace_id: str,
        task: PlannedTask,
        *,
        plan_id: str,
        action: str,
        display_message: str,
        parent_span_id: str | None,
        error: str | None = None,
    ) -> None:
        self._telemetry.emit(
            TaskEvent(
                trace_id=trace_id,
                span_id=self._telemetry.new_span_id(),
                parent_span_id=parent_span_id,
                plan_id=plan_id,
                task_id=task.task_id,
                title=task.title,
                assignee_kind=task.assignee_kind,
                assignee_name=task.assignee_name,
                action=action,
                display_message=display_message,
                error=error,
            )
        )


def _dependencies_satisfied(task: PlannedTask, results: dict[str, TaskResult]) -> bool:
    for dep in task.depends_on:
        dep_result = results.get(dep)
        if dep_result is None or dep_result.status != "success":
            return False
    return True


def _build_agent_context(task: PlannedTask, results: dict[str, TaskResult]) -> str:
    prior = {
        task_id: result.output
        for task_id, result in results.items()
        if result.status == "success" and result.output
    }
    return json.dumps({"task": task.model_dump(), "prior_outputs": prior}, default=str)[:4000]


def _build_skill_input(
    task: PlannedTask,
    results: dict[str, TaskResult],
    original_message: str,
) -> dict[str, Any]:
    if task.skill_input_template:
        payload = dict(task.skill_input_template)
    else:
        payload = infer_skill_input(task.assignee_name, original_message)

    for field, source in task.inputs_from.items():
        value = _resolve_input_source(source, results)
        if value is not None:
            payload[field] = value
    return payload


def _resolve_input_source(source: str, results: dict[str, TaskResult]) -> Any:
    if "." not in source:
        return source
    task_id, _, key = source.partition(".")
    result = results.get(task_id)
    if result is None or not result.output:
        return None
    return result.output.get(key)
