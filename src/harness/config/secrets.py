from __future__ import annotations

import os
import re
from typing import Any

_ENV_PATTERN = re.compile(r"\$\{env:([^}]+)\}")
_SECRET_PATTERN = re.compile(r"\$\{secret:([^}]+)\}")


def resolve_value(value: str) -> str:
    def _env_replace(match: re.Match[str]) -> str:
        return os.environ.get(match.group(1), "")

    def _secret_replace(match: re.Match[str]) -> str:
        key = match.group(1).upper().replace("-", "_")
        return os.environ.get(f"HARNESS_SECRET_{key}", "")

    resolved = _SECRET_PATTERN.sub(_secret_replace, value)
    return _ENV_PATTERN.sub(_env_replace, resolved)


def resolve_tree(data: Any) -> Any:
    if isinstance(data, str):
        return resolve_value(data)
    if isinstance(data, dict):
        return {key: resolve_tree(value) for key, value in data.items()}
    if isinstance(data, list):
        return [resolve_tree(item) for item in data]
    return data
