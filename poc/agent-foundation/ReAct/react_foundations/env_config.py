"""Load `.env` into os.environ (Jupyter on Windows does not do this automatically)."""

from __future__ import annotations

import os
from pathlib import Path


def react_package_root() -> Path:
    return Path(__file__).resolve().parent.parent


def dotenv_search_paths() -> list[Path]:
    """Places we look for `.env` (first match wins)."""
    paths: list[Path] = []
    explicit = os.environ.get("OPENROUTER_ENV_FILE") or os.environ.get("REACT_ENV_FILE")
    if explicit:
        paths.append(Path(explicit).expanduser())

    cwd = Path.cwd()
    paths.append(cwd / ".env")
    if cwd.name.lower() == "notebooks":
        paths.append(cwd.parent / ".env")

    root = react_package_root()
    paths.append(root / ".env")

    # Repo root when .env was placed next to AI-Exploration checkout
    for parent in [cwd, *cwd.parents]:
        if (parent / "poc" / "agent-foundation" / "ReAct" / ".env").is_file():
            paths.append(parent / "poc" / "agent-foundation" / "ReAct" / ".env")
            break

    # De-dupe while preserving order
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(path)
    return unique


def load_project_dotenv() -> Path | None:
    """Load the first `.env` found. Returns the path loaded, or None."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return None

    for path in dotenv_search_paths():
        if path.is_file():
            load_dotenv(path, override=False, encoding="utf-8")
            return path
    return None


def dotenv_hint() -> str:
    checked = ", ".join(str(p) for p in dotenv_search_paths())
    return (
        "Set OPENROUTER_API_KEY and OPENROUTER_MODEL.\n"
        f"Checked for .env at: {checked}\n"
        "Windows (PowerShell): $env:OPENROUTER_API_KEY='sk-or-...'; $env:OPENROUTER_MODEL='openai/gpt-4o-mini'\n"
        "Or put a .env file in poc/agent-foundation/ReAct/ (same folder as .env.example) and "
        "pip install -e '.[dev]' so python-dotenv is installed."
    )
