"""Reconstruct a DeepEval-style LLMTestCase payload from a completed trace.

The adapter is the only place that knows how to read span attributes back into
evaluation inputs. It keeps the eval worker decoupled from the telemetry bridge:
the worker never touches OTel, it only consumes the SQLAlchemy rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.db.models import Span


@dataclass(frozen=True)
class ReconstructedCase:
    """Evaluation inputs lifted out of one completed trace."""

    input: str
    actual_output: str | None
    retrieval_context: list[str]
    document_ids: list[str]
    tools_called: list[str]
    llm_provider: str | None
    model: str | None
    duration_ms: float | None
    iterations: int | None = None
    tool_calls_detail: tuple[dict[str, Any], ...] = ()
    is_agent_trace: bool = False


def _attribute_value(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("[", "{", '"')):
            try:
                import json

                return json.loads(stripped)
            except (ValueError, TypeError):
                return value
    return value


def _first_span(spans: list[Span], kind: str) -> Span | None:
    return next((span for span in spans if span.kind == kind), None)


def _root_input(spans: list[Span]) -> str | None:
    root = min(
        (span for span in spans),
        key=lambda span: span.start_time,
        default=None,
    )
    if root is None:
        return None
    raw = root.attributes.get("gen_ai.input")
    parsed = _attribute_value(raw)
    if isinstance(parsed, dict):
        question = parsed.get("question") or parsed.get("input")
        if isinstance(question, str):
            return question
    if isinstance(parsed, list) and parsed and isinstance(parsed[0], str):
        return parsed[0]
    if isinstance(parsed, str):
        # LLM spans store a full prompt; prefer chain/retriever inputs.
        if root.kind == "llm" or root.name.startswith("llm."):
            for span in sorted(spans, key=lambda s: s.start_time):
                candidate = _attribute_value(span.attributes.get("gen_ai.input"))
                if isinstance(candidate, str) and "Context:" not in candidate:
                    return candidate
            return parsed.split("Question: ")[-1].split("\n\nContext:")[0]
        return parsed
    return str(raw) if raw is not None else None


def reconstruct_test_case(trace_id: str, spans: list[Span]) -> ReconstructedCase:
    """Build evaluation inputs from one trace's ordered span list"""

    retriever = _first_span(spans, "retriever")
    llm = _first_span(spans, "llm")
    root = _first_span(spans, "chain")
    tool_spans = [span for span in spans if span.kind == "tool"]

    retrieval_context: list[str] = []
    document_ids: list[str] = []
    if retriever is not None:
        docs = _attribute_value(retriever.attributes.get("gen_ai.output"))
        if isinstance(docs, list):
            retrieval_context = [str(doc) for doc in docs]
        ids = _attribute_value(retriever.attributes.get("gen_ai.retrieval.document_ids"))
        if isinstance(ids, list):
            document_ids = [str(doc_id) for doc_id in ids]

    tools_called = [
        str(_attribute_value(span.attributes.get("gen_ai.tool.name")) or span.name)
        for span in tool_spans
    ]
    tool_calls_detail = tuple(
        {
            "name": str(_attribute_value(span.attributes.get("gen_ai.tool.name")) or span.name),
            "input": str(_attribute_value(span.attributes.get("gen_ai.input")) or ""),
            "output": str(_attribute_value(span.attributes.get("gen_ai.output")) or ""),
        }
        for span in tool_spans
    )

    # Agent-loop traces carry "agent.loop" in their root name and iteration
    # count in the root's output payload.
    is_agent_trace = root is not None and "agent." in root.name
    iterations: int | None = None
    if root is not None:
        raw_iterations = _attribute_value(root.attributes.get("gen_ai.output"))
        if isinstance(raw_iterations, dict) and isinstance(raw_iterations.get("iterations"), int):
            iterations = raw_iterations["iterations"]
    if iterations is None and is_agent_trace:
        iterations = len(tool_spans) + (1 if llm is not None else 0)

    actual_output: str | None = None
    source = llm or root
    if source is not None:
        output = _attribute_value(source.attributes.get("gen_ai.output"))
        if isinstance(output, dict):
            answer = output.get("answer")
            actual_output = answer if isinstance(answer, str) else None
        elif isinstance(output, list):
            actual_output = "\n".join(str(item) for item in output)
        elif isinstance(output, str):
            actual_output = output

    return ReconstructedCase(
        input=_root_input(spans) or "",
        actual_output=normalise(actual_output),
        retrieval_context=retrieval_context,
        document_ids=document_ids,
        tools_called=tools_called,
        llm_provider=source.attributes.get("gen_ai.system") if source else None,
        model=source.attributes.get("gen_ai.request.model") if source else None,
        duration_ms=root.duration_ms if root is not None else None,
        iterations=iterations,
        tool_calls_detail=tool_calls_detail,
        is_agent_trace=is_agent_trace,
    )


def normalise(value: str | None) -> str | None:
    """Collapse whitespace-only outputs to None so judges skip cleanly."""

    if value is None:
        return None
    collapsed = value.strip()
    return collapsed or None
