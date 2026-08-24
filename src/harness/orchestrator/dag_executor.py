from __future__ import annotations

import asyncio
import time
from typing import Any, Literal

from harness.orchestrator.plan_models import (
    ExecutionPlan,
    PlannedTask,
    TaskResult,
    build_failure_user_message,
)
from harness.settings import HarnessSettings
from harness.telemetry.bus import TelemetryBus
from harness.telemetry.events import PlanProgressEvent, TaskEvent

FailurePolicy = Literal["continue", "fail_fast", "retry_once"]
RunTaskFn = Any


class DagExecutor:
    """Execute plan tasks respecting DAG dependencies with optional parallelism."""

    def __init__(
        self,
        *,
        telemetry: TelemetryBus,
        settings: HarnessSettings,
        run_task: RunTaskFn,
    ) -> None:
        self._telemetry = telemetry
        self._settings = settings
        self._run_task = run_task

    async def execute(
        self,
        plan: ExecutionPlan,
        *,
        trace_id: str,
        thread_id: str,
        original_message: str,
        root_span_id: str | None,
        results_seed: dict[str, TaskResult] | None = None,
    ) -> tuple[dict[str, TaskResult], ExecutionPlan]:
        policy = _resolve_failure_policy(plan, self._settings)
        if self._settings.orchestration_parallel:
            return await self._execute_parallel(
                plan,
                trace_id=trace_id,
                thread_id=thread_id,
                original_message=original_message,
                root_span_id=root_span_id,
                failure_policy=policy,
                results_seed=results_seed or {},
            )
        return await self._execute_sequential(
            plan,
            trace_id=trace_id,
            thread_id=thread_id,
            original_message=original_message,
            root_span_id=root_span_id,
            failure_policy=policy,
            results_seed=results_seed or {},
        )

    async def _execute_sequential(
        self,
        plan: ExecutionPlan,
        *,
        trace_id: str,
        thread_id: str,
        original_message: str,
        root_span_id: str | None,
        failure_policy: FailurePolicy,
        results_seed: dict[str, TaskResult],
    ) -> tuple[dict[str, TaskResult], ExecutionPlan]:
        from harness.orchestrator.plan_models import topological_order

        plan_id = plan.plan_id
        results = dict(results_seed)
        abort = False

        for task in topological_order(plan.tasks):
            if abort:
                break
            if task.task_id in results:
                continue
            if not _dependencies_satisfied(task, results):
                results[task.task_id] = _blocked_result(task)
                self._emit_task(
                    trace_id,
                    task,
                    plan_id=plan_id,
                    action="failed",
                    display_message=results[task.task_id].user_message or "",
                    parent_span_id=root_span_id,
                    error="blocked_by_dependency",
                )
                continue

            result = await self._run_one(
                task,
                results=results,
                trace_id=trace_id,
                thread_id=thread_id,
                original_message=original_message,
                root_span_id=root_span_id,
                plan_id=plan_id,
                failure_policy=failure_policy,
            )
            results[task.task_id] = result
            self._emit_progress(trace_id, plan, results, running=[], parent_span_id=root_span_id)
            if result.status == "failure" and failure_policy == "fail_fast":
                abort = True

        return _finalize_plan(plan, results)

    async def _execute_parallel(
        self,
        plan: ExecutionPlan,
        *,
        trace_id: str,
        thread_id: str,
        original_message: str,
        root_span_id: str | None,
        failure_policy: FailurePolicy,
        results_seed: dict[str, TaskResult],
    ) -> tuple[dict[str, TaskResult], ExecutionPlan]:
        plan_id = plan.plan_id
        results = dict(results_seed)
        by_id = {task.task_id: task for task in plan.tasks}
        pending = {task.task_id for task in plan.tasks if task.task_id not in results}
        abort = False

        while pending and not abort:
            ready = [
                by_id[task_id]
                for task_id in sorted(pending)
                if _dependencies_satisfied(by_id[task_id], results)
            ]
            blocked = [
                by_id[task_id]
                for task_id in sorted(pending)
                if not _dependencies_satisfied(by_id[task_id], results)
                and not _has_pending_deps(by_id[task_id], pending)
            ]
            for task in blocked:
                pending.discard(task.task_id)
                results[task.task_id] = _blocked_result(task)
                self._emit_task(
                    trace_id,
                    task,
                    plan_id=plan_id,
                    action="failed",
                    display_message=results[task.task_id].user_message or "",
                    parent_span_id=root_span_id,
                    error="blocked_by_dependency",
                )

            if not ready:
                break

            batch = ready[: self._settings.orchestration_max_parallel]
            running_ids = [task.task_id for task in batch]
            self._emit_progress(
                trace_id,
                plan,
                results,
                running=running_ids,
                parent_span_id=root_span_id,
            )

            async def _run_batch_item(task: PlannedTask) -> tuple[str, TaskResult]:
                result = await self._run_one(
                    task,
                    results=results,
                    trace_id=trace_id,
                    thread_id=thread_id,
                    original_message=original_message,
                    root_span_id=root_span_id,
                    plan_id=plan_id,
                    failure_policy=failure_policy,
                )
                return task.task_id, result

            batch_results = await asyncio.gather(
                *[_run_batch_item(task) for task in batch],
                return_exceptions=True,
            )

            batch_failed = False
            for item in batch_results:
                if isinstance(item, Exception):
                    batch_failed = True
                    continue
                task_id, result = item
                pending.discard(task_id)
                results[task_id] = result
                if result.status == "failure":
                    batch_failed = True

            self._emit_progress(trace_id, plan, results, running=[], parent_span_id=root_span_id)
            if batch_failed and failure_policy == "fail_fast":
                abort = True
                for task_id in list(pending):
                    task = by_id[task_id]
                    results[task_id] = TaskResult(
                        task_id=task.task_id,
                        title=task.title,
                        assignee_kind=task.assignee_kind,
                        assignee_name=task.assignee_name,
                        status="skipped",
                        user_message=f'Skipped "{task.title}" because an earlier task failed.',
                    )
                    pending.discard(task_id)

        return _finalize_plan(plan, results)

    async def _run_one(
        self,
        task: PlannedTask,
        *,
        results: dict[str, TaskResult],
        trace_id: str,
        thread_id: str,
        original_message: str,
        root_span_id: str | None,
        plan_id: str,
        failure_policy: FailurePolicy,
    ) -> TaskResult:
        task.status = "running"
        started = time.perf_counter()
        self._emit_task(
            trace_id,
            task,
            plan_id=plan_id,
            action="started",
            display_message=f"Running: {task.title}",
            parent_span_id=root_span_id,
        )

        attempts = 2 if failure_policy == "retry_once" else 1
        last_error = ""
        for attempt in range(attempts):
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
                duration_ms = int((time.perf_counter() - started) * 1000)
                self._emit_task(
                    trace_id,
                    task,
                    plan_id=plan_id,
                    action="completed",
                    display_message=f"Completed: {task.title}",
                    parent_span_id=root_span_id,
                    duration_ms=duration_ms,
                )
                return result
            except Exception as exc:
                last_error = str(exc)
                if attempt + 1 < attempts:
                    continue

        user_message = build_failure_user_message(task, last_error)
        task.status = "failure"
        task.error = last_error
        task.user_message = user_message
        duration_ms = int((time.perf_counter() - started) * 1000)
        self._emit_task(
            trace_id,
            task,
            plan_id=plan_id,
            action="failed",
            display_message=user_message,
            parent_span_id=root_span_id,
            error=last_error,
            duration_ms=duration_ms,
        )
        return TaskResult(
            task_id=task.task_id,
            title=task.title,
            assignee_kind=task.assignee_kind,
            assignee_name=task.assignee_name,
            status="failure",
            error=last_error,
            user_message=user_message,
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
        duration_ms: int | None = None,
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
                action=action,  # type: ignore[arg-type]
                display_message=display_message,
                error=error,
                duration_ms=duration_ms,
            )
        )

    def _emit_progress(
        self,
        trace_id: str,
        plan: ExecutionPlan,
        results: dict[str, TaskResult],
        *,
        running: list[str],
        parent_span_id: str | None,
    ) -> None:
        completed = sum(1 for result in results.values() if result.status == "success")
        self._telemetry.emit(
            PlanProgressEvent(
                trace_id=trace_id,
                span_id=self._telemetry.new_span_id(),
                parent_span_id=parent_span_id,
                plan_id=plan.plan_id,
                completed=completed,
                total=len(plan.tasks),
                running=running,
                display_message=(
                    f"Plan progress: {completed}/{len(plan.tasks)} completed"
                    + (f", running: {', '.join(running)}" if running else "")
                ),
            )
        )


