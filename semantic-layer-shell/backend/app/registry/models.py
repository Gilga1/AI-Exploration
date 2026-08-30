from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class RegistryKind(str, Enum):
    DATA_SOURCE = "data_source"
    MEASURE = "measure"
    METRIC = "metric"
    ENTITY = "entity"


class Metadata(BaseModel):
    id: str
    name: str
    description: str = ""
    owner: str | None = None
    status: Literal["draft", "active", "deprecated"] = "active"
    tags: list[str] = Field(default_factory=list)
    synonyms: list[str] = Field(default_factory=list)


class SchemaField(BaseModel):
    name: str
    type: str
    role: Literal[
        "key", "entity", "dimension", "amount", "filter", "timestamp", "time_key", "metadata"
    ]
    exposed: bool = True
    pii: bool = False
    description: str = ""
    entity_ref: str | None = None


class JoinSpec(BaseModel):
    target: str
    on: str
    cardinality: str
    type: Literal["left", "inner", "right", "full"] = "left"
    canonical: bool = False
    strategy: Literal["full_history", "latest_snapshot"] = "full_history"
    requires_preaggregation: list[str] = Field(default_factory=list)
    notes: str = ""


class DataSourceSpec(BaseModel):
    type: Literal["fact", "dimension", "bridge"]
    location: str
    grain: str
    grain_keys: list[str]
    schema_fields: list[SchemaField]
    joins: list[JoinSpec] = Field(default_factory=list)


class DataSourceDocument(BaseModel):
    apiVersion: Literal["semantic-layer/v1"]
    kind: Literal["data_source"]
    metadata: Metadata
    spec: DataSourceSpec


class ParameterOption(BaseModel):
    column: str
    description: str = ""


class MeasureSpec(BaseModel):
    parameters: dict[str, Any] = Field(default_factory=dict)
    time_filter: dict[str, Any] = Field(default_factory=dict)
    dimension_context: dict[str, Any] = Field(default_factory=dict)
    sql_fragment: str
    output_columns: list[dict[str, Any]] = Field(default_factory=list)
    depends_on: list[dict[str, str]] = Field(default_factory=list)


class MeasureDocument(BaseModel):
    apiVersion: Literal["semantic-layer/v1"]
    kind: Literal["measure"]
    metadata: Metadata
    spec: MeasureSpec


class MetricComponent(BaseModel):
    kind: Literal["measure", "metric"]
    ref: str
    parameters: dict[str, str] = Field(default_factory=dict)


class MetricSpec(BaseModel):
    metric_type: Literal["simple", "ratio", "change", "composite"]
    components: dict[str, MetricComponent]
    formula: str = ""
    unit: str = ""
    direction: Literal["higher_is_better", "lower_is_better", "target_range"] = "higher_is_better"
    dimensions: list[str] = Field(default_factory=list)
    time_key: str = ""
    business_rules: list[str] = Field(default_factory=list)
    depends_on: list[dict[str, str]] = Field(default_factory=list)


class MetricDocument(BaseModel):
    apiVersion: Literal["semantic-layer/v1"]
    kind: Literal["metric"]
    metadata: Metadata
    spec: MetricSpec


class EntityDocument(BaseModel):
    apiVersion: Literal["semantic-layer/v1"]
    kind: Literal["entity"]
    metadata: Metadata
    spec: dict[str, Any] = Field(default_factory=dict)


RegistryDocument = DataSourceDocument | MeasureDocument | MetricDocument | EntityDocument


class ValidationError(BaseModel):
    code: str
    message: str
    node_id: str | None = None
    edge_id: str | None = None


class ValidationResult(BaseModel):
    passed: bool
    errors: list[ValidationError] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StagedRegistry(BaseModel):
    documents: list[RegistryDocument] = Field(default_factory=list)
    source_files: list[str] = Field(default_factory=list)
