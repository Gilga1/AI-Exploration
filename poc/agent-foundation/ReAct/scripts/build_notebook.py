#!/usr/bin/env python3
"""Generate notebooks/react_from_scratch.ipynb."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

nb = nbf.v4.new_notebook()
nb.metadata["kernelspec"] = {
    "display_name": "Python 3",
    "language": "python",
    "name": "python3",
}

cells: list = []


def md(source: str) -> None:
    cells.append(nbf.v4.new_markdown_cell(source.strip() + "\n"))


def code(source: str) -> None:
    cells.append(nbf.v4.new_code_cell(source.strip() + "\n"))


md(
    """
# ReAct from scratch (Yao et al., 2022)

Study notebook for **ReAct: Synergizing Reasoning and Acting in Language Models** (ICLR 2023).

Read [`../PAPER_NOTES.md`](../PAPER_NOTES.md) first. Every experiment below calls a **live LLM via OpenRouter** — there are no scripted or hardcoded model outputs in this repo.

**Before you start**

```bash
cp .env.example .env   # set OPENROUTER_API_KEY and OPENROUTER_MODEL
```

Paper: https://arxiv.org/abs/2210.03629 · official code: https://github.com/ysymyth/ReAct
"""
)

md(
    """
## 0. Connect OpenRouter

Uses `OpenRouterLLM.from_env()` → chat completions, `temperature=0` (greedy), same stop tokens as the original `text-davinci-002` notebook.
"""
)

code(
    """
from pathlib import Path
import sys

ROOT = Path.cwd()
if ROOT.name == "notebooks":
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

from react_foundations.evaluate import evaluate_mini, run_example
from react_foundations.llm import OpenRouterLLM
from react_foundations.loop import ReactAgent
from react_foundations.wiki import LiveWikipediaEnv, LocalWikiEnv, load_hotpot_mini

llm = OpenRouterLLM.from_env()
print("model:", llm.model)
print("mini-set size:", len(load_hotpot_mini()))
"""
)

md(
    """
## 1. Wikipedia tools (no LLM)

Three actions: `search[entity]`, `lookup[keyword]`, `finish[answer]`. Deliberately weaker than RAG — reformulation happens in language during ReAct.
"""
)

code(
    """
env = LocalWikiEnv.from_fixture()
env.reset()

for action in (
    "Search[Arthur's Magazine]",
    "Search[First for Women]",
):
    obs = env.step(action).observation
    print(action, "→", obs[:120], "...\\n")

env.step("Search[Milhouse]")
print("lookup →", env.step("Lookup[named after]").observation[:120])
print("similar on miss →", env.step("Search[Sistine]").observation[:120])
"""
)

md(
    """
## 2. Figure 1 question — ReAct (live LLM, local wiki)

> Which magazine was started first, Arthur's Magazine or First for Women?

Gold: **Arthur's Magazine**. Read the trace: do observations contain 1844 and 1989 before `Finish`?
"""
)

code(
    """
question = "Which magazine was started first, Arthur's Magazine or First for Women?"
gold = "Arthur's Magazine"

react = run_example(question, gold, "react", llm)
print("EM:", react.em, "| answer:", react.answer, "| calls:", react.n_calls, "| tag:", react.failure_tag)
for i, step in enumerate(react.steps, start=1):
    print(f"Thought {i}: {step.thought}")
    print(f"Action {i}: {step.action}")
    print(f"Observation {i}: {step.observation[:200]}")
    print()
"""
)

md(
    """
## 3. Same question — Act vs CoT (live LLM)

**Act** — tools only, no thoughts. Does the model search entity names or paste the whole question?

**CoT** — no Wikipedia. Does the model hallucinate years, or get lucky from memory?
"""
)

code(
    """
act_result = run_example(question, gold, "act", llm)
print("Act EM:", act_result.em, "answer:", act_result.answer, "tag:", act_result.failure_tag)
for i, step in enumerate(act_result.steps, start=1):
    print(f"Action {i}: {step.action}")
    print(f"Observation {i}: {step.observation[:160]}")
print()

cot_result = run_example(question, gold, "cot", llm)
print("CoT EM:", cot_result.em, "answer:", cot_result.answer, "tag:", cot_result.failure_tag)
print("Thought:", (cot_result.steps[0].thought or "")[:400])
"""
)

md(
    """
## 4. Mini benchmark — four methods, your model

Eight public multi-hop questions, local wiki, execution-based EM / F1. Scores are **your** baseline, not Table 1 (PaLM-540B, 500 dev).
"""
)

code(
    """
rows = []
for method in ("standard", "cot", "act", "react"):
    summary = evaluate_mini(method, llm)
    rows.append(
        {
            "method": method,
            "n": summary["n"],
            "EM": round(summary["em"], 3),
            "F1": round(summary["f1"], 3),
            "failures": summary["failure_tags"] or "—",
        }
    )

print(f"{'method':<10} {'n':>3} {'EM':>6} {'F1':>6}  failures")
for row in rows:
    print(f"{row['method']:<10} {row['n']:>3} {row['EM']:>6.3f} {row['F1']:>6.3f}  {row['failures']}")

print()
print("Paper Table 1 (calibration only): Standard 28.7 | CoT 29.4 | Act 25.7 | ReAct 27.4")
"""
)

md(
    """
## 5. Per-question ReAct traces

Inspect failures: `search_result_error` vs `reasoning_error` vs `label_ambiguity` (Table 2 style).
"""
)

code(
    """
for task in load_hotpot_mini():
    result = run_example(task.question, task.answer, "react", llm)
    actions = " → ".join(step.action for step in result.steps)
    print(f"[{'PASS' if result.em else 'FAIL'}] {task.example_id}")
    print(f"  Q: {task.question}")
    print(f"  A: {result.answer!r}  gold={task.answer!r}  tag={result.failure_tag}")
    print(f"  {actions}")
    print()
"""
)

md(
    """
## 6. Live Wikipedia + ReAct (network)

Same loop, real `en.wikipedia.org`. Start with **one** question — latency and noise are part of the experiment.
"""
)

code(
    """
live_env = LiveWikipediaEnv()
task = load_hotpot_mini()[1]  # iPhone / Cupertino hop
agent = ReactAgent(llm, live_env, method="react")
result = agent.run(task.question, gold=task.answer)
print("Q:", task.question)
print("EM:", result.em, "answer:", result.answer, "tag:", result.failure_tag)
for step in result.steps:
    print(step.action, "→", step.observation[:100].replace("\\n", " "))
"""
)

md(
    """
## 7. Intuition checks

1. Why can ReAct EM lose to CoT on HotpotQA and still be more trustworthy?
2. Why is swapping in a strong retriever a confounding change?
3. When would you use sparse thoughts (ALFWorld) vs dense (HotpotQA)?
4. What does finetuning on correct *traces* teach that finetuning CoT does not?

Next paper: **Reflexion** — self-critique between episodes.
"""
)

nb.cells = cells
out = Path(__file__).resolve().parent.parent / "notebooks" / "react_from_scratch.ipynb"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(nbf.writes(nb), encoding="utf-8")
print("wrote", out)
