from __future__ import annotations

from collections import deque

from app.registry.models import (
    DataSourceDocument,
    MeasureDocument,
    MetricDocument,
    RegistryDocument,
    ValidationError,
)


def _index_documents(documents: list[RegistryDocument]) -> dict[str, RegistryDocument]:
    return {doc.metadata.id: doc for doc in documents}


def _reachable_sources(
    start_id: str,
    index: dict[str, RegistryDocument],
) -> set[str]:
    visited = {start_id}
    queue: deque[str] = deque([start_id])
    while queue:
        current = queue.popleft()
        doc = index.get(current)
        if not isinstance(doc, DataSourceDocument):
            continue
        for join in doc.spec.joins:
            if join.target not in visited:
                visited.add(join.target)
                queue.append(join.target)
    return visited


def _source_has_column(doc: DataSourceDocument, column: str) -> bool:
    return any(field.name == column for field in doc.spec.schema_fields)


def validate_metric_dimensions(documents: list[RegistryDocument]) -> list[ValidationError]:
    """Each metric dimension must exist on a data source reachable from every component measure."""
    errors: list[ValidationError] = []
    index = _index_documents(documents)

    for doc in documents:
        if not isinstance(doc, MetricDocument):
            continue
        if not doc.spec.dimensions:
            continue

        measure_ids = [comp.ref for comp in doc.spec.components.values() if comp.kind == "measure"]
        primary_facts: list[str] = []
        for measure_id in measure_ids:
            measure = index.get(measure_id)
            if not isinstance(measure, MeasureDocument):
                continue
            if not measure.spec.depends_on:
                continue
            primary_facts.append(measure.spec.depends_on[0].get("ref", ""))

        for dimension in doc.spec.dimensions:
            for fact_id in primary_facts:
                fact_doc = index.get(fact_id)
                if not isinstance(fact_doc, DataSourceDocument):
                    errors.append(
                        ValidationError(
                            code="metric_dimension_missing_fact",
                            message=f"metric dimension {dimension!r} references unknown fact {fact_id!r}",
                            node_id=doc.metadata.id,
                        )
                    )
                    continue
                reachable = _reachable_sources(fact_id, index)
                found_on: str | None = None
                for source_id in reachable:
                    source_doc = index.get(source_id)
                    if isinstance(source_doc, DataSourceDocument) and _source_has_column(source_doc, dimension):
                        found_on = source_id
                        break
                if not found_on:
                    errors.append(
                        ValidationError(
                            code="metric_dimension_unreachable",
                            message=(
                                f"metric dimension {dimension!r} is not reachable from fact {fact_id!r} "
                                "via declared joins"
                            ),
                            node_id=doc.metadata.id,
                        )
                    )
    return errors


def validate_compositional_dimension_grain(documents: list[RegistryDocument]) -> list[ValidationError]:
    """Ensure join keys used across facts represent compatible non-time grains."""
    errors: list[ValidationError] = []
    index = _index_documents(documents)

    for doc in documents:
        if not isinstance(doc, DataSourceDocument):
            continue
        source_cols = {field.name: field for field in doc.spec.schema_fields}
        for join in doc.spec.joins:
            target_doc = index.get(join.target)
            if not isinstance(target_doc, DataSourceDocument):
                continue
            target_cols = {field.name: field for field in target_doc.spec.schema_fields}

            for clause in join.on.split(","):
                if "=" not in clause:
                    continue
                left, right = clause.split("=", 1)
                left_key = left.strip().split(".")[-1]
                right_key = right.strip().split(".")[-1]
                left_field = source_cols.get(left_key)
                right_field = target_cols.get(right_key)
                if not left_field or not right_field:
                    continue

                left_roles = {left_field.role}
                right_roles = {right_field.role}
                if left_field.role == "entity" and right_field.role == "entity":
                    continue
                if left_field.role in {"key", "entity"} and right_field.role in {"key", "entity"}:
                    continue
                if left_field.role == "dimension" and right_field.role == "dimension":
                    if left_key != right_key:
                        errors.append(
                            ValidationError(
                                code="dimensional_grain_mismatch",
                                message=(
                                    f"join {doc.metadata.id} -> {join.target} pairs "
                                    f"{left_key!r} ({left_field.role}) with {right_key!r} ({right_field.role}) "
                                    "at incompatible dimensional grains"
                                ),
                                edge_id=f"{doc.metadata.id}->JOINS_TO->{join.target}",
                            )
                        )
    return errors
