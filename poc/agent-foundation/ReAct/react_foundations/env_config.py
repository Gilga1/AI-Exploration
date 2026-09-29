"""Load `.env` into os.environ (Jupyter / VS Code on Windows does not do this automatically)."""

from __future__ import annotations

import os
from pathlib import Path


def react_package_root() -> Path:
    """Directory containing pyproject.toml (…/poc/agent-foundation/ReAct)."""
    return Path(__file__).resolve().parent.parent


def dotenv_search_paths() -> list[Path]:
    """Places we look for `.env` (first existing file wins)."""
    paths: list[Path] = []
    explicit = os.environ.get("OPENROUTER_ENV_FILE") or os.environ.get("REACT_ENV_FILE")
    if explicit:
        paths.append(Path(explicit).expanduser())

    # Most reliable when the package is installed editable: always next to this source tree
    paths.append(react_package_root() / ".env")

    cwd = Path.cwd()
    if cwd.name.lower() == "notebooks":
        paths.append(cwd.parent / ".env")
    paths.append(cwd / ".env")

    for parent in [cwd, *cwd.parents]:
        candidate = parent / "poc" / "agent-foundation" / "ReAct" / ".env"
        if candidate.is_file():
            paths.append(candidate)
            break

    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved not in seen:
            seen.add(resolved)
            unique.append(path)
    return unique


def load_dotenv_file(path: Path, *, override: bool = False) -> bool:
    """Minimal .env parser (no third-party dependency). Handles UTF-8 BOM on Windows."""
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8-sig")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        if not override and os.environ.get(key):
            continue
        os.environ[key] = value
    return True


def load_project_dotenv() -> Path | None:
    """Load the first `.env` found. Returns the path loaded, or None."""
    for path in dotenv_search_paths():
        if path.is_file():
            load_dotenv_file(path)
            try:
                from dotenv import load_dotenv

                load_dotenv(path, override=False, encoding="utf-8-sig")
            except ImportError:
                pass
            return path
    return None


def dotenv_hint() -> str:
    checked = "\n  - ".join(str(p) for p in dotenv_search_paths())
    root_env = react_package_root() / ".env"
    return (
        "OPENROUTER_API_KEY / OPENROUTER_MODEL are missing after loading .env.\n\n"
        f"Checked paths:\n  - {checked}\n\n"
        f"Expected file: {root_env}\n"
        "Format (no spaces around =):\n"
        "  OPENROUTER_API_KEY=sk-or-v1-...\n"
        "  OPENROUTER_MODEL=openai/gpt-4o-mini\n\n"
        "Windows PowerShell (same session as Jupyter):\n"
        '  $env:OPENROUTER_API_KEY="sk-or-..."\n'
        '  $env:OPENROUTER_MODEL="openai/gpt-4o-mini"\n\n'
        "Then restart the notebook kernel."
    )


def debug_env_status() -> dict[str, str | bool]:
    """Safe diagnostics for notebook cell 0 (does not print secrets)."""
    loaded = load_project_dotenv()
    key = os.environ.get("OPENROUTER_API_KEY")
    model = os.environ.get("OPENROUTER_MODEL")
    return {
        "env_file_loaded": str(loaded) if loaded else "",
        "package_root": str(react_package_root()),
        "cwd": str(Path.cwd()),
        "expected_env": str(react_package_root() / ".env"),
        "expected_env_exists": (react_package_root() / ".env").is_file(),
        "api_key_set": bool(key and key.strip() and not key.strip().startswith("sk-or-...")),
        "api_key_prefix": (key[:12] + "...") if key and len(key) > 12 else "",
        "model_set": bool(model and model.strip()),
        "model": model or "",
    }
