from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from harness.orchestrator.plan_models import FailurePolicy, PlannedTask


class WorkflowVariableSpec(BaseModel):
    extract: str | None = Field(
        default=None,
        description="Regex pattern with one capture group for slot filling",
    )
    default: str = ""


class WorkflowTaskTemplate(BaseModel):
    task_id: str
    title: str
    objective: str = ""
    assignee_kind: Literal["agent", "skill"] | None = None
    assignee_name: str | None = None
    assignee: dict[str, str] | None = None
    depends_on: list[str] = Field(default_factory=list)
    inputs_from: dict[str, str] = Field(default_factory=dict)
    skill_input_template: dict[str, Any] | None = None
    fallback_hint: str | None = None
    max_steps: int | None = None
    timeout_s: int | None = None

    def resolved_assignee(self) -> tuple[Literal["agent", "skill", "profile"], str]:
        if self.assignee:
            kind = self.assignee.get("kind", "agent")
            name = self.assignee.get("name", "")
            return kind, name  # type: ignore[return-value]
        if self.assignee_kind and self.assignee_name:
            return self.assignee_kind, self.assignee_name
        raise ValueError(f"Workflow task {self.task_id!r} missing assignee")


class WorkflowTemplate(BaseModel):
    name: str
    description: str
    match_tags: list[str] = Field(default_factory=list)
    match_patterns: list[str] = Field(default_factory=list)
    variables: dict[str, WorkflowVariableSpec] = Field(default_factory=dict)
    tasks: list[WorkflowTaskTemplate]
    failure_policy: FailurePolicy | None = None
    priority: int = 0

    def to_planned_tasks(self, values: dict[str, str]) -> list[PlannedTask]:
        planned: list[PlannedTask] = []
        for task in self.tasks:
            kind, name = task.resolved_assignee()
            planned.append(
                PlannedTask(
                    task_id=_substitute(task.task_id, values),
                    title=_substitute(task.title, values),
                    objective=_substitute(task.objective, values),
                    assignee_kind=kind,
                    assignee_name=name,
                    depends_on=[_substitute(dep, values) for dep in task.depends_on],
                    inputs_from={
                        key: _substitute(value, values) for key, value in task.inputs_from.items()
                    },
                    skill_input_template=_substitute_tree(task.skill_input_template, values),
                    fallback_hint=_substitute(task.fallback_hint or "", values) or None,
                    max_steps=task.max_steps,
                    timeout_s=task.timeout_s,
                )
            )
        return planned


def _substitute(text: str, values: dict[str, str]) -> str:
    result = text
    for key, value in values.items():
        result = result.replace(f"{{{{{key}}}}}", value)
    return result


def _substitute_tree(value: Any, values: dict[str, str]) -> Any:
    if isinstance(value, str):
        return _substitute(value, values)
    if isinstance(value, dict):
        return {k: _substitute_tree(v, values) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_tree(item, values) for item in value]
    return value
