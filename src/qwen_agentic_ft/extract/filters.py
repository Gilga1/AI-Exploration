from __future__ import annotations

import ast
import re

from qwen_agentic_ft.extract.parser import CodeChunk


def has_agent_import(imports: list[str], markers: list[str]) -> bool:
    joined = " ".join(imports).lower()
    return any(marker in joined for marker in markers)


def contains_deprecated(code: str, deprecated_patterns: list[str]) -> bool:
    return any(pattern in code for pattern in deprecated_patterns)


def passes_syntax_check(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def validate_chunk(
    chunk: CodeChunk,
    *,
    min_code_chars: int,
    max_code_chars: int,
    required_import_markers: list[str],
    deprecated_patterns: list[str],
) -> tuple[bool, str | None]:
    if len(chunk.code) < min_code_chars:
        return False, "code_too_short"
    if len(chunk.code) > max_code_chars:
        return False, "code_too_long"
    if not passes_syntax_check(chunk.code):
        return False, "syntax_error"
    if not has_agent_import(chunk.imports, required_import_markers):
        return False, "missing_agent_import"
    if contains_deprecated(chunk.code, deprecated_patterns):
        return False, "deprecated_pattern"
    if re.search(r"(?i)(api_key|secret|password)\s*=\s*['\"][^'\"]+['\"]", chunk.code):
        return False, "possible_secret"
    return True, None
