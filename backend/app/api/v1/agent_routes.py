"""Phase 4 agent endpoints backed by the LangGraph tool-use loop."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from app.core.config import get_settings

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentInvokeRequest(BaseModel):
    question: str = Field(min_length=1)
    max_iterations: int = Field(default=5, ge=1, le=10)


class ToolCallSummary(BaseModel):
    name: str
    input: str
    output: str
    iteration: int


class AgentInvokeResponse(BaseModel):
    answer: str
    iterations: int
    tool_calls: list[ToolCallSummary]
    source_ids: list[str]
    trace_id: str | None = None


_agent_app = None


def get_agent_app():
    """Lazily compile the LangGraph app once per process."""

    global _agent_app
    if _agent_app is None:
        from app.agent.graph import build_agent_graph

        _agent_app, _ = build_agent_graph(get_settings())
    return _agent_app


@router.get("/tools")
def list_tools() -> list[dict[str, str]]:
    """Expose the tool registry for the dashboard/UI."""

    from app.agent.tools.registry import REGISTRY

    return [
        {"name": t.name, "description": t.description} for t in REGISTRY.values()
    ]


@router.post("/invoke")
def invoke_agent(request: AgentInvokeRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Run one full agent loop; tracing and async eval are side-effect free."""

    from sqlalchemy import select

    from app.core.config import get_settings
    from app.db.models import EvalResult, Trace
    from app.db.session import session_scope
    from app.evaluation.runners.realtime_worker import score_trace, should_sample

    app_graph = get_agent_app()
    initial_state = {
        "question": request.question,
        "iteration": 0,
        "max_iterations": request.max_iterations,
        "decision": None,
        "decision_rationale": None,
        "retrieved_contexts": [],
        "source_ids": [],
        "tool_calls": [],
        "intermediate_notes": [],
        "answer": None,
    }
    final_state = app_graph.invoke(initial_state)

    # The root span closed last, so the newest trace is this invocation's.
    with session_scope() as session:
        trace_id = session.scalars(
            select(Trace.id).order_by(Trace.start_time.desc()).limit(1)
        ).first()

    settings = get_settings()
    if trace_id and should_sample(trace_id, rate=settings.eval_sampling_rate):
        background_tasks.add_task(score_trace, trace_id)

    return {
        "answer": final_state.get("answer") or "",
        "iterations": final_state.get("iteration", 0),
        "tool_calls": final_state.get("tool_calls", []),
        "source_ids": list(dict.fromkeys(final_state.get("source_ids", []))),
        "trace_id": trace_id,
    }
