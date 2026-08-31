from __future__ import annotations

from app.registry.models import EntityDocument, RegistryDocument, ValidationError


def validate_entity_specs(documents: list[RegistryDocument]) -> list[ValidationError]:
    errors: list[ValidationError] = []
    ds_ids = {doc.metadata.id for doc in documents if doc.kind == "data_source"}

    for doc in documents:
        if not isinstance(doc, EntityDocument):
            continue
        spec = doc.spec
        if not spec.resolves_via:
            continue
        rv = spec.resolves_via
        if rv.data_source not in ds_ids:
            errors.append(
                ValidationError(
                    code="entity_resolves_via_missing_source",
                    message=f"resolves_via.data_source {rv.data_source!r} not found",
                    node_id=doc.metadata.id,
                )
            )
            continue
        ds = next(d for d in documents if d.metadata.id == rv.data_source)
        columns = {f.name for f in ds.spec.schema_fields}  # type: ignore[union-attr]
        if rv.label_column not in columns:
            errors.append(
                ValidationError(
                    code="entity_label_column_missing",
                    message=f"label_column {rv.label_column!r} not on {rv.data_source}",
                    node_id=doc.metadata.id,
                )
            )
        if rv.key_column not in columns:
            errors.append(
                ValidationError(
                    code="entity_key_column_missing",
                    message=f"key_column {rv.key_column!r} not on {rv.data_source}",
                    node_id=doc.metadata.id,
                )
            )
        for target in spec.filter_targets:
            if target.data_source not in ds_ids:
                errors.append(
                    ValidationError(
                        code="entity_filter_target_missing_source",
                        message=f"filter_targets data_source {target.data_source!r} not found",
                        node_id=doc.metadata.id,
                    )
                )
    return errors
