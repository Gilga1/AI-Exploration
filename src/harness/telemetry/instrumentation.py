from __future__ import annotations

import time
from typing import Any

from harness.core.context import RunContext
from harness.telemetry.bus import TelemetryBus
from harness.telemetry.events import ToolInvocationEvent


async def invoke_tool_with_telemetry(
    tool_name: str,
    tool: Any,
    args: Any,
    *,
    context: RunContext,
    rationale: str = "",
) -> Any:
    telemetry: TelemetryBus | None = context.metadata.get("telemetry")
    parent_span = context.metadata.get("parent_span_id")
    if telemetry is None:
        return await tool.run(args, context=context)

    capture = telemetry.should_capture_content()
    span_id = telemetry.new_span_id()
    start = time.perf_counter()
    input_payload = args.model_dump() if hasattr(args, "model_dump") else dict(args)

    with telemetry.span(
        f"execute_tool:{tool_name}",
        trace_id=context.trace_id,
        span_id=span_id,
        otel_attributes={
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": tool_name,
        },
    ):
        error: str | None = None
        output_payload: dict[str, Any] | None = None
        try:
            result = await tool.run(args, context=context)
            if hasattr(result, "model_dump"):
                output_payload = result.model_dump()
                if not capture and "pdf_bytes" in output_payload:
                    output_payload = {**output_payload, "pdf_bytes": "<redacted>"}
            else:
                output_payload = {"result": str(result)}
            return result
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            latency_ms = int((time.perf_counter() - start) * 1000)
            telemetry.emit(
                ToolInvocationEvent(
                    trace_id=context.trace_id,
                    span_id=span_id,
                    parent_span_id=parent_span,
                    tool_name=tool_name,
                    input=input_payload if capture else {"redacted": True},
                    output=output_payload,
                    rationale=rationale,
                    error=error,
                    latency_ms=latency_ms,
                    capture_content=capture,
                )
            )
