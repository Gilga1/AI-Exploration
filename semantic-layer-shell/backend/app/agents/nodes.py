from __future__ import annotations

import time
from typing import Any, AsyncIterator

from app.graph.discovery import GraphDiscovery
from app.graph.neo4j_client import get_neo4j_client
from app.graph.resolver import GraphResolver
from app.sql_gen.assembler import SQLAssembler
from app.warehouse.snowflake_client import SnowflakeClient


class QueryPipeline:
    def __init__(self) -> None:
        self.client = get_neo4j_client()
        self.discovery = GraphDiscovery(self.client)
        self.resolver = GraphResolver(self.client)
        self.assembler = SQLAssembler()
        self.warehouse = SnowflakeClient()

    async def run(self, question: str, metric_id: str | None = None) -> AsyncIterator[dict[str, Any]]:
        stages = ["decompose", "discover", "reason", "resolve", "assemble", "execute", "answer"]
        context: dict[str, Any] = {"question": question}

        for stage in stages:
            start = time.perf_counter()
            yield {"event": "stage_start", "stage": stage}
            try:
                if stage == "decompose":
                    context["intent"] = self._decompose(question)
                elif stage == "discover":
                    terms = context["intent"].get("search_terms", [question])
                    candidates = []
                    for term in terms[:3]:
                        candidates.extend(self.discovery.search(term, limit=5))
                    context["candidates"] = self._dedupe_candidates(candidates)
                elif stage == "reason":
                    context["selection"] = self._reason(context["candidates"], metric_id)
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
                    rows, columns = self.warehouse.execute(assembled.sql)
                    context["rows"] = rows
                    context["columns"] = columns
                    yield {"event": "data_rows", "rows": rows, "columns": columns}
                elif stage == "answer":
                    answer = self._answer(context)
                    yield {"event": "token", "stage": "answer", "delta": answer}
            except Exception as exc:
                yield {"event": "error", "stage": stage, "error": str(exc)}
                return
            elapsed = time.perf_counter() - start
            yield {"event": "stage_complete", "stage": stage, "elapsed_sec": round(elapsed, 3)}

        yield {
            "event": "done",
            "result": {
                "metric_id": context.get("selection", {}).get("metric_id"),
                "sql_hash": getattr(context.get("assembled"), "sql_hash", None),
                "row_count": len(context.get("rows", [])),
            },
        }

    def _decompose(self, question: str) -> dict[str, Any]:
        # Phase 1 heuristic decompose (LLM hook point for LangGraph expansion)
        terms = [t.strip("?.,!") for t in question.lower().split() if len(t) > 3]
        return {
            "intent": "metric_query",
            "search_terms": terms or [question],
            "raw_question": question,
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

    def _reason(self, candidates: list[dict[str, Any]], metric_id: str | None) -> dict[str, Any]:
        if metric_id:
            return {"metric_id": metric_id, "parameters": {}, "dimensions": []}

        metrics = [c for c in candidates if c.get("kind") == "metric"]
        if metrics:
            top = metrics[0]
            return {"metric_id": top["id"], "parameters": {}, "dimensions": []}

        if candidates:
            return {"metric_id": candidates[0]["id"], "parameters": {}, "dimensions": []}

        # Default pilot metric
        return {"metric_id": "net_flow_ratio", "parameters": {}, "dimensions": []}

    def _answer(self, context: dict[str, Any]) -> str:
        selection = context.get("selection", {})
        rows = context.get("rows", [])
        metric_id = selection.get("metric_id", "unknown")
        if not rows:
            return f"No rows returned for metric {metric_id}."
        return f"Query for {metric_id} returned {len(rows)} row(s)."
