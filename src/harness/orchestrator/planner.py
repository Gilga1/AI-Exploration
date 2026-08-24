from __future__ import annotations

import json
import re
import uuid
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from harness.config.models import ConfigPlane
from harness.core.request import IncomingRequest
from harness.llm.factory import build_chat_model
from harness.orchestrator.plan_models import ExecutionPlan, PlannedTask
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
    ) -> None:
        self._registry = registry
        self._index = capability_index
        self._config = config
        self._settings = settings

    def create_plan(self, request: IncomingRequest) -> ExecutionPlan:
        if self._settings.force_stub_models:
            return _stub_plan(request.message, self._registry, self._settings)

        model_cfg = next(
            (m for m in self._config.models.models if m.name == "fast_router"),
            None,
        )
        if model_cfg is None or model_cfg.provider == "stub":
            return _heuristic_plan(request.message, self._registry, self._settings)

        return _llm_plan(
            request.message,
            registry=self._registry,
            config=self._config,
            settings=self._settings,
            model_name="fast_router",
        )


def _llm_plan(
    message: str,
    *,
    registry: ToolRegistry,
    config: ConfigPlane,
    settings: HarnessSettings,
    model_name: str,
) -> ExecutionPlan:
    model_cfg = next((m for m in config.models.models if m.name == model_name), None)
    assert model_cfg is not None
    model = build_chat_model(model_cfg)

    catalog = _build_catalog(registry, exclude={"synthesizer"})
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
    return _plan_from_payload(parsed, registry, settings, message)


def _heuristic_plan(message: str, registry: ToolRegistry, settings: HarnessSettings) -> ExecutionPlan:
    return _stub_plan(message, registry, settings)


def _stub_plan(message: str, registry: ToolRegistry, settings: HarnessSettings) -> ExecutionPlan:
    lowered = message.lower()
    tasks: list[PlannedTask] = []
    if any(word in lowered for word in ("competitor", "research")):
        competitor = _extract_name(message, r"competitor\s+([A-Za-z0-9][A-Za-z0-9 ._-]*)")
        tasks.append(
            PlannedTask(
                task_id="t1",
                title=f"Research {competitor or 'competitor'}",
                objective=f"Research competitor {competitor or 'the named competitor'}",
                assignee_kind="agent",
                assignee_name="competitor_research",
                fallback_hint=f"public information about {competitor or 'the competitor'}",
            )
        )
    if any(word in lowered for word in ("advisor", "sales", "analyze", "analysis", "product")):
        advisor = _extract_name(message, r"advisor\s+([A-Za-z][A-Za-z .'-]*)")
        tasks.append(
            PlannedTask(
                task_id=f"t{len(tasks) + 1}",
                title=f"Analyze {advisor or 'advisor'} sales",
                objective=message,
                assignee_kind="agent",
                assignee_name="agentic_analyzer",
                fallback_hint=f"sales figures for {advisor or 'this advisor'}",
            )
        )
    if "pdf" in lowered and "markdown_to_pdf" in registry.skills:
        tasks.append(
            PlannedTask(
                task_id=f"t{len(tasks) + 1}",
                title="Render PDF",
                objective="",
                assignee_kind="skill",
                assignee_name="markdown_to_pdf",
                depends_on=[tasks[-1].task_id] if tasks else [],
                skill_input_template={"markdown": "# Brief\n\nGenerated from prior tasks.", "title": "Brief"},
                fallback_hint="exporting the final brief as a PDF",
            )
        )

    if not tasks:
        candidates = registry.list_capabilities()
        agent = next((c for c in candidates if c.kind == "agent" and c.name != "synthesizer"), None)
        if agent:
            tasks.append(
                PlannedTask(
                    task_id="t1",
                    title=agent.description[:80],
                    objective=message,
                    assignee_kind="agent",
                    assignee_name=agent.name,
                )
            )

    tasks = tasks[: settings.orchestration_max_tasks]
    plan_id = uuid.uuid4().hex
    return ExecutionPlan(
        plan_id=plan_id,
        tasks=tasks,
        rationale="Stub/heuristic plan based on message keywords and registry.",
        status="awaiting_approval",
    )


def _plan_from_payload(
    payload: dict[str, Any],
    registry: ToolRegistry,
    settings: HarnessSettings,
    message: str,
) -> ExecutionPlan:
    raw_tasks = payload.get("tasks") or []
    tasks: list[PlannedTask] = []
    for index, raw in enumerate(raw_tasks[: settings.orchestration_max_tasks]):
        kind = raw.get("assignee_kind", "agent")
        name = raw.get("assignee_name", "")
        if kind == "agent" and name not in registry.agents:
            continue
        if kind == "skill" and name not in registry.skills:
            continue
        if name == "synthesizer":
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
        return _stub_plan(message, registry, settings)

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


def _extract_name(message: str, pattern: str) -> str:
    match = re.search(pattern, message, re.I)
    return match.group(1).strip().rstrip(".") if match else ""


def _parse_json(content: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", content, flags=re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
