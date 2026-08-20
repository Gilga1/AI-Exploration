from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
REPOS_DIR = DATA_DIR / "repos"
PROCESSED_DIR = DATA_DIR / "processed"


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_repo_config(path: Path | None = None) -> dict[str, Any]:
    return load_yaml(path or CONFIG_DIR / "repos.yaml")


def load_extraction_config(path: Path | None = None) -> dict[str, Any]:
    return load_yaml(path or CONFIG_DIR / "extraction.yaml")
