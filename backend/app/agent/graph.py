"""The Phase 4 LangGraph StateGraph: Planner → Decide → Retrieve/Tool → Generate.

The routing policy (which tool to call, when to retrieve, when to generate) is
a deterministic guardrail; every answer and judge score comes from the LLM.
Run-scoped trace identity lives in AgentState, so concurrent invocations each
get their own OTel root span and trace id.
"""

from __future__ import annotations

import re
from typing import Any, Literal
from uuid import UUID

from app.agent.state import AgentState
from app.agent.tools.registry import REGISTRY
from app.core.config import Settings, get_settings
from app.rag.chains import get_chat_model
from app.rag.corpus import CORPUS
from app.rag.embeddings import get_embedding_model
from app.rag.retriever import RagRetriever
from app.rag.vectorstore import InMemoryVectorStore
from app.telemetry.callback_bridge import LangChainOTelCallbackHandler

try:
    from langgraph.graph import END, StateGraph
except ImportError:  # pragma: no cover - keeps the module importable pre-install
    StateGraph = None  # type: ignore[assignment,misc]
    END = "__end__"  # type: ignore[assignment]

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {
    "a", "an", "and", "are", "as", "at", "be", "by", "does", "do", "for", "from",
    "how", "in", "is", "it", "of", "on", "or", "the", "to", "what", "when",
    "where", "which", "with", "many", "much", "can", "i", "me", "my",
}
_ARITHMETIC = re.compile(r"^[\d\s+\-*/().]+$")


def _terms(text: str) -> set[str]:
    return {t for t in _WORD.findall(text.lower()) if t not in _STOP}


