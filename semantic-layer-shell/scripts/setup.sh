#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Semantic Layer Shell setup"

# 1. Environment file
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "    Created .env from .env.example — edit it with your API keys and Snowflake credentials."
else
  echo "    .env already exists"
fi

# 2. Neo4j via Docker
if command -v docker &>/dev/null; then
  echo "==> Starting Neo4j (docker compose)..."
  docker compose up -d neo4j
  echo "    Waiting for Neo4j to become healthy..."
  for i in $(seq 1 60); do
    if docker compose ps neo4j 2>/dev/null | grep -q "(healthy)"; then
      echo "    Neo4j is healthy"
      break
    fi
    if [[ $i -eq 60 ]]; then
      echo "    WARNING: Neo4j health check timed out — continuing anyway"
    fi
    sleep 2
  done
else
  echo "    WARNING: docker not found — start Neo4j manually"
fi

# 3. Python backend
echo "==> Installing Python dependencies..."
cd backend
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt

# 4. Bootstrap graph (publish registry to Neo4j)
echo "==> Bootstrapping registry into Neo4j..."
python -m scripts.bootstrap_graph

# 5. Frontend
echo "==> Installing frontend dependencies..."
cd "$ROOT/frontend"
if command -v npm &>/dev/null; then
  npm install --silent
else
  echo "    WARNING: npm not found — skip frontend install"
fi

echo ""
echo "Setup complete. Next steps:"
echo "  1. Edit $ROOT/.env with OPENAI_API_KEY and SNOWFLAKE_* credentials"
echo "  2. Backend:  cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000"
echo "  3. Frontend: cd frontend && npm run dev"
echo "  4. Neo4j UI: http://localhost:7474  (neo4j / password)"
