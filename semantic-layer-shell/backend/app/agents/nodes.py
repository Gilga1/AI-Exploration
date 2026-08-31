from __future__ import annotations

import time
from typing import Any, AsyncIterator, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.analysis import analyze_rows
from app.agents.explorer import MetricExplorer
from app.agents.insights import generate_insights
from app.agents.dimension_selection import enrich_candidates_with_metric_fields
from app.agents.revision import apply_revision
from app.agents.entity_resolution import EntityResolver, build_mentions_from_intent
from app.agents.time_resolution import resolve_time_range
from app.graph.entity_catalog import load_data_sources_for_catalog, load_entity_catalog
from app.config.settings import get_settings
from app.agents.visualization import build_chart_spec
from app.audit.store import AuditStore
from app.cache.query_cache import QueryResultCache
from app.graph.discovery import GraphDiscovery
from app.graph.neo4j_client import get_neo4j_client
from app.graph.resolver import GraphResolver
from app.llm.client import LLMClient
from app.sql_gen.assembler import SQLAssembler
from app.warehouse.snowflake_client import SnowflakeClient


class PipelineState(TypedDict, total=False):
    question: str
    metric_id: str | None
    revision_hint: str | None
    intent: dict[str, Any]
    candidates: list[dict[str, Any]]
    selection: dict[str, Any]
    subgraph: Any
    assembled: Any
    rows: list[dict[str, Any]]
    columns: list[str]
    analysis: dict[str, Any]
    events: list[dict[str, Any]]