class AgentNodes:
    """Node callables sharing one retriever, chat model, and callback bridge."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        vector_store = InMemoryVectorStore.from_documents(
            CORPUS, get_embedding_model(self.settings)
        )
        self.retriever = RagRetriever(vector_store, self.settings.rag_retrieval_k)
        self.chat_model = get_chat_model(self.settings)
        self.callback_handler = LangChainOTelCallbackHandler()

    # ---------------------------------------------------------------- helpers
    def _open_root_span(self, state: AgentState) -> dict[str, Any] | None:
        """Open this invocation's root chain span exactly once, into state."""

        if state.get("root_run_id") is not None:
            return None
        run_id = self.callback_handler.new_run_id()
        self.callback_handler.on_chain_start(
            {"name": "agent.loop"},
            {"question": state["question"]},
            run_id=run_id,
        )
        trace_id = self.callback_handler.last_trace_id(str(run_id))
        return {"root_run_id": str(run_id), "trace_id": trace_id}

    # ------------------------------------------------------------------ nodes
    def planner(self, state: AgentState) -> dict[str, Any]:
        """Decide the next action from working memory (deterministic policy)."""

        updates: dict[str, Any] = {}
        root_update = self._open_root_span(state)
        if root_update:
            updates.update(root_update)

        iteration = state["iteration"] + 1
        question_lower = state["question"].lower()
        tools_used = {call["name"] for call in state["tool_calls"]}

        # 1) A calculation request goes to the calculator tool once, then to
        #    the generator so the loop terminates instead of thrashing.
        def _finish(**decision_updates: Any) -> dict[str, Any]:
            """Merge the root-span bookkeeping into every planner return."""

            return {**updates, **decision_updates}

        if _ARITHMETIC.match(state["question"].strip()) or "calculate" in question_lower:
            if "calculator" not in tools_used:
                return _finish(
                    iteration=iteration,
                    decision="tool",
                    decision_rationale="question requests arithmetic; routing to calculator tool",
                )
            return _finish(
                iteration=iteration,
                decision="generate",
                decision_rationale="calculator result available; generating final answer",
            )

        # 2) Explicit lookup phrasing goes straight to the document tool once.
        if any(kw in question_lower for kw in ("look up", "lookup", "find the doc")):
            if "document_lookup" not in tools_used:
                return _finish(
                    iteration=iteration,
                    decision="tool",
                    decision_rationale="explicit document lookup request; using document_lookup tool",
                )

        # 3) Default path: retrieve once if we have no context yet.
        if not state["retrieved_contexts"]:
            return _finish(
                iteration=iteration,
                decision="retrieve",
                decision_rationale="no context gathered yet; retrieving top documents",
            )

        # 4) Have context — generate. If we already generated and iterations
        #    remain but nothing new was learned, stop instead of thrashing.
        if state["answer"] is not None or state["iteration"] >= state["max_iterations"]:
            return _finish(iteration=iteration, decision="done",
                           decision_rationale="answer already produced or budget exhausted")

        return _finish(
            iteration=iteration,
            decision="generate",
            decision_rationale=f"context available after {state['iteration']} step(s); generating answer",
        )

    def retrieve_node(self, state: AgentState) -> dict[str, Any]:
        run_id = self.callback_handler.new_run_id()
        parent_run_id = UUID(state["root_run_id"]) if state.get("root_run_id") else None
        self.callback_handler.on_retriever_start(
            {"name": "AgentRetriever"}, state["question"], run_id=run_id,
            parent_run_id=parent_run_id,
        )
        documents = self.retriever.invoke(state["question"])
        self.callback_handler.on_retriever_end(documents, run_id=run_id)
        return {
            "retrieved_contexts": [doc.page_content for doc in documents],
            "source_ids": [doc.metadata.get("id", "unknown") for doc in documents],
            "intermediate_notes": [f"retrieved {len(documents)} documents"],
        }

    def tool_executor(self, state: AgentState) -> dict[str, Any]:
        parent_run_id = UUID(state["root_run_id"]) if state.get("root_run_id") else None
        question_lower = state["question"].lower()
        if _ARITHMETIC.match(state["question"].strip()) or "calculate" in question_lower:
            tool_name = "calculator"
            tool_input = state["question"]
        else:
            tool_name = "document_lookup"
            tool_input = state["question"]

        tool = REGISTRY[tool_name]
        run_id = self.callback_handler.new_run_id()
        self.callback_handler.on_tool_start(
            {"name": tool.name}, tool_input, run_id=run_id,
            parent_run_id=parent_run_id,
        )
        try:
            result = tool.func(tool_input)
        except Exception as exc:
            self.callback_handler.on_tool_error(exc, run_id=run_id)
            raise
        self.callback_handler.on_tool_end(result, run_id=run_id)
        return {
            "tool_calls": [{
                "name": tool.name,
                "input": tool_input,
                "output": result,
                "iteration": state["iteration"],
            }],
            "intermediate_notes": [f"{tool.name}: {result[:200]}"],
        }

    def generator(self, state: AgentState) -> dict[str, Any]:
        root_run_id = UUID(state["root_run_id"]) if state.get("root_run_id") else None
        contexts = list(state["retrieved_contexts"])
        for call in state["tool_calls"]:
            if call["name"] == "document_lookup":
                contexts.append(call["output"])

        # Pure-arithmetic runs have no retrieval context: the calculator's
        # result IS the answer — don't force it through an extractive stub.
        calculator_outputs = [
            call["output"] for call in state["tool_calls"] if call["name"] == "calculator"
        ]
        if not contexts and calculator_outputs:
            answer = f"The result is {calculator_outputs[-1]}."
            self.callback_handler.on_chain_end(
                {"answer": answer, "iterations": state["iteration"],
                 "tool_calls": [c["name"] for c in state["tool_calls"]]},
                run_id=root_run_id,
            )
            return {"answer": answer}

        joined = "\n\n".join(
            f"[Document {i}]\n{c}" for i, c in enumerate(contexts, start=1)
        ) or "(no context retrieved)"
        prompt = (
            "Answer the question using only the supplied context.\n"
            f"Question: {state['question']}\n\nContext:\n{joined}"
        )

        run_id = self.callback_handler.new_run_id()
        self.callback_handler.on_llm_start(
            {"name": type(self.chat_model).__name__, "provider": self.chat_model.provider_name},
            [prompt], run_id=run_id,
            parent_run_id=root_run_id,
        )
        try:
            response = self.chat_model.invoke(prompt)
        except Exception as exc:
            self.callback_handler.on_llm_error(exc, run_id=run_id)
            raise
        self.callback_handler.on_llm_end(response, run_id=run_id)

        content = getattr(response, "content", response)
        answer = str(content).strip() if not isinstance(content, list) else "".join(
            item.get("text", "") if isinstance(item, dict) else str(item) for item in content
        ).strip()

        self.callback_handler.on_chain_end(
            {"answer": answer, "iterations": state["iteration"],
             "tool_calls": [c["name"] for c in state["tool_calls"]]},
            run_id=root_run_id,
        )
        return {"answer": answer}

    # ------------------------------------------------------------- dispatcher
    def decide(self, state: AgentState) -> Literal["retrieve", "tool", "generate", "done"]:
        decision = state.get("decision")
        if state["iteration"] > state["max_iterations"]:
            return "done"
        return decision if decision in ("retrieve", "tool", "generate") else "done"

    def route_after_generate(self, state: AgentState) -> Literal["decide", "__end__"]:
        """After one generation pass the loop ends (single-answer contract)."""

        return END if state.get("answer") is not None else "decide"


def build_agent_graph(settings: Settings | None = None):
    """Compile the Planner → Decide → Retrieve/Tool → Generate LangGraph app."""

    if StateGraph is None:
        raise RuntimeError("langgraph is required for the agent loop (pip install langgraph)")

    nodes = AgentNodes(settings)
    graph = StateGraph(AgentState)

    graph.add_node("planner", nodes.planner)
    graph.add_node("retrieve", nodes.retrieve_node)
    graph.add_node("tool_executor", nodes.tool_executor)
    graph.add_node("generator", nodes.generator)

    graph.set_entry_point("planner")
    graph.add_node("decide", lambda state: {})  # router pseudo-node
    graph.add_conditional_edges(
        "planner",
        nodes.decide,
        {
            "retrieve": "retrieve",
            "tool": "tool_executor",
            "generate": "generator",
            "done": END,
        },
    )
    # Retrieved context or tool output feeds back into the planner for the
    # next decision — this edge is what makes it a loop rather than a chain.
    graph.add_edge("retrieve", "planner")
    graph.add_edge("tool_executor", "planner")
    graph.add_conditional_edges(
        "generator",
        nodes.route_after_generate,
        {"decide": "planner", END: END},
    )

    return graph.compile(), nodes
