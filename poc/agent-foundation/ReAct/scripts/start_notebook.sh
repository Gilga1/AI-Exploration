#!/usr/bin/env bash
# Launch Jupyter for react_from_scratch.ipynb (from repo: poc/agent-foundation/ReAct)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck source=/dev/null
source .venv/bin/activate
pip install -q -e ".[dev,notebook]"
echo "Open: http://127.0.0.1:8888/notebooks/notebooks/react_from_scratch.ipynb"
jupyter notebook --no-browser --ip=127.0.0.1 --port=8888 --allow-root notebooks/react_from_scratch.ipynb
