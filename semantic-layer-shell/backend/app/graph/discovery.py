from __future__ import annotations

from typing import Any

from app.graph.neo4j_client import Neo4jClient


class GraphDiscovery:
    def __init__(self, client: Neo4jClient) -> None:
        self.client = client

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        # Phase 1: keyword fallback when vector index unavailable
        cypher = """
        CALL {
            MATCH (m:Metric)
            WHERE toLower(m.name) CONTAINS toLower($q)
               OR toLower(m.description) CONTAINS toLower($q)
            RETURN m.id AS id, 'metric' AS kind, m.name AS name, m.description AS description, 1.0 AS score
            UNION
            MATCH (ms:Measure)
            WHERE toLower(ms.name) CONTAINS toLower($q)
               OR toLower(ms.description) CONTAINS toLower($q)
            RETURN ms.id AS id, 'measure' AS kind, ms.name AS name, ms.description AS description, 0.9 AS score
            UNION
            MATCH (d:DataSource)
            WHERE toLower(d.name) CONTAINS toLower($q)
               OR toLower(d.description) CONTAINS toLower($q)
            RETURN d.id AS id, 'data_source' AS kind, d.name AS name, d.description AS description, 0.8 AS score
        }
        RETURN id, kind, name, description, score
        ORDER BY score DESC
        LIMIT $limit
        """
        results = self.client.run(cypher, {"q": query, "limit": limit})
        if results:
            return results

        # In-memory fallback for dev without Neo4j
        return self._fallback_search(query, limit)

    def _fallback_search(self, query: str, limit: int) -> list[dict[str, Any]]:
        from app.registry.parser import parse_registry_directory
        from pathlib import Path

        registry_dir = Path(__file__).resolve().parents[3] / "registry"
        if not registry_dir.exists():
            return []

        staged = parse_registry_directory(registry_dir)
        q = query.lower()
        candidates: list[dict[str, Any]] = []
        for doc in staged.documents:
            haystack = f"{doc.metadata.name} {doc.metadata.description}".lower()
            if q in haystack or any(term in haystack for term in q.split()):
                candidates.append(
                    {
                        "id": doc.metadata.id,
                        "kind": doc.kind,
                        "name": doc.metadata.name,
                        "description": doc.metadata.description,
                        "score": 1.0,
                    }
                )
        return candidates[:limit]
