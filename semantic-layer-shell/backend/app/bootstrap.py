from __future__ import annotations

import logging
from pathlib import Path

from app.config.settings import get_settings
from app.graph.neo4j_client import get_neo4j_client
from app.graph.schema import CONSTRAINTS_AND_INDEXES
from app.registry.ingestor import RegistryIngestor
from app.registry.parser import parse_registry_directory
from app.registry.validator import validate_staged_registry

logger = logging.getLogger(__name__)


def ensure_graph_schema() -> bool:
    client = get_neo4j_client()
    if not client.connect():
        logger.warning("Neo4j not reachable: %s", client.last_error)
        return False
    for stmt in CONSTRAINTS_AND_INDEXES:
        try:
            client.run(stmt)
        except Exception as exc:
            logger.debug("Schema statement skipped: %s — %s", exc, stmt[:60])
    return True


def graph_has_data() -> bool:
    client = get_neo4j_client()
    if not client.connect():
        return False
    rows = client.run("MATCH (m:Metric) RETURN count(m) AS c")
    return bool(rows and rows[0].get("c", 0) > 0)


def bootstrap_registry(force: bool = False) -> str | None:
    """Validate and publish bundled registry YAML into Neo4j."""
    settings = get_settings()
    if not settings.auto_publish_registry and not force:
        logger.info("auto_publish_registry disabled — skipping bootstrap")
        return None

    if not ensure_graph_schema():
        return None

    if graph_has_data() and not force:
        logger.info("Neo4j already has metrics — skipping bootstrap publish")
        return None

    registry_dir = Path(__file__).resolve().parents[2] / "registry"
    if not registry_dir.exists():
        logger.warning("Registry directory not found: %s", registry_dir)
        return None

    staged = parse_registry_directory(registry_dir)
    validation = validate_staged_registry(staged)
    if not validation.passed:
        logger.error("Registry validation failed: %s", validation.errors)
        return None

    client = get_neo4j_client()
    ingestor = RegistryIngestor(client, settings.embedding_dimensions)
    version_id = ingestor.publish(staged)
    logger.info("Published registry %s (%d documents)", version_id, len(staged.documents))
    return version_id
