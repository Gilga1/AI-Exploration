#!/usr/bin/env python3
"""Cross-platform data extraction entry point."""

from __future__ import annotations

import sys

from qwen_agentic_ft.cli import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
