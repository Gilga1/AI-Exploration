from __future__ import annotations

import time
from typing import Any, AsyncIterator, TypedDict

from langgraph.graph import END, StateGraph

from app.audit.store import AuditStore
from app.graph.discovery import GraphDiscovery
from app.graph.neo4j_client import get_neo4j_client
from app.graph.resolver import GraphResolver
from app.llm.client import LLMClient
from app.sql_gen.assembler import SQLAssembler
from app.warehouse.snowflake_client import SnowflakeClient


class PipelineState(TypedDict, total=False):
    question: str
    metric_id: str | None
    intent: dict[str, Any]
    candidates: list[dict[str, Any]]
    selection: dict[str, Any]
    subgraph: Any
    assembled: Any
    rows: list[dict[str, Any]]
    columns: list[str]
    events: list[dict[str, Any]]


class QueryPipeline:
    def __init__(self) -> None:
        self.client = get_neo4j_client()
        self.discovery = GraphDiscovery(self.client)
        self.resolver = GraphResolver(self.client)
        self.assembler = SQLAssembler()
        self.warehouse = SnowflakeClient()
        self.llm = LLMClient()
        self.audit = AuditStore()

    async def run(self, question: str, metric_id: str | None = None) -> AsyncIterator[dict[str, Any]]:
        stages = ["decompose", "discover", "reason", "resolve", "assemble", "execute", "answer"]
        context: dict[str, Any] = {"question": question}

        for stage in stages:
            start = time.perf_counter()
            yield {"event": "stage_start", "stage": stage}
            try:
                if stage == "decompose":
                    context["intent"] = self.llm.decompose(question)
                elif stage == "discover":
                    terms = context["intent"].get("search_terms", [question])
                    candidates = []
                    for term in terms[:3]:
                        candidates.extend(self.discovery.search(term, limit=5))
                    context["candidates"] = self._dedupe_candidates(candidates)
                elif stage == "reason":
                    context["selection"] = self.llm.reason(
                        question, context["candidates"], metric_id=metric_id
                    )
                    sel = context["selection"]
                    yield {
                        "event": "selection",
                        "metric_id": sel.get("metric_id"),
                        "confidence": sel.get("confidence"),
                        "rationale": sel.get("rationale"),
                        "needs_confirmation": (sel.get("confidence") or 1.0) < 0.7,
                    }
                elif stage == "resolve":
                    selected_id = context["selection"]["metric_id"]
                    subgraph = self.resolver.resolve_metric(selected_id)
                    if not subgraph:
                        raise ValueError(f"Could not resolve metric {selected_id!r}")
                    context["subgraph"] = subgraph
                elif stage == "assemble":
                    subgraph = context["subgraph"]
                    selection = context["selection"]
                    assembled = self.assembler.assemble(
                        subgraph,
                        parameters=selection.get("parameters", {}),
                        dimensions=selection.get("dimensions"),
                    )
                    context["assembled"] = assembled
                    yield {
                        "event": "sql_preview",
                        "metric_id": assembled.metric_id,
                        "sql": assembled.sql,
                        "graph_version_id": assembled.graph_version_id,
                        "sql_hash": assembled.sql_hash,
                        "node_ids": assembled.node_ids,
                        "edge_ids": assembled.edge_ids,
                    }
                elif stage == "execute":
                    assembled = context["assembled"]
                    try:
                        rows, columns = self.warehouse.execute(assembled.sql)
                    except RuntimeError as exc:
                        if not self.warehouse.is_configured:
                            rows, columns = [], []
                            yield {"event": "warning", "stage": "execute", "message": str(exc)}
                        else:
                            raise
                    context["rows"] = rows
                    context["columns"] = columns
                    yield {"event": "data_rows", "rows": rows, "columns": columns}
                elif stage == "answer":
                    assembled = context.get("assembled")
                    answer = self.llm.answer(
                        question=question,
                        metric_id=context["selection"]["metric_id"],
                        rows=context.get("rows", []),
                        columns=context.get("columns", []),
                        sql=getattr(assembled, "sql", None),
                    )
                    yield {"event": "token", "stage": "answer", "delta": answer}
            except Exception as exc:
                yield {"event": "error", "stage": stage, "error": str(exc)}
                return
            elapsed = time.perf_counter() - start
            yield {"event": "stage_complete", "stage": stage, "elapsed_sec": round(elapsed, 3)}

        selection = context.get("selection", {})
        assembled = context.get("assembled")
        self.audit.log_query(
            user_id=None,
            question=question,
            metric_id=selection.get("metric_id"),
            graph_version_id=getattr(assembled, "graph_version_id", None),
            sql_hash=getattr(assembled, "sql_hash", None),
            sql_text=getattr(assembled, "sql", None),
            row_count=len(context.get("rows", [])),
            node_ids=getattr(assembled, "node_ids", None),
            edge_ids=getattr(assembled, "edge_ids", None),
            selection_confidence=selection.get("confidence"),
            extra={"rationale": selection.get("rationale")},
        )

        yield {
            "event": "done",
            "result": {
                "metric_id": context.get("selection", {}).get("metric_id"),
                "sql_hash": getattr(context.get("assembled"), "sql_hash", None),
                "row_count": len(context.get("rows", [])),
                "llm_enabled": self.llm.enabled,
            },
        }

    def _dedupe_candidates(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for c in candidates:
            cid = c.get("id", "")
            if cid and cid not in seen:
                seen.add(cid)
                deduped.append(c)
        return deduped


def build_langgraph_pipeline() -> Any:
    """LangGraph state machine mirroring the streaming pipeline stages."""
    pipeline = QueryPipeline()

    def decompose_node(state: PipelineState) -> PipelineState:
        state["intent"] = pipeline.llm.decompose(state["question"])
        return state

    def discover_node(state: PipelineState) -> PipelineState:
        terms = state.get("intent", {}).get("search_terms", [state["question"]])
        candidates: list[dict[str, Any]] = []
        for term in terms[:3]:
            candidates.extend(pipeline.discovery.search(term, limit=5))
        state["candidates"] = pipeline._dedupe_candidates(candidates)
        return state

    def reason_node(state: PipelineState) -> PipelineState:
        state["selection"] = pipeline.llm.reason(
            state["question"], state.get("candidates", []), metric_id=state.get("metric_id")
        )
        return state

    def resolve_node(state: PipelineState) -> PipelineState:
        selected_id = state["selection"]["metric_id"]
        subgraph = pipeline.resolver.resolve_metric(selected_id)
        if not subgraph:
            raise ValueError(f"Could not resolve metric {selected_id!r}")
        state["subgraph"] = subgraph
        return state

    def assemble_node(state: PipelineState) -> PipelineState:
        selection = state["selection"]
        state["assembled"] = pipeline.assembler.assemble(
            state["subgraph"],
            parameters=selection.get("parameters", {}),
            dimensions=selection.get("dimensions"),
        )
        return state

    def execute_node(state: PipelineState) -> PipelineState:
        rows, columns = pipeline.warehouse.execute(state["assembled"].sql)
        state["rows"] = rows
        state["columns"] = columns
        return state

    graph = StateGraph(PipelineState)
    graph.add_node("decompose", decompose_node)
    graph.add_node("discover", discover_node)
    graph.add_node("reason", reason_node)
    graph.add_node("resolve", resolve_node)
    graph.add_node("assemble", assemble_node)
    graph.add_node("execute", execute_node)
    graph.set_entry_point("decompose")
    graph.add_edge("decompose", "discover")
    graph.add_edge("discover", "reason")
    graph.add_edge("reason", "resolve")
    graph.add_edge("resolve", "assemble")
    graph.add_edge("assemble", "execute")
    graph.add_edge("execute", END)
    return graph.compile()
