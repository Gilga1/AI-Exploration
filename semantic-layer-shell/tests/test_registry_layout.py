import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.registry.graph_validation import validate_composition_acyclic, derive_metric_depends_on
from app.registry.models import (
    MeasureDocument,
    Metadata,
    MetricComponent,
    MetricDocument,
    MetricSpec,
    StagedRegistry,
)
from app.registry.parser import parse_registry_directory
from app.registry.validator import validate_staged_registry

REGISTRY_DIR = Path(__file__).resolve().parents[1] / "registry"


def test_registry_folder_layout():
    assert (REGISTRY_DIR / "data_sources").is_dir()
    assert (REGISTRY_DIR / "measures").is_dir()
    assert (REGISTRY_DIR / "metrics").is_dir()
    assert (REGISTRY_DIR / "entities").is_dir()


def test_metric_depends_on_matches_components():
    staged = parse_registry_directory(REGISTRY_DIR)
    metric = next(d for d in staged.documents if d.metadata.id == "net_flow_ratio")
    assert isinstance(metric, MetricDocument)
    deps = derive_metric_depends_on(metric)
    assert len(deps) == 2
    refs = {d["ref"] for d in deps}
    assert "total_transaction_amount_by_fund_day" in refs


def test_composition_cycle_detected():
    cyclic = MetricDocument(
        apiVersion="semantic-layer/v1",
        kind="metric",
        metadata=Metadata(id="a", name="A"),
        spec=MetricSpec(
            metric_type="composite",
            components={"child": MetricComponent(kind="metric", ref="b")},
        ),
    )
    cyclic_b = MetricDocument(
        apiVersion="semantic-layer/v1",
        kind="metric",
        metadata=Metadata(id="b", name="B"),
        spec=MetricSpec(
            metric_type="composite",
            components={"child": MetricComponent(kind="metric", ref="a")},
        ),
    )
    errors = validate_composition_acyclic([cyclic, cyclic_b])
    assert errors
    assert errors[0].code == "composition_cycle"
