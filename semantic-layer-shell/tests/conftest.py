import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.config.settings import Settings, get_settings


@pytest.fixture(autouse=True)
def enable_registry_fallback_for_tests(monkeypatch):
    """Tests use bundled pilot registry/ YAML when Neo4j is unavailable."""
    monkeypatch.setenv("ALLOW_REGISTRY_FALLBACK", "true")
    monkeypatch.setenv("DEBUG", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
