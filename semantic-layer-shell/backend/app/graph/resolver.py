from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.graph.neo4j_client import Neo4jClient
from app.registry.models import MetricDocument, DataSourceDocument
from app.registry.parser import parse_registry_directory


@dataclass
class ResolvedSubgraph:
    metric_id: str
    metric: dict[str, Any]
    measures: list[dict[str, Any]] = field(default_factory=list)
    data_sources: list[dict[str, Any]] = field(default_factory=list)
    joins: list[dict[str, Any]] = field(default_factory=list)
    graph_version_id: str | None = None
    node_ids: list[str] = field(default_factory=list)
    edge_ids: list[str] = field(default_factory=list)


class GraphResolver:
    def __init__(self, client: Neo4jClient) -> None:
        self.client = client

    def resolve_metric(self, metric_id: str) -> ResolvedSubgraph | None:
        cypher = """
        MATCH (v:GraphVersion {current: true})
        MATCH (m:Metric {id: $metric_id})-[:VERSION_OF]->(v)
        OPTIONAL MATCH (m)-[uc:USES_COMPONENT]->(comp)
        OPTIONAL MATCH (comp:Measure)-[:DEPENDS_ON]->(ds:DataSource)
        OPTIONAL MATCH (ds)-[j:JOINS_TO]->(target:DataSource)
        RETURN m, v.id AS graph_version_id,
               collect(DISTINCT comp) AS components,
               collect(DISTINCT ds) + collect(DISTINCT target) AS data_sources,
               collect(DISTINCT {source: ds.id, target: target.id, props: properties(j)}) AS joins,
               collect(DISTINCT {measure_id: comp.id, source_id: ds.id}) AS measure_sources
        """
        rows = self.client.run(cypher, {"metric_id": metric_id})
        if rows:
            row = rows[0]
            metric_node = row.get("m")
            if metric_node:
                return self._from_neo4j_row(metric_id, row)

        return self._resolve_from_registry_files(metric_id)

    def _normalize_measure(self, measure: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(measure)
        dimension_context = normalized.get("dimension_context")
        if isinstance(dimension_context, str):
            try:
                normalized["dimension_context"] = json.loads(dimension_context)
            except json.JSONDecodeError:
                normalized["dimension_context"] = {}
        spec_params = normalized.get("parameters")
        if isinstance(spec_params, str):
            try:
                normalized["spec_parameters"] = json.loads(spec_params)
            except json.JSONDecodeError:
                normalized["spec_parameters"] = {}
        elif spec_params and "spec_parameters" not in normalized:
            normalized["spec_parameters"] = spec_params
        return normalized

    def _from_neo4j_row(self, metric_id: str, row: dict[str, Any]) -> ResolvedSubgraph:
        metric = dict(row["m"]) if row.get("m") else {"id": metric_id}
        measure_sources: dict[str, list[str]] = {}
        for link in row.get("measure_sources", []) or []:
            if not link:
                continue
            mid = link.get("measure_id")
            sid = link.get("source_id")
            if mid and sid:
                measure_sources.setdefault(mid, []).append(sid)

        measures = []
        for m in row.get("components", []) or []:
            if not m:
                continue
            normalized = self._normalize_measure(dict(m))
            mid = normalized.get("id")
            if mid and mid in measure_sources:
                normalized["depends_on_refs"] = measure_sources[mid]
            measures.append(normalized)
        data_sources = []
        for d in row.get("data_sources", []) or []:
            if not d:
                continue
            ds = dict(d)
            gf = ds.get("global_filters")
            if isinstance(gf, str):
                try:
                    ds["global_filters"] = json.loads(gf)
                except json.JSONDecodeError:
                    ds["global_filters"] = []
            data_sources.append(ds)
        joins = [j for j in row.get("joins", []) if j and j.get("source")]
        node_ids = [metric_id] + [m.get("id", "") for m in measures] + [d.get("id", "") for d in data_sources]
        edge_ids = [f"{j['source']}->JOINS_TO->{j['target']}" for j in joins]
        return ResolvedSubgraph(
            metric_id=metric_id,
            metric=metric,
            measures=measures,
            data_sources=data_sources,
            joins=joins,
            graph_version_id=row.get("graph_version_id"),
            node_ids=[n for n in node_ids if n],
            edge_ids=edge_ids,
        )

    def _resolve_from_registry_files(self, metric_id: str) -> ResolvedSubgraph | None:
        registry_dir = Path(__file__).resolve().parents[3] / "registry"
        if not registry_dir.exists():
            return None

        staged = parse_registry_directory(registry_dir)
        metric_doc: MetricDocument | None = None
        for doc in staged.documents:
            if doc.kind == "metric" and doc.metadata.id == metric_id:
                metric_doc = doc  # type: ignore[assignment]
                break

        if not metric_doc:
            return None

        measures: list[dict[str, Any]] = []
        data_sources: list[dict[str, Any]] = []
        joins: list[dict[str, Any]] = []
        node_ids = [metric_id]
        edge_ids: list[str] = []

        doc_index = {d.metadata.id: d for d in staged.documents}
        ds_ids: set[str] = set()

        def add_data_source(ds_doc: DataSourceDocument) -> None:
            if ds_doc.metadata.id in ds_ids:
                return
            ds_ids.add(ds_doc.metadata.id)
            data_sources.append(
                {
                    "id": ds_doc.metadata.id,
                    "location": ds_doc.spec.location,
                    "type": ds_doc.spec.type,
                    "grain_keys": ds_doc.spec.grain_keys,
                    "schema_fields": [f.model_dump() for f in ds_doc.spec.schema_fields],
                    "global_filters": [
                        gf.model_dump(exclude_none=True) for gf in ds_doc.spec.global_filters
                    ],
                }
            )
            node_ids.append(ds_doc.metadata.id)

        for role, component in metric_doc.spec.components.items():
            child = doc_index.get(component.ref)
            if child and child.kind == "measure":
                measures.append(
                    {
                        "id": child.metadata.id,
                        "role": role,
                        "parameters": component.parameters,
                        "sql_fragment": child.spec.sql_fragment,  # type: ignore[union-attr]
                        "spec_parameters": child.spec.parameters,  # type: ignore[union-attr]
                        "dimension_context": child.spec.dimension_context,  # type: ignore[union-attr]
                        "time_filter": child.spec.time_filter,  # type: ignore[union-attr]
                        "depends_on_refs": [dep.get("ref", "") for dep in child.spec.depends_on],  # type: ignore[union-attr]
                    }
                )
                node_ids.append(child.metadata.id)
                edge_ids.append(f"{metric_id}->USES_COMPONENT->{child.metadata.id}({role})")

                for dep in child.spec.depends_on:  # type: ignore[union-attr]
                    ds = doc_index.get(dep.get("ref", ""))
                    if ds and ds.kind == "data_source":
                        add_data_source(ds)  # type: ignore[arg-type]
                        edge_ids.append(f"{child.metadata.id}->DEPENDS_ON->{ds.metadata.id}")
                        for join in ds.spec.joins:  # type: ignore[union-attr]
                            joins.append(
                                {
                                    "source": ds.metadata.id,
                                    "target": join.target,
                                    "on": join.on,
                                    "type": join.type,
                                    "canonical": join.canonical,
                                    "strategy": join.strategy,
                                }
                            )
                            edge_ids.append(f"{ds.metadata.id}->JOINS_TO->{join.target}")
                            target_doc = doc_index.get(join.target)
                            if target_doc and target_doc.kind == "data_source":
                                add_data_source(target_doc)  # type: ignore[arg-type]

        return ResolvedSubgraph(
            metric_id=metric_id,
            metric=metric_doc.model_dump(),
            measures=measures,
            data_sources=data_sources,
            joins=joins,
            graph_version_id="local-registry",
            node_ids=node_ids,
            edge_ids=edge_ids,
        )

    def get_dag(self, subgraph: str = "composition") -> dict[str, Any]:
        rel_map = {
            "lineage": "SOURCED_FROM",
            "join": "JOINS_TO",
            "composition": "USES_COMPONENT",
        }
        rel = rel_map.get(subgraph, "USES_COMPONENT")
        cypher = f"""
        MATCH (a)-[r:{rel}]->(b)
        RETURN collect(DISTINCT {{id: coalesce(a.id, a.name), label: labels(a)[0], name: coalesce(a.name, a.id)}}) AS nodes,
               collect(DISTINCT {{source: a.id, target: b.id, type: '{rel}', props: properties(r)}}) AS edges
        """
        rows = self.client.run(cypher)
        if rows and rows[0].get("nodes"):
            return {"nodes": rows[0]["nodes"], "edges": rows[0]["edges"], "subgraph": subgraph}

        return self._dag_from_registry(subgraph)

    def _dag_from_registry(self, subgraph: str) -> dict[str, Any]:
        registry_dir = Path(__file__).resolve().parents[3] / "registry"
        staged = parse_registry_directory(registry_dir) if registry_dir.exists() else None
        if not staged:
            return {"nodes": [], "edges": [], "subgraph": subgraph}

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add_node(node_id: str, label: str, name: str) -> None:
            if node_id not in seen:
                seen.add(node_id)
                nodes.append({"id": node_id, "label": label, "name": name})

        for doc in staged.documents:
            label = doc.kind.replace("_", " ").title().replace(" ", "")
            add_node(doc.metadata.id, label, doc.metadata.name)

            if subgraph == "join" and doc.kind == "data_source":
                for join in doc.spec.joins:  # type: ignore[union-attr]
                    edges.append(
                        {
                            "source": doc.metadata.id,
                            "target": join.target,
                            "type": "JOINS_TO",
                            "props": join.model_dump(),
                        }
                    )
            elif subgraph == "composition" and doc.kind == "metric":
                for role, comp in doc.spec.components.items():  # type: ignore[union-attr]
                    edges.append(
                        {
                            "source": doc.metadata.id,
                            "target": comp.ref,
                            "type": "USES_COMPONENT",
                            "props": {"role": role, **comp.model_dump()},
                        }
                    )
            elif subgraph == "composition" and doc.kind == "measure":
                for dep in doc.spec.depends_on:  # type: ignore[union-attr]
                    edges.append(
                        {
                            "source": doc.metadata.id,
                            "target": dep.get("ref"),
                            "type": "DEPENDS_ON",
                            "props": dep,
                        }
                    )

        return {"nodes": nodes, "edges": edges, "subgraph": subgraph}

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        for label in ("Metric", "Measure", "DataSource", "Entity"):
            cypher = f"MATCH (n:{label} {{id: $id}}) RETURN n, labels(n) AS labels"
            rows = self.client.run(cypher, {"id": node_id})
            if rows:
                node = dict(rows[0]["n"])
                node["labels"] = rows[0]["labels"]
                return node

        registry_dir = Path(__file__).resolve().parents[3] / "registry"
        if registry_dir.exists():
            staged = parse_registry_directory(registry_dir)
            for doc in staged.documents:
                if doc.metadata.id == node_id:
                    return {"id": node_id, "labels": [doc.kind], "document": doc.model_dump()}
        return None
