from __future__ import annotations

from typing import Any

from app.llm.client import LLMClient


def apply_revision(
    llm: LLMClient,
    question: str,
    revision_hint: str,
    prior_selection: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Re-run reason step with user revision context — still constrained to candidates."""
    revised_question = f"{question}\n\nUser revision: {revision_hint}"
    selection = llm.reason(revised_question, candidates, metric_id=prior_selection.get("metric_id"))
    selection["revised"] = True
    selection["revision_hint"] = revision_hint
    return selection
