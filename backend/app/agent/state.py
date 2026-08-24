"""AgentState schema for the Phase 4 LangGraph tool-use loop."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from typing_extensions import TypedDict


def merge_lists(left: list[Any] | None, right: list[Any] | None) -> list[Any]:
    """Reducer that appends across loop iterations without losing history."""

    return (left or []) + (right or [])


class AgentState(TypedDict):
    """Shared working memory flowing through the agent graph.

    Lists use append-reducers because each loop iteration contributes new
    items; scalars are simply overwritten by whichever node runs last.
    """

    question: str
    iteration: int
    max_iterations: int
    decision: Literal["retrieve", "tool", "generate", "done"] | None
    decision_rationale: str | None
    retrieved_contexts: Annotated[list[str], merge_lists]
    source_ids: Annotated[list[str], merge_lists]
    tool_calls: Annotated[list[dict[str, Any]], merge_lists]
    intermediate_notes: Annotated[list[str], merge_lists]
    answer: str | None
