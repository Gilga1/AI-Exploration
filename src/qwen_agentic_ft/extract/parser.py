from __future__ import annotations

import ast
import hashlib
import re
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path


@dataclass
class CodeChunk:
    repo_name: str
    framework: str
    source_file: str
    chunk_type: str
    name: str
    code: str
    docstring: str | None
    imports: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)


AGENT_PATTERNS: dict[str, re.Pattern[str]] = {
    "state_graph": re.compile(r"\bStateGraph\b"),
    "create_deep_agent": re.compile(r"\bcreate_deep_agent\b"),
    "create_agent": re.compile(r"\bcreate_agent\b"),
    "tool_decorator": re.compile(r"@tool\b"),
    "checkpointer": re.compile(r"\b(MemorySaver|SqliteSaver|checkpointer)\b"),
    "subagent": re.compile(r"\b(subagent|SubAgent|task)\b", re.I),
    "hitl": re.compile(r"\b(interrupt|human.in.the.loop|HITL)\b", re.I),
    "backend": re.compile(r"\b(Backend|FilesystemBackend)\b"),
}


def _collect_imports(tree: ast.AST) -> list[str]:
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.append(module)
    return imports


def _detect_patterns(code: str) -> list[str]:
    return [name for name, pattern in AGENT_PATTERNS.items() if pattern.search(code)]


def _get_docstring(node: ast.AST) -> str | None:
    doc = ast.get_docstring(node)
    if doc:
        return doc.strip()
    return None


def _matches_glob(path: Path, patterns: list[str]) -> bool:
    posix = path.as_posix()
    return any(fnmatch(posix, pattern) for pattern in patterns)


def _path_in_include(rel: str, include_paths: list[str]) -> bool:
    if not include_paths or include_paths == ["."]:
        return True
    for raw in include_paths:
        prefix = raw.strip("/")
        if not prefix or prefix == ".":
            return True
        if rel == prefix or rel.startswith(f"{prefix}/"):
            return True
    return False


def _should_skip_path(path: Path, repo_root: Path, repo_cfg: dict, defaults: dict) -> bool:
    rel = path.relative_to(repo_root).as_posix()
    include_paths = repo_cfg.get("include_paths", ["."])
    if not _path_in_include(rel, include_paths):
        return True

    for substring in defaults.get("exclude_path_substrings", []):
        if substring in rel:
            return True

    include_globs = repo_cfg.get("include_globs") or defaults.get("include_globs", ["**/*.py"])
    exclude_globs = repo_cfg.get("exclude_globs") or defaults.get("exclude_globs", [])
    if not _matches_glob(path, include_globs):
        return True
    if _matches_glob(path, exclude_globs):
        return True
    return False


def _extract_chunks_from_tree(
    tree: ast.AST,
    source: str,
    repo_name: str,
    framework: str,
    source_file: str,
) -> list[CodeChunk]:
    lines = source.splitlines()
    chunks: list[CodeChunk] = []

    module_imports = _collect_imports(tree)
    module_doc = _get_docstring(tree)

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = node.lineno - 1
            end = node.end_lineno or node.lineno
            code = "\n".join(lines[start:end]).strip()
            if len(code) < 80:
                continue
            chunk_imports = list(dict.fromkeys(module_imports + _collect_imports(node)))
            chunks.append(
                CodeChunk(
                    repo_name=repo_name,
                    framework=framework,
                    source_file=source_file,
                    chunk_type=type(node).__name__,
                    name=node.name,
                    code=code,
                    docstring=_get_docstring(node) or module_doc,
                    imports=chunk_imports,
                    patterns=_detect_patterns(code),
                )
            )

    if not chunks and len(source.strip()) >= 80:
        chunks.append(
            CodeChunk(
                repo_name=repo_name,
                framework=framework,
                source_file=source_file,
                chunk_type="module",
                name=Path(source_file).stem,
                code=source.strip(),
                docstring=module_doc,
                imports=module_imports,
                patterns=_detect_patterns(source),
            )
        )

    return chunks


def iter_repo_source_files(repo_root: Path, repo_cfg: dict, defaults: dict) -> list[Path]:
    files: list[Path] = []
    include_globs = repo_cfg.get("include_globs") or defaults.get("include_globs", ["**/*.py"])
    seen: set[Path] = set()
    for pattern in include_globs:
        for path in sorted(repo_root.glob(pattern)):
            if not path.is_file() or path in seen:
                continue
            if _should_skip_path(path, repo_root, repo_cfg, defaults):
                continue
            seen.add(path)
            files.append(path)
    return files


def extract_chunks_from_file(
    path: Path,
    repo_root: Path,
    repo_name: str,
    framework: str,
) -> list[CodeChunk]:
    source = path.read_text(encoding="utf-8", errors="ignore")
    tree = ast.parse(source, filename=str(path))
    rel = path.relative_to(repo_root).as_posix()
    return _extract_chunks_from_tree(tree, source, repo_name, framework, rel)


def normalize_code(code: str, strip_comments: bool = True) -> str:
    if strip_comments:
        code = re.sub(r"#.*$", "", code, flags=re.MULTILINE)
    code = re.sub(r"\s+", " ", code).strip()
    return code


def code_hash(code: str) -> str:
    return hashlib.sha256(normalize_code(code).encode()).hexdigest()[:16]
