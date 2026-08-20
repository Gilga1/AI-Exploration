#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"

echo ""
echo "Base extraction dependencies installed."
echo "For training on a CUDA machine, also run:"
echo "  pip install -e '.[train]'"
echo "For agent-stack validation:"
echo "  pip install -e '.[agents]'"
