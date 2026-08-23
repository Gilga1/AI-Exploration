#!/usr/bin/env python3
"""Cross-platform LoRA training entry point."""

from __future__ import annotations

import sys

from qwen_agentic_ft.train.cli import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
