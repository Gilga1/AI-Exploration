from __future__ import annotations

from typing import Any

from app.graph.neo4j_client import Neo4jClient


class MetricExplorer:
    def __init__(self, client: Neo4jClient) -> None:
        self.client = client

    def related_metrics(self, metric_id: str, limit: int = 5) -> list[dict[str, Any]]:
        cypher = """
        MATCH (v:GraphVersion {current: true})
        MATCH (m:Metric {id: $metric_id})-[:VERSION_OF]->(v)
        OPTIONAL MATCH (m)-[:USES_COMPONENT|DEPENDS_ON*1..2]->(related:Measure)
        OPTIONAL MATCH (related_metric:Metric)-[:USES_COMPONENT]->(related)
        WHERE related_metric.id <> $metric_id
        RETURN DISTINCT related_metric.id AS id, related_metric.name AS name,
               related_metric.description AS description
        LIMIT $limit
        """
        rows = self.client.run(cypher, {"metric_id": metric_id, "limit": limit})
        if rows:
            return [r for r in rows if r.get("id")]

        # Registry fallback
        from pathlib import Path

        from app.registry.parser import parse_registry_directory

        registry_dir = Path(__file__).resolve().parents[3] / "registry"
        if not registry_dir.exists():
            return []

        staged = parse_registry_directory(registry_dir)
        related: list[dict[str, Any]] = []
        for doc in staged.documents:
            if doc.kind == "metric" and doc.metadata.id != metric_id:
                related.append(
                    {
                        "id": doc.metadata.id,
                        "name": doc.metadata.name,
                        "description": doc.metadata.description,
                    }
                )
        return related[:limit]
