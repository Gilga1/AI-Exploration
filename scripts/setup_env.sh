#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"

echo ""
echo "Agent Harness dependencies installed."
echo "Run tests:  pytest -q"
echo "Start API:  harness-serve"
