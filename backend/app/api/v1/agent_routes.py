"""Phase 4 agent endpoints backed by the LangGraph tool-use loop."""

from __future__ import annotations

import threading
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, Field

from app.core.auth import require_api_key
from app.core.config import get_settings
from app.telemetry.callback_bridge import LangChainOTelCallbackHandler

router = APIRouter(
    prefix="/agent",
    tags=["agent"],
    dependencies=[Depends(require_api_key)],
)


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
_agent_nodes = None
_agent_lock = threading.Lock()


def get_agent_graph():
    """Lazily compile the LangGraph app once per process."""

    global _agent_app, _agent_nodes
    if _agent_app is not None and _agent_nodes is not None:
        return _agent_app, _agent_nodes
    with _agent_lock:
        if _agent_app is None or _agent_nodes is None:
            from app.agent.graph import build_agent_graph

            _agent_app, _agent_nodes = build_agent_graph(get_settings())
        return _agent_app, _agent_nodes


@router.get("/tools")
def list_tools() -> list[dict[str, str]]:
    from app.agent.tools.registry import REGISTRY

    return [
        {"name": tool.name, "description": tool.description} for tool in REGISTRY.values()
    ]


@router.post("/invoke")
def invoke_agent(request: AgentInvokeRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    from app.evaluation.runners.realtime_worker import score_trace, should_sample

    settings = get_settings()
    if request.question and len(request.question) > settings.agent_question_max_length:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422,
            detail=f"question exceeds maximum length of {settings.agent_question_max_length}",
        )
    max_iterations = max(request.max_iterations, settings.agent_min_iterations)

    callback_handler = LangChainOTelCallbackHandler()
    app_graph, nodes = get_agent_graph()
    nodes.callback_handler = callback_handler

    initial_state = {
        "question": request.question,
        "iteration": 0,
        "max_iterations": max_iterations,
        "decision": None,
        "decision_rationale": None,
        "retrieved_contexts": [],
        "source_ids": [],
        "tool_calls": [],
        "intermediate_notes": [],
        "answer": None,
        "root_run_id": None,
        "trace_id": None,
    }
    final_state = app_graph.invoke(initial_state)

    trace_id = final_state.get("trace_id") or callback_handler.last_completed_trace_id()

    if trace_id and should_sample(trace_id, rate=settings.eval_sampling_rate):
        background_tasks.add_task(score_trace, trace_id)

    return {
        "answer": final_state.get("answer") or "",
        "iterations": final_state.get("iteration", 0),
        "tool_calls": final_state.get("tool_calls", []),
        "source_ids": list(dict.fromkeys(final_state.get("source_ids", []))),
        "trace_id": trace_id,
    }
