from __future__ import annotations

import json
import uuid
from typing import Any

from harness.core.context import RunContext
from harness.core.models import ExecutionBudget, HandoffPacket
from harness.memory.artifacts import ArtifactStore
from harness.orchestrator.dag_executor import DagExecutor
from harness.orchestrator.plan_models import ExecutionPlan, PlannedTask, TaskResult
from harness.orchestrator.skill_input import infer_skill_input
from harness.registry.registry import ToolRegistry
from harness.settings import HarnessSettings
from harness.telemetry.bus import TelemetryBus


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
        self._dag = DagExecutor(
            telemetry=telemetry,
            settings=settings,
            run_task=self._run_task,
        )

    async def execute(
        self,
        plan: ExecutionPlan,
        *,
        trace_id: str,
        thread_id: str,
        original_message: str,
        root_span_id: str | None = None,
    ) -> tuple[dict[str, TaskResult], ExecutionPlan]:
        plan.status = "executing"
        with self._telemetry.span(
            "execute_plan",
            trace_id=trace_id,
            otel_attributes={
                "harness.operation": "execute_plan",
                "harness.plan.id": plan.plan_id,
                "harness.plan.parallel": self._settings.orchestration_parallel,
            },
        ):
            return await self._dag.execute(
                plan,
                trace_id=trace_id,
                thread_id=thread_id,
                original_message=original_message,
                root_span_id=root_span_id,
            )

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
        task_span_id = self._telemetry.new_span_id()
        with self._telemetry.span(
            f"task:{task.task_id}",
            trace_id=trace_id,
            span_id=task_span_id,
            otel_attributes={
                "harness.task.id": task.task_id,
                "harness.task.assignee": task.assignee_name,
                "harness.task.kind": task.assignee_kind,
            },
        ):
            artifacts = ArtifactStore()
            context = RunContext(
                trace_id=trace_id,
                thread_id=thread_id,
                tools=self._registry.tools,
                connectors=self._connectors,
                artifacts=artifacts,
                metadata={
                    "telemetry": self._telemetry,
                    "parent_span_id": task_span_id,
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
                max_steps = task.max_steps or agent.manifest.max_steps
                timeout_s = task.timeout_s or agent.manifest.timeout_s
                packet = HandoffPacket(
                    task_id=uuid.uuid4().hex,
                    parent_trace_id=trace_id,
                    objective=task.objective or original_message,
                    context_summary=_build_agent_context(task, results),
                    budget=ExecutionBudget(
                        max_steps=max_steps,
                        max_tokens=agent.manifest.max_tokens_budget,
                        timeout_s=timeout_s,
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