class QueryPipeline:
    def __init__(self) -> None:
        self.client = get_neo4j_client()
        self.discovery = GraphDiscovery(self.client)
        self.resolver = GraphResolver(self.client)
        self.assembler = SQLAssembler()
        self.warehouse = SnowflakeClient()
        self.llm = LLMClient(self.resolver)
        self.audit = AuditStore()
        self.cache = QueryResultCache()
        self.explorer = MetricExplorer(self.client)

        self.entity_resolver = EntityResolver(self.warehouse)

    async def run(
        self,
        question: str,
        metric_id: str | None = None,
        revision_hint: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        stages = [
            "decompose",
            "discover",
            "reason",
            "resolve_entities",
            "resolve_time",
            "resolve",
            "assemble",
            "execute",
            "analyze",
            "insights",
            "visualization",
            "explorer",
            "answer",
        ]
        context: dict[str, Any] = {
            "question": question,
            "revision_hint": revision_hint,
            "entity_catalog": load_entity_catalog(self.client),
        }

        for stage in stages:
            start = time.perf_counter()
            yield {"event": "stage_start", "stage": stage}
            try:
                if stage == "decompose":
                    context["intent"] = self.llm.decompose(
                        question, context.get("entity_catalog", [])
                    )
                elif stage == "discover":
                    terms = context["intent"].get("search_terms", [question])
                    candidates = []
                    for term in terms[:3]:
                        candidates.extend(self.discovery.search(term, limit=5))
                    context["candidates"] = enrich_candidates_with_metric_fields(
                        self._dedupe_candidates(candidates)
                    )
                elif stage == "reason":
                    if revision_hint and context.get("candidates"):
                        context["selection"] = apply_revision(
                            self.llm,
                            question,
                            revision_hint,
                            context.get("selection", {}),
                            context["candidates"],
                        )
                    else:
                        context["selection"] = self.llm.reason(
                            question,
                            context["candidates"],
                            metric_id=metric_id,
                            intent=context.get("intent"),
                        )
                    sel = context["selection"]
                    threshold = get_settings().reason_confidence_threshold
                    confidence = sel.get("confidence") if sel.get("confidence") is not None else 1.0
                    needs_confirmation = confidence < threshold and not sel.get("confirmed")
                    yield {
                        "event": "selection",
                        "metric_id": sel.get("metric_id"),
                        "dimensions": sel.get("dimensions", []),
                        "confidence": sel.get("confidence"),
                        "rationale": sel.get("rationale"),
                        "needs_confirmation": needs_confirmation,
                        "revised": sel.get("revised", False),
                        "dimension_warnings": sel.get("dimension_warnings", []),
                    }
                    if needs_confirmation:
                        yield {
                            "event": "confirmation_required",
                            "metric_id": sel.get("metric_id"),
                            "confidence": confidence,
                            "candidates": context.get("candidates", [])[:10],
                            "message": (
                                "Low confidence metric selection — confirm the metric before continuing."
                            ),
                        }
                        return
                elif stage == "resolve_entities":
                    mentions = build_mentions_from_intent(context.get("intent", {}))
                    resolution_sources = load_data_sources_for_catalog(
                        context.get("entity_catalog", []), self.client
                    )
                    entity_result = self.entity_resolver.resolve(
                        mentions,
                        context.get("entity_catalog", []),
                        resolution_sources,
                    )
                    context["entity_resolution"] = entity_result.to_dict()
                    ambiguous = [
                        r for r in entity_result.resolutions if r.get("status") == "ambiguous"
                    ]
                    if ambiguous:
                        yield {
                            "event": "disambiguation_required",
                            "entity_type": ambiguous[0].get("entity_type"),
                            "candidates": ambiguous[0].get("candidates", []),
                        }
                        return
                    yield {
                        "event": "entity_resolution",
                        "resolutions": entity_result.resolutions,
                    }
                elif stage == "resolve_time":
                    context["resolved_time"] = resolve_time_range(
                        context.get("intent", {}).get("time_range")
                    )
                    if context["resolved_time"]:
                        yield {"event": "time_resolution", "time": context["resolved_time"]}
                elif stage == "resolve":
                    selected_id = context["selection"]["metric_id"]
                    subgraph = self.resolver.resolve_metric(selected_id)
                    if not subgraph:
                        raise ValueError(f"Could not resolve metric {selected_id!r}")
                    context["subgraph"] = subgraph
                elif stage == "assemble":
                    subgraph = context["subgraph"]
                    selection = context["selection"]
                    entity_resolution = context.get("entity_resolution", {})
                    assembled = self.assembler.assemble(
                        subgraph,
                        parameters=selection.get("parameters", {}),
                        dimensions=selection.get("dimensions"),
                        entity_filters=entity_resolution.get("filters", []),
                        resolved_time=context.get("resolved_time"),
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
                        "filters_applied": entity_resolution.get("filters", []),
                        "time_range_applied": context.get("resolved_time"),
                        "global_filters_applied": assembled.provenance.get(
                            "global_filters_applied", []
                        ),
                    }
                elif stage == "execute":
                    assembled = context["assembled"]
                    selection = context["selection"]
                    cache_key = QueryResultCache.make_key(
                        graph_version_id=assembled.graph_version_id,
                        node_ids=assembled.node_ids,
                        edge_ids=assembled.edge_ids,
                        parameters=selection.get("parameters"),
                        dimensions=selection.get("dimensions"),
                        sql_hash=assembled.sql_hash,
                    )
                    context["cache_key"] = cache_key
                    cached = self.cache.get(cache_key)
                    if cached:
                        rows, columns = cached
                        yield {"event": "cache_hit", "cache_key": cache_key}
                    else:
                        try:
                            rows, columns = self.warehouse.execute(assembled.sql)
                        except RuntimeError as exc:
                            if not self.warehouse.is_configured:
                                rows, columns = [], []
                                yield {"event": "warning", "stage": "execute", "message": str(exc)}
                            else:
                                raise
                        if rows:
                            self.cache.set(cache_key, rows, columns)
                    context["rows"] = rows
                    context["columns"] = columns
                    yield {"event": "data_rows", "rows": rows, "columns": columns}
                elif stage == "analyze":
                    context["analysis"] = analyze_rows(
                        context.get("rows", []), context.get("columns", [])
                    )
                    yield {"event": "analysis", "analysis": context["analysis"]}
                elif stage == "insights":
                    text = generate_insights(
                        self.llm,
                        question,
                        context["selection"]["metric_id"],
                        context.get("analysis", {}),
                        context.get("rows", []),
                    )
                    context["insights"] = text
                    yield {"event": "insights", "delta": text}
                elif stage == "visualization":
                    chart = build_chart_spec(
                        context.get("rows", []),
                        context.get("columns", []),
                        context["selection"]["metric_id"],
                    )
                    context["chart"] = chart
                    if chart:
                        yield {"event": "visualization", "chart": chart}
                elif stage == "explorer":
                    related = self.explorer.related_metrics(context["selection"]["metric_id"])
                    context["related_metrics"] = related
                    yield {"event": "explorer", "related_metrics": related}
                elif stage == "answer":
                    assembled = context.get("assembled")
                    insights = context.get("insights", "")
                    answer = self.llm.answer(
                        question=question,
                        metric_id=context["selection"]["metric_id"],
                        rows=context.get("rows", []),
                        columns=context.get("columns", []),
                        sql=getattr(assembled, "sql", None),
                    )
                    if insights and insights not in answer:
                        answer = f"{answer}\n\n{insights}"
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
            extra={
                "rationale": selection.get("rationale"),
                "cache_key": context.get("cache_key"),
                "revised": selection.get("revised", False),
            },
        )

        yield {
            "event": "done",
            "result": {
                "metric_id": selection.get("metric_id"),
                "sql_hash": getattr(assembled, "sql_hash", None),
                "row_count": len(context.get("rows", [])),
                "llm_enabled": self.llm.enabled,
                "cache_key": context.get("cache_key"),
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
    """LangGraph state machine for Phase 2 pipeline (non-streaming path)."""
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
        if state.get("revision_hint"):
            state["selection"] = apply_revision(
                pipeline.llm,
                state["question"],
                state["revision_hint"],
                state.get("selection", {}),
                state.get("candidates", []),
            )
        else:
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
        assembled = state["assembled"]
        selection = state["selection"]
        cache_key = QueryResultCache.make_key(
            graph_version_id=assembled.graph_version_id,
            node_ids=assembled.node_ids,
            edge_ids=assembled.edge_ids,
            parameters=selection.get("parameters"),
            dimensions=selection.get("dimensions"),
            sql_hash=assembled.sql_hash,
        )
        cached = pipeline.cache.get(cache_key)
        if cached:
            state["rows"], state["columns"] = cached
        else:
            try:
                state["rows"], state["columns"] = pipeline.warehouse.execute(assembled.sql)
            except RuntimeError:
                state["rows"], state["columns"] = [], []
            if state["rows"]:
                pipeline.cache.set(cache_key, state["rows"], state["columns"])
        return state

    def analyze_node(state: PipelineState) -> PipelineState:
        state["analysis"] = analyze_rows(state.get("rows", []), state.get("columns", []))
        return state

    graph = StateGraph(PipelineState)
    graph.add_node("decompose", decompose_node)
    graph.add_node("discover", discover_node)
    graph.add_node("reason", reason_node)
    graph.add_node("resolve", resolve_node)
    graph.add_node("assemble", assemble_node)
    graph.add_node("execute", execute_node)
    graph.add_node("analyze", analyze_node)
    graph.set_entry_point("decompose")
    graph.add_edge("decompose", "discover")
    graph.add_edge("discover", "reason")
    graph.add_edge("reason", "resolve")
    graph.add_edge("resolve", "assemble")
    graph.add_edge("assemble", "execute")
    graph.add_edge("execute", "analyze")
    graph.add_edge("analyze", END)
    return graph.compile()
