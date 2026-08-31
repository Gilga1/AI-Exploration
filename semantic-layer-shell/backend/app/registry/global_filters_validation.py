from __future__ import annotations

from app.registry.models import DataSourceDocument, RegistryDocument, ValidationError

SUPPORTED_OPERATORS = {
    "=",
    "!=",
    ">",
    ">=",
    "<",
    "<=",
    "is_null",
    "is_not_null",
    "in",
    "not_in",
    "ilike",
    "prefix",
}


def validate_global_filters(documents: list[RegistryDocument]) -> list[ValidationError]:
    errors: list[ValidationError] = []
    for doc in documents:
        if not isinstance(doc, DataSourceDocument):
            continue
        columns = {field.name for field in doc.spec.schema_fields}
        for idx, predicate in enumerate(doc.spec.global_filters):
            raw = predicate.model_dump(exclude_none=True)
            if predicate.sql:
                continue
            if not predicate.column or predicate.column not in columns:
                errors.append(
                    ValidationError(
                        code="global_filter_unknown_column",
                        message=f"global_filters[{idx}] column {predicate.column!r} not on {doc.metadata.id}",
                        node_id=doc.metadata.id,
                    )
                )
            if predicate.operator and predicate.operator not in SUPPORTED_OPERATORS:
                errors.append(
                    ValidationError(
                        code="global_filter_invalid_operator",
                        message=f"unsupported operator {predicate.operator!r}",
                        node_id=doc.metadata.id,
                    )
                )
            if predicate.operator in {"in", "not_in"} and not predicate.values:
                errors.append(
                    ValidationError(
                        code="global_filter_missing_values",
                        message=f"global_filters[{idx}] requires values for operator {predicate.operator}",
                        node_id=doc.metadata.id,
                    )
                )
            if predicate.operator not in {"is_null", "is_not_null", "in", "not_in"} and predicate.value is None:
                errors.append(
                    ValidationError(
                        code="global_filter_missing_value",
                        message=f"global_filters[{idx}] requires value for operator {predicate.operator}",
                        node_id=doc.metadata.id,
                    )
                )
    return errors
