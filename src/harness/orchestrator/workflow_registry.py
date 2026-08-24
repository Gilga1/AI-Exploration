from __future__ import annotations

import json
import re
import uuid
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage

from harness.config.models import ConfigPlane
from harness.llm.factory import build_chat_model
from harness.orchestrator.plan_models import ExecutionPlan
from harness.orchestrator.workflow_models import WorkflowTemplate
from harness.settings import HarnessSettings


PlannerMode = Literal["auto", "llm", "template", "hybrid"]


class WorkflowRegistry:
    def __init__(
        self,
        templates: list[WorkflowTemplate],
        *,
        settings: HarnessSettings,
        config: ConfigPlane | None = None,
    ) -> None:
        self._templates = sorted(templates, key=lambda t: t.priority, reverse=True)
        self._settings = settings
        self._config = config

    @property
    def templates(self) -> list[WorkflowTemplate]:
        return list(self._templates)

    def list_summaries(self) -> list[dict]:
        return [
            {
                "name": template.name,
                "description": template.description,
                "match_tags": template.match_tags,
                "task_count": len(template.tasks),
                "variables": list(template.variables.keys()),
                "priority": template.priority,
            }
            for template in self._templates
        ]

    def try_build_plan(
        self,
        message: str,
        *,
        mode: PlannerMode,
    ) -> ExecutionPlan | None:
        if mode == "llm":
            return None

        template = self._match_template(message)
        if template is None:
            return None

        values = extract_variables(message, template)
        tasks = template.to_planned_tasks(values)

        if mode == "hybrid":
            tasks = self._hybrid_enrich_objectives(message, template, tasks)

        return ExecutionPlan(
            plan_id=uuid.uuid4().hex,
            tasks=tasks[: self._settings.orchestration_max_tasks],
            rationale=f"Workflow template {template.name!r}: {template.description}",
            status="awaiting_approval",
            failure_policy=template.failure_policy,
        )

    def _match_template(self, message: str) -> WorkflowTemplate | None:
        if not self._templates:
            return None

        lowered = message.lower()
        best: WorkflowTemplate | None = None
        best_score = 0.0

        for template in self._templates:
            if template.match_patterns:
                if not any(re.search(pattern, message, re.I) for pattern in template.match_patterns):
                    continue

            if not template.match_tags:
                continue

            hits = sum(1 for tag in template.match_tags if tag.lower() in lowered)
            score = hits / len(template.match_tags)
            if score > best_score:
                best_score = score
                best = template

        threshold = self._settings.orchestration_workflow_match_threshold
        if best is None or best_score < threshold:
            return None
        return best

    def _hybrid_enrich_objectives(self, message: str, template: WorkflowTemplate, tasks):
        if self._settings.force_stub_models:
            return tasks

        model_cfg = None
        if self._config is not None:
            model_cfg = next(
                (m for m in self._config.models.models if m.name == self._settings.orchestration_planner_model),
                None,
            )
        if model_cfg is None or model_cfg.provider == "stub":
            return tasks

        model = build_chat_model(model_cfg)
        task_payload = [
            {"task_id": task.task_id, "title": task.title, "objective": task.objective}
            for task in tasks
        ]
        prompt = (
            "Refine task objectives for a workflow plan. Keep the same task_id values.\n"
            "Respond with JSON only: {\"tasks\": [{\"task_id\": \"...\", \"objective\": \"...\"}]}\n\n"
            f"Workflow: {template.name}\n"
            f"User request: {message}\n"
            f"Tasks: {json.dumps(task_payload)}"
        )
        response = model.invoke(
            [
                SystemMessage(content="You refine workflow task objectives for a harness planner."),
                HumanMessage(content=prompt),
            ]
        )
        content = response.content if isinstance(response.content, str) else str(response.content)
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            return tasks
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return tasks

        objective_by_id = {
            item.get("task_id"): item.get("objective")
            for item in parsed.get("tasks", [])
            if item.get("task_id")
        }
        for task in tasks:
            if task.task_id in objective_by_id and objective_by_id[task.task_id]:
                task.objective = str(objective_by_id[task.task_id])
        return tasks


def extract_variables(message: str, template: WorkflowTemplate) -> dict[str, str]:
    values: dict[str, str] = {}
    for name, spec in template.variables.items():
        value = ""
        if spec.extract:
            match = re.search(spec.extract, message, re.I)
            if match:
                value = match.group(1).strip().rstrip(".")
        if not value:
            value = spec.default or name.replace("_", " ")
        values[name] = value
    return values
