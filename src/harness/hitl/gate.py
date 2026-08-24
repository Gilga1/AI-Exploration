from __future__ import annotations

from typing import Any

from harness.core.context import RunContext
from harness.core.request import IncomingRequest
from harness.hitl.store import ApprovalStore, PendingApproval
from harness.telemetry.instrumentation import invoke_tool_with_telemetry


class ApprovalRequiredError(Exception):
    def __init__(self, tool_name: str, interrupt_payload: dict[str, Any], task_id: str) -> None:
        self.tool_name = tool_name
        self.interrupt_payload = interrupt_payload
        self.task_id = task_id
        super().__init__(f"Tool {tool_name!r} requires human approval")


async def invoke_tool_with_approval(
    tool_name: str,
    tool: Any,
    args: Any,
    *,
    context: RunContext,
    request: IncomingRequest | None = None,
    approval_store: ApprovalStore | None = None,
    task_id: str | None = None,
    rationale: str = "",
) -> Any:
    requires_approval = tool.spec.requires_approval
    pre_approved = (request.tool_approvals.get(tool_name) if request else None)

    if requires_approval and pre_approved is None:
        interrupt_payload = {
            "tool_name": tool_name,
            "args": args.model_dump() if hasattr(args, "model_dump") else dict(args),
            "rationale": rationale,
            "allowed_decisions": ["approve", "edit", "reject"],
        }
        if approval_store and task_id:
            approval_store.save(
                PendingApproval(
                    thread_id=context.thread_id or context.trace_id,
                    task_id=task_id,
                    agent_name="skill",
                    trace_id=context.trace_id,
                    interrupt_payload=interrupt_payload,
                )
            )
        raise ApprovalRequiredError(tool_name, interrupt_payload, task_id or context.trace_id)

    return await invoke_tool_with_telemetry(
        tool_name, tool, args, context=context, rationale=rationale
    )
