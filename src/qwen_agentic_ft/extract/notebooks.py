from __future__ import annotations

import json
from pathlib import Path

from qwen_agentic_ft.extract.parser import CodeChunk, _collect_imports, _detect_patterns, _get_docstring
import ast


def extract_notebook_chunks(
    path: Path,
    repo_root: Path,
    repo_name: str,
    framework: str,
) -> list[CodeChunk]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rel = path.relative_to(repo_root).as_posix()
    chunks: list[CodeChunk] = []

    for cell_idx, cell in enumerate(payload.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", [])).strip()
        if len(source) < 80:
            continue
        try:
            tree = ast.parse(source, filename=f"{rel}:cell{cell_idx}")
        except SyntaxError:
            continue

        imports = _collect_imports(tree)
        patterns = _detect_patterns(source)
        chunks.append(
            CodeChunk(
                repo_name=repo_name,
                framework=framework,
                source_file=f"{rel}#cell{cell_idx}",
                chunk_type="notebook_cell",
                name=f"cell_{cell_idx}",
                code=source,
                docstring=_get_docstring(tree),
                imports=imports,
                patterns=patterns,
            )
        )

    return chunks
