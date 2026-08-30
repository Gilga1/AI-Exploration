"""Bootstrap bundled registry YAML into Neo4j.

Usage (from semantic-layer-shell/backend with venv active):
    python -m scripts.bootstrap_graph
    python -m scripts.bootstrap_graph --force
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow running as `python -m scripts.bootstrap_graph` from backend/
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.bootstrap import bootstrap_registry, ensure_graph_schema, graph_has_data
from app.graph.neo4j_client import get_neo4j_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish bundled registry to Neo4j")
    parser.add_argument("--force", action="store_true", help="Re-publish even if graph has data")
    args = parser.parse_args()

    if not ensure_graph_schema():
        client = get_neo4j_client()
        logger.error("Cannot connect to Neo4j: %s", client.last_error)
        logger.error("Start Neo4j: cd semantic-layer-shell && docker compose up -d neo4j")
        return 1

    if graph_has_data() and not args.force:
        logger.info("Graph already populated — use --force to re-publish")

    version_id = bootstrap_registry(force=args.force)
    if version_id:
        logger.info("Published graph version: %s", version_id)
        return 0

    if graph_has_data():
        return 0

    logger.error("Bootstrap failed — check registry validation and Neo4j logs")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
