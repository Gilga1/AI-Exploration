#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ -f .venv/bin/python ]]; then
  .venv/bin/python scripts/train.py "$@"
else
  python3 scripts/train.py "$@"
fi
