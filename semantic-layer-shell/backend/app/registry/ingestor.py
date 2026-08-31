from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from app.graph.neo4j_client import Neo4jClient
from app.graph.versioning import GraphVersionManager
from app.registry.graph_validation import derive_metric_depends_on
from app.registry.models import (
    DataSourceDocument,
    EntityDocument,
    MeasureDocument,
    MetricDocument,
    RegistryDocument,
    StagedRegistry,
    ValidationPolicyDocument,
)


from app.llm.embeddings import EmbeddingClient


def _embedding_for(text: str, dimensions: int) -> list[float]:
    client = EmbeddingClient()
    vector = client.embed(text)
    if len(vector) == dimensions:
        return vector
    # Pad or truncate if provider returns unexpected size
    if len(vector) > dimensions:
        return vector[:dimensions]
    return vector + [0.0] * (dimensions - len(vector))


class RegistryIngestor:
    def __init__(self, client: Neo4jClient, embedding_dimensions: int = 1536) -> None:
        self.client = client
        self.embedding_dimensions = embedding_dimensions

    def build_staging_cypher(self, staged: StagedRegistry, version_id: str) -> list[tuple[str, dict[str, Any]]]:
        statements: list[tuple[str, dict[str, Any]]] = []

        statements.append(
            (
                "CREATE (v:GraphVersion {id: $id, created_at: $created_at, source_ref: $source_ref, published_by: $published_by, current: false})",
                {
                    "id": version_id,
                    "created_at": datetime.now(UTC).isoformat(),
                    "source_ref": json.dumps(staged.source_files),
                    "published_by": "system",
                },
            )
        )

        for doc in staged.documents:
            statements.extend(self._document_statements(doc, version_id))

        statements.extend(self._represents_statements(staged))

        return statements

    def _represents_statements(self, staged: StagedRegistry) -> list[tuple[str, dict[str, Any]]]:
        statements: list[tuple[str, dict[str, Any]]] = []
        for doc in staged.documents:
            if not isinstance(doc, DataSourceDocument):
                continue
            for field in doc.spec.schema_fields:
                if not field.entity_ref:
                    continue
                statements.append(
                    (
                        """
                        MATCH (d:DataSource {id: $source_id})-[:HAS_COLUMN]->(c:Column {name: $col_name, source_id: $source_id})
                        MATCH (e:Entity {id: $entity_id})
                        MERGE (c)-[:REPRESENTS]->(e)
                        """,
                        {
                            "source_id": doc.metadata.id,
                            "col_name": field.name,
                            "entity_id": field.entity_ref,
                        },
                    )
                )
        return statements

    def _document_statements(
        self, doc: RegistryDocument, version_id: str
    ) -> list[tuple[str, dict[str, Any]]]:
        statements: list[tuple[str, dict[str, Any]]] = []

        if isinstance(doc, DataSourceDocument):
            statements.append(
                (
                    """
                    MERGE (d:DataSource {id: $id})
                    SET d += $props
                    WITH d
                    MATCH (v:GraphVersion {id: $version_id})
                    MERGE (d)-[:VERSION_OF]->(v)
                    """,
                    {
                        "id": doc.metadata.id,
                        "version_id": version_id,
                        "props": {
                            "name": doc.metadata.name,
                            "description": doc.metadata.description,
                            "description_embedding": _embedding_for(doc.metadata.description, self.embedding_dimensions),
                            "owner": doc.metadata.owner,
                            "status": doc.metadata.status,
                            "type": doc.spec.type,
                            "location": doc.spec.location,
                            "grain": doc.spec.grain,
                            "grain_keys": doc.spec.grain_keys,
                            "global_filters": json.dumps(
                                [gf.model_dump(exclude_none=True) for gf in doc.spec.global_filters]
                            ),
                        },
                    },
                )
            )

            for field in doc.spec.schema_fields:
                statements.append(
                    (
                        """
                        MATCH (d:DataSource {id: $source_id})
                        MERGE (c:Column {name: $name, source_id: $source_id})
                        SET c += $props
                        MERGE (d)-[:HAS_COLUMN]->(c)
                        """,
                        {
                            "source_id": doc.metadata.id,
                            "name": field.name,
                            "props": {
                                "type": field.type,
                                "role": field.role,
                                "exposed": field.exposed,
                                "pii": field.pii,
                                "description": field.description,
                                "entity_ref": field.entity_ref,
                            },
                        },
                    )
                )

            for join in doc.spec.joins:
                statements.append(
                    (
                        """
                        MATCH (a:DataSource {id: $source_id}), (b:DataSource {id: $target_id})
                        MERGE (a)-[j:JOINS_TO {target_id: $target_id}]->(b)
                        SET j += $props
                        """,
                        {
                            "source_id": doc.metadata.id,
                            "target_id": join.target,
                            "props": {
                                "on": join.on,
                                "type": join.type,
                                "cardinality": join.cardinality,
                                "canonical": join.canonical,
                                "strategy": join.strategy,
                                "requires_preaggregation": join.requires_preaggregation,
                                "notes": join.notes,
                            },
                        },
                    )
                )

        elif isinstance(doc, MeasureDocument):
            statements.append(
                (
                    """
                    MERGE (m:Measure {id: $id})
                    SET m += $props
                    WITH m
                    MATCH (v:GraphVersion {id: $version_id})
                    MERGE (m)-[:VERSION_OF]->(v)
                    """,
                    {
                        "id": doc.metadata.id,
                        "version_id": version_id,
                        "props": {
                            "name": doc.metadata.name,
                            "description": doc.metadata.description,
                            "description_embedding": _embedding_for(doc.metadata.description, self.embedding_dimensions),
                            "parameters": json.dumps(doc.spec.parameters),
                            "time_filter": json.dumps(doc.spec.time_filter),
                            "dimension_context": json.dumps(doc.spec.dimension_context),
                            "sql_fragment": doc.spec.sql_fragment,
                            "output_columns": json.dumps(doc.spec.output_columns),
                            "owner": doc.metadata.owner,
                            "status": doc.metadata.status,
                        },
                    },
                )
            )
            for dep in doc.spec.depends_on:
                ref = dep.get("ref")
                if ref:
                    statements.append(
                        (
                            """
                            MATCH (m:Measure {id: $measure_id}), (d:DataSource {id: $source_id})
                            MERGE (m)-[:DEPENDS_ON]->(d)
                            """,
                            {"measure_id": doc.metadata.id, "source_id": ref},
                        )
                    )

        elif isinstance(doc, MetricDocument):
            statements.append(
                (
                    """
                    MERGE (m:Metric {id: $id})
                    SET m += $props
                    WITH m
                    MATCH (v:GraphVersion {id: $version_id})
                    MERGE (m)-[:VERSION_OF]->(v)
                    """,
                    {
                        "id": doc.metadata.id,
                        "version_id": version_id,
                        "props": {
                            "name": doc.metadata.name,
                            "description": doc.metadata.description,
                            "description_embedding": _embedding_for(doc.metadata.description, self.embedding_dimensions),
                            "metric_type": doc.spec.metric_type,
                            "formula": doc.spec.formula,
                            "unit": doc.spec.unit,
                            "direction": doc.spec.direction,
                            "dimensions": doc.spec.dimensions,
                            "time_key": doc.spec.time_key,
                            "business_rules": doc.spec.business_rules,
                            "validation_policy": doc.spec.validation_policy,
                            "owner": doc.metadata.owner,
                            "status": doc.metadata.status,
                            "tags": doc.metadata.tags,
                        },
                    },
                )
            )
            for role, component in doc.spec.components.items():
                label = "Measure" if component.kind == "measure" else "Metric"
                statements.append(
                    (
                        f"""
                        MATCH (parent:Metric {{id: $metric_id}}), (child:{label} {{id: $child_id}})
                        MERGE (parent)-[r:USES_COMPONENT {{role: $role}}]->(child)
                        SET r.parameters = $parameters
                        """,
                        {
                            "metric_id": doc.metadata.id,
                            "child_id": component.ref,
                            "role": role,
                            "parameters": json.dumps(component.parameters),
                        },
                    )
                )
            for dep in derive_metric_depends_on(doc):
                ref = dep.get("ref")
                kind = dep.get("kind", "measure")
                if not ref:
                    continue
                label = "Measure" if kind == "measure" else "Metric"
                statements.append(
                    (
                        f"""
                        MATCH (parent:Metric {{id: $metric_id}}), (child:{label} {{id: $child_id}})
                        MERGE (parent)-[:DEPENDS_ON]->(child)
                        """,
                        {"metric_id": doc.metadata.id, "child_id": ref},
                    )
                )

        elif isinstance(doc, EntityDocument):
            text = f"{doc.metadata.name} {doc.metadata.description} {' '.join(doc.metadata.synonyms)}"
            spec = doc.spec
            statements.append(
                (
                    """
                    MERGE (e:Entity {id: $id})
                    SET e += $props
                    WITH e
                    MATCH (v:GraphVersion {id: $version_id})
                    MERGE (e)-[:VERSION_OF]->(v)
                    """,
                    {
                        "id": doc.metadata.id,
                        "version_id": version_id,
                        "props": {
                            "name": doc.metadata.name,
                            "description": doc.metadata.description,
                            "definition": doc.metadata.description,
                            "definition_embedding": _embedding_for(text, self.embedding_dimensions),
                            "synonyms": doc.metadata.synonyms,
                            "owner": doc.metadata.owner,
                            "status": doc.metadata.status,
                            "attributes": json.dumps(
                                [a.model_dump() for a in spec.attributes]
                            ),
                            "resolves_via": json.dumps(
                                spec.resolves_via.model_dump() if spec.resolves_via else None
                            ),
                            "correlate_with": json.dumps(spec.correlate_with),
                            "filter_targets": json.dumps(
                                [ft.model_dump() for ft in spec.filter_targets]
                            ),
                        },
                    },
                )
            )
            if spec.resolves_via:
                statements.append(
                    (
                        """
                        MATCH (e:Entity {id: $entity_id}), (d:DataSource {id: $source_id})
                        MERGE (e)-[r:RESOLVES_VIA]->(d)
                        SET r += $props
                        """,
                        {
                            "entity_id": doc.metadata.id,
                            "source_id": spec.resolves_via.data_source,
                            "props": {
                                "label_column": spec.resolves_via.label_column,
                                "key_column": spec.resolves_via.key_column,
                                "match": spec.resolves_via.match,
                                "limit": spec.resolves_via.limit,
                            },
                        },
                    )
                )

        elif isinstance(doc, ValidationPolicyDocument):
            statements.append(
                (
                    """
                    MERGE (p:ValidationPolicy {id: $id})
                    SET p += $props
                    WITH p
                    MATCH (v:GraphVersion {id: $version_id})
                    MERGE (p)-[:VERSION_OF]->(v)
                    """,
                    {
                        "id": doc.metadata.id,
                        "version_id": version_id,
                        "props": {
                            "name": doc.metadata.name,
                            "description": doc.metadata.description,
                            "rules": json.dumps(doc.spec.rules),
                            "confidence_aggregation": doc.spec.confidence_aggregation,
                            "applies_to": json.dumps(doc.spec.applies_to),
                        },
                    },
                )
            )
            for target in doc.spec.applies_to:
                ref = target.get("ref")
                kind = target.get("kind", "metric")
                if not ref or kind != "metric":
                    continue
                statements.append(
                    (
                        """
                        MATCH (m:Metric {id: $metric_id}), (p:ValidationPolicy {id: $policy_id})
                        MERGE (m)-[:HAS_VALIDATION_POLICY]->(p)
                        """,
                        {"metric_id": ref, "policy_id": doc.metadata.id},
                    )
                )

        return statements

    def publish(self, staged: StagedRegistry) -> str:
        version_id = f"v-{uuid.uuid4().hex[:12]}"
        statements = self.build_staging_cypher(staged, version_id)
        self.client.run_transaction(statements)
        GraphVersionManager(self.client).activate_version(version_id)
        return version_id
