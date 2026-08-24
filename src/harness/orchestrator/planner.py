from __future__ import annotations

import json
import re
import uuid
from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage

from harness.config.models import ConfigPlane
from harness.core.request import IncomingRequest
from harness.llm.factory import build_chat_model
from harness.orchestrator.plan_models import ExecutionPlan, PlannedTask
from harness.orchestrator.workflow_registry import PlannerMode, WorkflowRegistry
from harness.registry.registry import ToolRegistry
from harness.routing.capability_index import CapabilityIndex
from harness.settings import HarnessSettings


class Planner:
    def __init__(
        self,
        *,
        registry: ToolRegistry,
        capability_index: CapabilityIndex,
        config: ConfigPlane,
        settings: HarnessSettings,
        workflows: WorkflowRegistry | None = None,
    ) -> None:
        self._registry = registry
        self._index = capability_index
        self._config = config
        self._settings = settings
        self._workflows = workflows

    def create_plan(self, request: IncomingRequest) -> ExecutionPlan:
        mode: PlannerMode = self._settings.orchestration_planner  # type: ignore[assignment]

        if self._workflows is not None and mode in ("auto", "template", "hybrid"):
            plan = self._workflows.try_build_plan(request.message, mode=mode)
            if plan is not None:
                plan.rationale = self._annotate_rationale(plan.rationale, mode=mode)
                return plan
            if mode == "template":
                return _empty_template_plan(request.message)

        if mode == "template":
            return _empty_template_plan(request.message)

        if self._settings.force_stub_models:
            return _index_plan(
                request.message,
                self._index,
                self._registry,
                self._settings,
                mode=mode,
            )

        model_cfg = next(
            (m for m in self._config.models.models if m.name == self._settings.orchestration_planner_model),
            None,
        )
        if model_cfg is None or model_cfg.provider == "stub":
            return _heuristic_plan(
                request.message,
                self._index,
                self._registry,
                self._settings,
                mode=mode,
            )

        return _llm_plan(
            request.message,
            registry=self._registry,
            config=self._config,
            settings=self._settings,
            model_name=self._settings.orchestration_planner_model,
            mode=mode,
            capability_index=self._index,
        )

    def _annotate_rationale(self, rationale: str, *, mode: PlannerMode) -> str:
        if mode == "hybrid":
            return f"{rationale} (hybrid: template structure + LLM objective refinement)"
        if mode == "auto":
            return f"{rationale} (auto-selected workflow template)"
        return rationale


def _empty_template_plan(message: str) -> ExecutionPlan:
    return ExecutionPlan(
        plan_id=uuid.uuid4().hex,
        tasks=[],
        rationale="No workflow template matched the request.",
        status="awaiting_approval",
    )


def _llm_plan(
    message: str,
    *,
    registry: ToolRegistry,
    config: ConfigPlane,
    settings: HarnessSettings,
    model_name: str,
    mode: PlannerMode,
    capability_index: CapabilityIndex,
) -> ExecutionPlan:
    model_cfg = next((m for m in config.models.models if m.name == model_name), None)
    assert model_cfg is not None
    model = build_chat_model(model_cfg)

    synthesizer = settings.orchestration_synthesizer_agent
    catalog = _build_catalog(registry, exclude={synthesizer})
    prompt = (
        "Create an execution plan for the user request using ONLY registered agents and skills.\n"
        "Do NOT include a synthesizer step — it runs automatically after all tasks.\n"
        "Respond with JSON only:\n"
        "{\n"
        '  "rationale": "...",\n'
        '  "tasks": [\n'
        "    {\n"
        '      "task_id": "t1",\n'
        '      "title": "user-visible title",\n'
        '      "objective": "natural language objective for agents",\n'
        '      "assignee_kind": "agent|skill",\n'
        '      "assignee_name": "<registered name>",\n'
        '      "depends_on": [],\n'
        '      "fallback_hint": "what user might do if this fails"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        f"Max tasks: {settings.orchestration_max_tasks}\n\n"
        f"User request: {message}\n\n"
        f"Catalog:\n{catalog}"
    )
    response = model.invoke(
        [
            SystemMessage(content="You are a task planner for a multi-agent harness."),
            HumanMessage(content=prompt),
        ]
    )
    content = response.content if isinstance(response.content, str) else str(response.content)
    parsed = _parse_json(content)
    plan = _plan_from_payload(parsed, registry, settings, message, capability_index)
    plan.rationale = f"{plan.rationale} (planner={mode})"
    return plan


