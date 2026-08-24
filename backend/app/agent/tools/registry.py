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
    """Evaluate a tiny arithmetic expression via a safe AST walk (M5 fix).

    Only numeric literals and +, -, *, /, //, %, ** and unary +/- are allowed;
    anything else (names, calls, attribute access) is rejected before
    evaluation, so there is no eval() surface at all.
    """

    import ast
    import operator as op

    allowed_binops = {
        ast.Add: op.add,
        ast.Sub: op.sub,
        ast.Mult: op.mul,
        ast.Div: op.truediv,
        ast.FloorDiv: op.floordiv,
        ast.Mod: op.mod,
        ast.Pow: op.pow,
    }
    allowed_unaryops = {ast.UAdd: op.pos, ast.USub: op.neg}

    def _eval_node(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval_node(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in allowed_binops:
            return allowed_binops[type(node.op)](_eval_node(node.left), _eval_node(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in allowed_unaryops:
            return allowed_unaryops[type(node.op)](_eval_node(node.operand))
        raise ValueError(f"unsupported expression element: {type(node).__name__}")

    # Extract the arithmetic substring: the agent passes whole questions like
    # "calculate 144/12", and ast.parse rejects leading words. Take the
    # longest run of expression characters in the input.
    import re as _re

    runs = _re.findall(r"[\d\s+\-*/().%]+", expression)
    sanitized = max(runs, key=len).strip() if runs else ""
    if not sanitized:
        return "error: empty expression"
    try:
        tree = ast.parse(sanitized, mode="eval")
        return str(_eval_node(tree))
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
