"""Official few-shot strings from ysymyth/ReAct (prompts/prompts_naive.json)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

REACT_INSTRUCTION = """Solve a question answering task with interleaving Thought, Action, Observation steps. Thought can reason about the current situation, and Action can be three types:
(1) Search[entity], which searches the exact entity on Wikipedia and returns the first paragraph if it exists. If not, it will return some similar entities to search.
(2) Lookup[keyword], which returns the next sentence containing keyword in the current passage.
(3) Finish[answer], which returns the answer and finishes the task.
Here are some examples.
"""

COT_INSTRUCTION = """Solve a question answering task by having a Thought, then Finish with an answer. Thought can reason about the current situation. Here are some examples.
"""

ACT_INSTRUCTION = """Solve a question answering task with interleaving Action, Observation steps. Action can be three types:
(1) Search[entity], which searches the exact entity on Wikipedia and returns the first paragraph if it exists. If not, it will return some similar entities to search.
(2) Lookup[keyword], which returns the next sentence containing keyword in the current passage.
(3) Finish[answer], which returns the answer and finishes the task.
Here are some examples.
"""

STANDARD_INSTRUCTION = """Answer the question. Here are some examples.
"""


@lru_cache(maxsize=1)
def _prompt_dict() -> dict[str, str]:
    path = Path(__file__).resolve().parent.parent / "fixtures" / "prompts_naive.json"
    return json.loads(path.read_text(encoding="utf-8"))


def official_examples(key: str) -> str:
    return _prompt_dict()[key]


def react_prompt() -> str:
    return REACT_INSTRUCTION + official_examples("webthink_simple6")


def cot_prompt() -> str:
    return COT_INSTRUCTION + official_examples("cotqa_simple6")


def act_prompt() -> str:
    return ACT_INSTRUCTION + official_examples("webact_simple6")


def standard_prompt() -> str:
    return STANDARD_INSTRUCTION + official_examples("webqa_simple6")
