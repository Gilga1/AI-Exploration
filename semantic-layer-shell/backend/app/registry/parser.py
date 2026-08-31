from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.registry.models import (
    DataSourceDocument,
    EntityDocument,
    MeasureDocument,
    MetricDocument,
    RegistryDocument,
    StagedRegistry,
    ValidationPolicyDocument,
)


def _parse_document(data: dict[str, Any]) -> RegistryDocument:
    kind = data.get("kind")
    if kind == "data_source":
        return DataSourceDocument.model_validate(data)
    if kind == "measure":
        return MeasureDocument.model_validate(data)
    if kind == "metric":
        return MetricDocument.model_validate(data)
    if kind == "entity":
        return EntityDocument.model_validate(data)
    if kind == "validation_policy":
        return ValidationPolicyDocument.model_validate(data)
    raise ValueError(f"Unknown registry kind: {kind!r}")


def parse_yaml_content(content: str, source_name: str = "<inline>") -> RegistryDocument:
    data = yaml.safe_load(content)
    if not isinstance(data, dict):
        raise ValueError(f"{source_name}: expected YAML mapping at root")
    return _parse_document(data)


def parse_yaml_file(path: Path) -> RegistryDocument:
    content = path.read_text(encoding="utf-8")
    return parse_yaml_content(content, source_name=str(path))


def parse_registry_files(paths: list[Path]) -> StagedRegistry:
    documents: list[RegistryDocument] = []
    source_files: list[str] = []
    for path in paths:
        doc = parse_yaml_file(path)
        documents.append(doc)
        source_files.append(str(path))
    return StagedRegistry(documents=documents, source_files=source_files)


def parse_registry_directory(directory: Path) -> StagedRegistry:
    paths = sorted(directory.glob("**/*.yaml")) + sorted(directory.glob("**/*.yml"))
    return parse_registry_files(paths)
