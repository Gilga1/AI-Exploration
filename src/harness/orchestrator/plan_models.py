from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


TaskStatus = Literal["pending", "running", "success", "failure", "skipped", "blocked"]
PlanStatus = Literal[
    "draft",
    "awaiting_approval",
    "approved",
    "executing",
    "completed",
    "partial",
    "failed",
]
AssigneeKind = Literal["agent", "skill"]


class PlannedTask(BaseModel):
    task_id: str
    title: str
    objective: str = ""
    assignee_kind: AssigneeKind
    assignee_name: str
    depends_on: list[str] = Field(default_factory=list)
    inputs_from: dict[str, str] = Field(default_factory=dict)
    skill_input_template: dict[str, Any] | None = None
    status: TaskStatus = "pending"
    fallback_hint: str | None = None
    error: str | None = None
    user_message: str | None = None


class ExecutionPlan(BaseModel):
    plan_id: str
    tasks: list[PlannedTask]
    rationale: str = ""
    status: PlanStatus = "draft"


class TaskResult(BaseModel):
    task_id: str
    title: str
    assignee_kind: AssigneeKind
    assignee_name: str
    status: Literal["success", "failure", "skipped", "blocked"]
    output: dict[str, Any] | None = None
    error: str | None = None
    user_message: str | None = None
    artifacts: list[dict[str, Any]] = Field(default_factory=list)


def topological_order(tasks: list[PlannedTask]) -> list[PlannedTask]:
    by_id = {task.task_id: task for task in tasks}
    ordered: list[PlannedTask] = []
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visited:
            return
        task = by_id.get(task_id)
        if task is None:
            return
        for dep in task.depends_on:
            visit(dep)
        visited.add(task_id)
        ordered.append(task)

    for task in tasks:
        visit(task.task_id)
    return ordered


def build_failure_user_message(task: PlannedTask, error: str) -> str:
    hint = task.fallback_hint or task.title
    return (
        f'Could not complete "{task.title}". {error} '
        f"You might still want to check {hint} separately."
    )
