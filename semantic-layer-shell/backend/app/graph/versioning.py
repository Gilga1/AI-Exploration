from __future__ import annotations

from typing import Any

from app.graph.neo4j_client import Neo4jClient


class GraphVersionManager:
    def __init__(self, client: Neo4jClient) -> None:
        self.client = client

    def activate_version(self, version_id: str) -> None:
        statements = [
            (
                "MATCH (v:GraphVersion) SET v.current = false",
                {},
            ),
            (
                """
                MATCH (v:GraphVersion {id: $version_id})
                SET v.current = true
                WITH v
                MERGE (p:ProductionPointer {id: 'current'})
                SET p.version_id = $version_id, p.updated_at = datetime()
                """,
                {"version_id": version_id},
            ),
        ]
        self.client.run_transaction(statements)

    def get_current_version_id(self) -> str | None:
        rows = self.client.run(
            "MATCH (p:ProductionPointer {id: 'current'}) RETURN p.version_id AS version_id"
        )
        if rows and rows[0].get("version_id"):
            return rows[0]["version_id"]
        rows = self.client.run(
            "MATCH (v:GraphVersion {current: true}) RETURN v.id AS version_id LIMIT 1"
        )
        return rows[0]["version_id"] if rows else None

    def list_versions(self) -> list[dict[str, Any]]:
        current = self.get_current_version_id()
        rows = self.client.run(
            """
            MATCH (v:GraphVersion)
            OPTIONAL MATCH (n)-[:VERSION_OF]->(v)
            WITH v, count(n) AS node_count
            RETURN v.id AS id, v.created_at AS created_at, v.source_ref AS source_ref,
                   v.published_by AS published_by, v.current AS current, node_count
            ORDER BY v.created_at DESC
            """
        )
        for row in rows:
            row["current"] = row.get("id") == current or row.get("current") is True
        return rows

    def rollback(self, version_id: str) -> dict[str, str]:
        rows = self.client.run(
            "MATCH (v:GraphVersion {id: $version_id}) RETURN v.id AS id",
            {"version_id": version_id},
        )
        if not rows:
            raise ValueError(f"GraphVersion {version_id!r} not found")
        self.activate_version(version_id)
        return {"status": "rolled_back", "version_id": version_id}