def _heuristic_plan(
    message: str,
    index: CapabilityIndex,
    registry: ToolRegistry,
    settings: HarnessSettings,
    *,
    mode: PlannerMode,
) -> ExecutionPlan:
    return _index_plan(message, index, registry, settings, mode=mode)


def _index_plan(
    message: str,
    index: CapabilityIndex,
    registry: ToolRegistry,
    settings: HarnessSettings,
    *,
    mode: PlannerMode = "auto",
) -> ExecutionPlan:
    synthesizer = settings.orchestration_synthesizer_agent
    candidates = index.search(message, k=settings.routing_top_k)
    viable = [
        candidate
        for candidate in candidates
        if candidate.name != synthesizer and candidate.score >= settings.routing_min_score
    ]

    tasks: list[PlannedTask] = []
    seen: set[str] = set()
    for candidate in viable:
        if candidate.name in seen:
            continue
        seen.add(candidate.name)
        tasks.append(
            PlannedTask(
                task_id=f"t{len(tasks) + 1}",
                title=(candidate.description[:80] if candidate.description else candidate.name),
                objective=message,
                assignee_kind=candidate.kind,
                assignee_name=candidate.name,
                fallback_hint=f"results from {candidate.name}",
            )
        )
        if len(tasks) >= settings.orchestration_max_tasks:
            break

    if not tasks:
        for capability in registry.list_capabilities():
            if capability.kind == "agent" and capability.name != synthesizer:
                tasks.append(
                    PlannedTask(
                        task_id="t1",
                        title=capability.description[:80],
                        objective=message,
                        assignee_kind="agent",
                        assignee_name=capability.name,
                    )
                )
                break

    return ExecutionPlan(
        plan_id=uuid.uuid4().hex,
        tasks=tasks[: settings.orchestration_max_tasks],
        rationale=f"Capability-index plan (planner={mode}).",
        status="awaiting_approval",
    )


def _plan_from_payload(
    payload: dict[str, Any],
    registry: ToolRegistry,
    settings: HarnessSettings,
    message: str,
    capability_index: CapabilityIndex,
) -> ExecutionPlan:
    synthesizer = settings.orchestration_synthesizer_agent
    raw_tasks = payload.get("tasks") or []
    tasks: list[PlannedTask] = []
    for index, raw in enumerate(raw_tasks[: settings.orchestration_max_tasks]):
        kind = raw.get("assignee_kind", "agent")
        name = raw.get("assignee_name", "")
        if kind == "agent" and name not in registry.agents:
            continue
        if kind == "skill" and name not in registry.skills:
            continue
        if name == synthesizer:
            continue
        tasks.append(
            PlannedTask(
                task_id=raw.get("task_id") or f"t{index + 1}",
                title=raw.get("title") or name,
                objective=raw.get("objective") or message,
                assignee_kind=kind,
                assignee_name=name,
                depends_on=list(raw.get("depends_on") or []),
                inputs_from=dict(raw.get("inputs_from") or {}),
                skill_input_template=raw.get("skill_input_template"),
                fallback_hint=raw.get("fallback_hint"),
            )
        )

    if not tasks:
        return _index_plan(message, capability_index, registry, settings)

    return ExecutionPlan(
        plan_id=uuid.uuid4().hex,
        tasks=tasks,
        rationale=str(payload.get("rationale") or "LLM-generated plan"),
        status="awaiting_approval",
    )


def _build_catalog(registry: ToolRegistry, *, exclude: set[str]) -> str:
    lines: list[str] = []
    for cap in registry.list_capabilities():
        if cap.kind not in ("agent", "skill"):
            continue
        if cap.name in exclude:
            continue
        lines.append(f"- {cap.name} ({cap.kind}): {cap.description}")
    return "\n".join(lines)


def _parse_json(content: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", content, flags=re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
