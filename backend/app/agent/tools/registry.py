"""Tool registry for the Phase 4 agent loop.

Tools are deliberately small and deterministic so the offline demo behaves the
same in CI. Each tool declares its name, description, and a pure callable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.rag.corpus import CORPUS


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    func: Callable[[str], str]


def _doc_lookup(query: str) -> str:
    """Return corpus documents whose ids or content mention the query terms."""

    terms = {token.strip("?.!, ").lower() for token in query.split()} - {
        "the", "a", "an", "of", "for", "to", "and", "in", "is", "what",
    }
    hits = [
        f"[{doc.metadata['id']}]\n{doc.page_content}"
        for doc in CORPUS
        if terms & {token.strip("?.!, ").lower() for token in doc.page_content.split()}
        or doc.metadata["id"].lower() in query.lower()
    ]
    return "\n\n".join(hits) if hits else "no matching documents"


def _word_count(text: str) -> str:
    return f"word_count={len(text.split())}"


def _calculator(expression: str) -> str:
    """Evaluate a tiny arithmetic expression (digits/operators only)."""

    sanitized = "".join(ch for ch in expression if ch in "0123456789+-*/(). ")
    if not sanitized:
        return "error: empty expression"
    try:
        return str(eval(sanitized, {"__builtins__": {}}, {}))  # noqa: S307 - sandboxed charset
    except Exception as exc:
        return f"error: {exc}"


REGISTRY: dict[str, Tool] = {
    tool.name: tool
    for tool in [
        Tool(
            name="document_lookup",
            description="Search the fixed Acme Orbit corpus for documents matching a query.",
            func=_doc_lookup,
        ),
        Tool(
            name="calculator",
            description="Evaluate a simple arithmetic expression.",
            func=_calculator,
        ),
        Tool(
            name="word_count",
            description="Count words in the provided text.",
            func=_word_count,
        ),
    ]
}


def get_tool(name: str) -> Tool | None:
    return REGISTRY.get(name)


def list_tools() -> list[dict[str, str]]:
    return [{"name": t.name, "description": t.description} for t in REGISTRY.values()]
