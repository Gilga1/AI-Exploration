from __future__ import annotations

from collections import defaultdict

from app.registry.models import (
    DataSourceDocument,
    MeasureDocument,
    MetricDocument,
    RegistryDocument,
    ValidationError,
)


def derive_metric_depends_on(doc: MetricDocument) -> list[dict[str, str]]:
    """If depends_on is empty, derive from components."""
    if doc.spec.depends_on:
        return doc.spec.depends_on
    derived: list[dict[str, str]] = []
    for component in doc.spec.components.values():
        derived.append({"kind": component.kind, "ref": component.ref})
    return derived


def validate_metric_depends_on(documents: list[RegistryDocument]) -> list[ValidationError]:
    errors: list[ValidationError] = []
    index = _index(documents)

    for doc in documents:
        if not isinstance(doc, MetricDocument):
            continue
        deps = derive_metric_depends_on(doc)
        component_refs = {c.ref for c in doc.spec.components.values()}
        for dep in deps:
            ref = dep.get("ref", "")
            kind = dep.get("kind", "")
            if ref not in index:
                errors.append(
                    ValidationError(
                        code="missing_metric_depends_on",
                        message=f"metric depends_on ref {ref!r} not found",
                        node_id=doc.metadata.id,
                    )
                )
            elif ref not in component_refs:
                errors.append(
                    ValidationError(
                        code="depends_on_not_in_components",
                        message=f"depends_on ref {ref!r} must appear in components",
                        node_id=doc.metadata.id,
                    )
                )
            elif kind and index[ref].kind != kind:
                errors.append(
                    ValidationError(
                        code="depends_on_kind_mismatch",
                        message=f"depends_on kind {kind!r} does not match document kind for {ref!r}",
                        node_id=doc.metadata.id,
                    )
                )
    return errors


def validate_composition_acyclic(documents: list[RegistryDocument]) -> list[ValidationError]:
    """Detect cycles in metric→metric composition (USES_COMPONENT among metrics)."""
    graph: dict[str, list[str]] = defaultdict(list)
    for doc in documents:
        if not isinstance(doc, MetricDocument):
            continue
        for component in doc.spec.components.values():
            if component.kind == "metric":
                graph[doc.metadata.id].append(component.ref)

    visited: set[str] = set()
    stack: set[str] = set()
    cycle_path: list[str] = []

    def dfs(node: str, path: list[str]) -> bool:
        if node in stack:
            cycle_path.extend(path[path.index(node) :] + [node])
            return True
        if node in visited:
            return False
        visited.add(node)
        stack.add(node)
        for child in graph.get(node, []):
            if dfs(child, path + [node]):
                return True
        stack.remove(node)
        return False

    for node in graph:
        if dfs(node, []):
            return [
                ValidationError(
                    code="composition_cycle",
                    message=f"composition cycle detected: {' -> '.join(cycle_path)}",
                    node_id=cycle_path[0] if cycle_path else node,
                )
            ]
    return []


def validate_lineage_acyclic(documents: list[RegistryDocument]) -> list[ValidationError]:
    """Detect cycles in data_source sourced_from lineage (when declared)."""
    graph: dict[str, list[str]] = defaultdict(list)
    for doc in documents:
        if not isinstance(doc, DataSourceDocument):
            continue
        for source_id in getattr(doc.spec, "sourced_from", []) or []:
            graph[doc.metadata.id].append(source_id)

    if not graph:
        return []

    visited: set[str] = set()
    stack: set[str] = set()
    cycle_path: list[str] = []

    def dfs(node: str, path: list[str]) -> bool:
        if node in stack:
            cycle_path.extend(path[path.index(node) :] + [node])
            return True
        if node in visited:
            return False
        visited.add(node)
        stack.add(node)
        for child in graph.get(node, []):
            if dfs(child, path + [node]):
                return True
        stack.remove(node)
        return False

    for node in graph:
        if dfs(node, []):
            return [
                ValidationError(
                    code="lineage_cycle",
                    message=f"lineage cycle detected: {' -> '.join(cycle_path)}",
                    node_id=cycle_path[0] if cycle_path else node,
                )
            ]
    return []


def validate_neo4j_cycles(client) -> list[ValidationError]:
    """Run Cypher cycle checks against the live graph (post-ingest sanity)."""
    errors: list[ValidationError] = []
    composition = client.run(
        """
        MATCH p = (m:Metric)-[:USES_COMPONENT*1..]->(m)
        RETURN m.id AS cyclic_node, [n IN nodes(p) | n.id] AS cycle_path
        LIMIT 1
        """
    )
    if composition:
        row = composition[0]
        errors.append(
            ValidationError(
                code="composition_cycle_neo4j",
                message=f"Neo4j composition cycle at {row.get('cyclic_node')}",
                node_id=row.get("cyclic_node"),
            )
        )
    return errors


def _index(documents: list[RegistryDocument]) -> dict[str, RegistryDocument]:
    return {doc.metadata.id: doc for doc in documents}
