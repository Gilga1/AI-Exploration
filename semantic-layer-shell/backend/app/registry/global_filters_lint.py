from __future__ import annotations

import re

from app.registry.models import DataSourceDocument, MeasureDocument, RegistryDocument, ValidationError
from app.sql_gen.filter_assembler import predicate_to_sql


def validate_duplicate_global_filters(documents: list[RegistryDocument]) -> list[str]:
    warnings: list[str] = []
    index = {doc.metadata.id: doc for doc in documents}

    for doc in documents:
        if not isinstance(doc, MeasureDocument):
            continue
        for dep in doc.spec.depends_on:
            ds = index.get(dep.get("ref", ""))
            if not isinstance(ds, DataSourceDocument):
                continue
            for predicate in ds.spec.global_filters:
                rendered = predicate_to_sql(predicate.model_dump(exclude_none=True))
                if rendered and rendered.lower() in doc.spec.sql_fragment.lower():
                    warnings.append(
                        f"measure {doc.metadata.id} duplicates global_filters predicate "
                        f"from {ds.metadata.id}: {rendered}"
                    )
    return warnings
