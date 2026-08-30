from __future__ import annotations

import re
from collections import defaultdict

from app.registry.models import (
    DataSourceDocument,
    MeasureDocument,
    MetricDocument,
    RegistryDocument,
    StagedRegistry,
    ValidationError,
    ValidationResult,
)

PARAM_PATTERN = re.compile(r"\{\{(\w+)\.(\w+)\}\}")


def _index_documents(documents: list[RegistryDocument]) -> dict[str, RegistryDocument]:
    return {doc.metadata.id: doc for doc in documents}


def validate_schema(documents: list[RegistryDocument]) -> list[ValidationError]:
    errors: list[ValidationError] = []
    for doc in documents:
        if doc.metadata.id != doc.metadata.id.strip():
            errors.append(
                ValidationError(
                    code="invalid_id",
                    message="metadata.id must not contain leading/trailing whitespace",
                    node_id=doc.metadata.id,
                )
            )
    return errors


def validate_reference_integrity(
    documents: list[RegistryDocument],
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    index = _index_documents(documents)

    for doc in documents:
        if isinstance(doc, DataSourceDocument):
            for join in doc.spec.joins:
                if join.target not in index:
                    errors.append(
                        ValidationError(
                            code="missing_join_target",
                            message=f"join target {join.target!r} not found in staged registry",
                            node_id=doc.metadata.id,
                            edge_id=f"{doc.metadata.id}->JOINS_TO->{join.target}",
                        )
                    )

        if isinstance(doc, MeasureDocument):
            for dep in doc.spec.depends_on:
                ref = dep.get("ref", "")
                if ref not in index:
                    errors.append(
                        ValidationError(
                            code="missing_depends_on",
                            message=f"depends_on ref {ref!r} not found",
                            node_id=doc.metadata.id,
                        )
                    )

        if isinstance(doc, MetricDocument):
            for role, component in doc.spec.components.items():
                if component.ref not in index:
                    errors.append(
                        ValidationError(
                            code="missing_component",
                            message=f"component {role} ref {component.ref!r} not found",
                            node_id=doc.metadata.id,
                        )
                    )
    return errors


def validate_canonical_path_uniqueness(
    documents: list[RegistryDocument],
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    canonical_pairs: dict[tuple[str, str], list[str]] = defaultdict(list)

    for doc in documents:
        if not isinstance(doc, DataSourceDocument):
            continue
        for join in doc.spec.joins:
            if not join.canonical:
                continue
            pair = tuple(sorted([doc.metadata.id, join.target]))
            canonical_pairs[pair].append(doc.metadata.id)

    for pair, sources in canonical_pairs.items():
        if len(sources) > 1:
            errors.append(
                ValidationError(
                    code="duplicate_canonical",
                    message=f"multiple canonical edges for pair {pair}",
                    edge_id=f"{pair[0]}<->{pair[1]}",
                )
            )
    return errors


def validate_parameter_enums(documents: list[RegistryDocument]) -> list[ValidationError]:
    errors: list[ValidationError] = []

    for doc in documents:
        if not isinstance(doc, MeasureDocument):
            continue
        params = doc.spec.parameters
        for match in PARAM_PATTERN.finditer(doc.spec.sql_fragment):
            param_name, field_name = match.group(1), match.group(2)
            param_def = params.get(param_name)
            if not param_def:
                errors.append(
                    ValidationError(
                        code="unknown_parameter",
                        message=f"sql_fragment references undeclared parameter {param_name!r}",
                        node_id=doc.metadata.id,
                    )
                )
                continue
            options = param_def.get("options", {})
            default = param_def.get("default")
            if field_name == "column":
                # column substitution is validated at assembly time against selected option
                if default and default not in options:
                    errors.append(
                        ValidationError(
                            code="invalid_default",
                            message=f"default {default!r} not in options for {param_name}",
                            node_id=doc.metadata.id,
                        )
                    )
            elif field_name not in ("column",):
                errors.append(
                    ValidationError(
                        code="invalid_param_field",
                        message=f"unsupported parameter field {field_name!r} in sql_fragment",
                        node_id=doc.metadata.id,
                    )
                )
    return errors


def validate_fact_to_fact_grain(documents: list[RegistryDocument]) -> list[ValidationError]:
    errors: list[ValidationError] = []
    index = _index_documents(documents)

    for doc in documents:
        if not isinstance(doc, DataSourceDocument):
            continue
        for join in doc.spec.joins:
            target_doc = index.get(join.target)
            if not isinstance(target_doc, DataSourceDocument):
                continue
            if doc.spec.type == "fact" and target_doc.spec.type == "fact":
                if not join.requires_preaggregation:
                    errors.append(
                        ValidationError(
                            code="fact_to_fact_preaggregation",
                            message=(
                                f"fact-to-fact join {doc.metadata.id} -> {join.target} "
                                "requires requires_preaggregation"
                            ),
                            edge_id=f"{doc.metadata.id}->JOINS_TO->{join.target}",
                        )
                    )
    return errors


def validate_staged_registry(staged: StagedRegistry) -> ValidationResult:
    documents = staged.documents
    all_errors: list[ValidationError] = []

    all_errors.extend(validate_schema(documents))
    all_errors.extend(validate_reference_integrity(documents))
    all_errors.extend(validate_canonical_path_uniqueness(documents))
    all_errors.extend(validate_parameter_enums(documents))
    all_errors.extend(validate_fact_to_fact_grain(documents))

    return ValidationResult(passed=len(all_errors) == 0, errors=all_errors)