def _dependencies_satisfied(task: PlannedTask, results: dict[str, TaskResult]) -> bool:
    for dep in task.depends_on:
        dep_result = results.get(dep)
        if dep_result is None or dep_result.status != "success":
            return False
    return True


def _has_pending_deps(task: PlannedTask, pending: set[str]) -> bool:
    return any(dep in pending for dep in task.depends_on)


def _blocked_result(task: PlannedTask) -> TaskResult:
    task.status = "blocked"
    message = f'Skipped "{task.title}" because an upstream task failed.'
    task.user_message = message
    return TaskResult(
        task_id=task.task_id,
        title=task.title,
        assignee_kind=task.assignee_kind,
        assignee_name=task.assignee_name,
        status="blocked",
        user_message=message,
    )


def _finalize_plan(
    plan: ExecutionPlan,
    results: dict[str, TaskResult],
) -> tuple[dict[str, TaskResult], ExecutionPlan]:
    successes = [r for r in results.values() if r.status == "success"]
    failures = [r for r in results.values() if r.status in ("failure", "blocked", "skipped")]
    if failures and successes:
        plan.status = "partial"
    elif failures and not successes:
        plan.status = "failed"
    else:
        plan.status = "completed"
    return results, plan


def _resolve_failure_policy(plan: ExecutionPlan, settings: HarnessSettings) -> FailurePolicy:
    if plan.failure_policy:
        return plan.failure_policy
    if not settings.orchestration_continue_on_failure:
        return "fail_fast"
    return settings.orchestration_failure_policy  # type: ignore[return-value]
