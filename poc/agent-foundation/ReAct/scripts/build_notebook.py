#!/usr/bin/env python3
"""Generate notebooks/react_from_scratch.ipynb."""

from __future__ import annotations

import json
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

Reproduction notebook for **ReAct: Synergizing Reasoning and Acting in Language Models** (ICLR 2023).

This notebook is meant to be read *with* [`../PAPER_NOTES.md`](../PAPER_NOTES.md). The notes are the close reading. The cells below are the experiment: a real Thought → Action → Observation loop, the paper's Wikipedia action space, and execution-based HotpotQA metrics.

**Rules for this study**

- No LangChain / LangGraph / "agents" SDK.
- Score answers with exact match / token F1 against gold labels, not an LLM judge.
- Default path uses a **scripted** language model so the notebook runs without API keys. The loop, environment, and metrics are the real algorithm. Swap in `OpenAICompatibleLLM` when you want a live model.

Paper: https://arxiv.org/abs/2210.03629 · official code: https://github.com/ysymyth/ReAct
"""
)

md(
    """
## 0. What you should walk away knowing

1. ReAct is an **augmented action space** `$\\hat{\\mathcal{A}} = \\mathcal{A} \\cup \\mathcal{L}$`, not a product architecture.
2. Thoughts write the context; actions write the environment; observations come back as text.
3. On knowledge tasks the distinctive CoT failure is **hallucination**; the distinctive ReAct failure is **bad search + rigid traces**.
4. ReAct alone is *not* the paper's best HotpotQA prompting method. ReAct ⇄ CoT-SC backoff is.
5. The loop you are about to run is the same shape as an MCP tool loop. Everything after this paper (Reflexion, tool-calling APIs, Deep Agents) is a variation on context writes vs environment writes.
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
from react_foundations.llm import ScriptedLLM
from react_foundations.loop import ReactAgent
from react_foundations.metrics import exact_match, f1_score
from react_foundations.policies import COT_HALLUCINATED_MAGAZINES, WEAK_ACT_SCRIPTS
from react_foundations.wiki import LiveWikipediaEnv, LocalWikiEnv, load_hotpot_mini

print("package root:", ROOT)
print("mini-set size:", len(load_hotpot_mini()))
"""
)

md(
    """
## 1. The claim, in one figure

Four prompting methods on the same HotpotQA-style question (paper Figure 1):

| Method | Emits | Grounded in Wikipedia? |
|---|---|---|
| Standard | answer | no |
| CoT | thoughts + answer | no (parametric facts) |
| Act | search/lookup/finish | yes |
| **ReAct** | thought + search/lookup/finish + observation, repeated | yes |

Running example:

> Which magazine was started first, Arthur's Magazine or First for Women?

Gold: **Arthur's Magazine** (1844 vs 1989). CoT can get this right *or* invent the years. ReAct is supposed to refuse to invent them and go look.
"""
)

md(
    """
## 2. Formal loop

At step `$t$` the policy conditions on context `$c_t$`. A thought does not call Wikipedia; it only extends `$c_t$`. An action does.

For HotpotQA the paper uses **dense** thoughts (one thought per action), greedy decoding, and a **7-step** cap. That is what `ReactAgent` implements.

The original notebook asks the model to continue after `Thought {i}:` and stops at `Observation {i}:`, then splits on `Action {i}:`. If the split fails, it issues a second call starting at `Action {i}:`. We keep that recovery path (`n_badcalls`).
"""
)

code(
    """
from react_foundations.loop import ReactAgent
import inspect

print(inspect.getsource(ReactAgent.run))
"""
)

md(
    """
## 3. Wikipedia tools (paper §3.1)

Three actions only:

- `search[entity]` → first five sentences, or similar titles
- `lookup[keyword]` → next sentence containing the keyword (Ctrl+F)
- `finish[answer]` → terminate

Deliberately weaker than RAG. Query reformulation has to happen in language.
"""
)

code(
    """
env = LocalWikiEnv.from_fixture()
env.reset()

obs = env.step("Search[Arthur's Magazine]").observation
print("search[Arthur's Magazine]\\n", obs, "\\n")

obs = env.step("Search[First for Women]").observation
print("search[First for Women]\\n", obs, "\\n")

env.step("Search[Milhouse]")
obs = env.step("Lookup[named after]").observation
print("lookup[named after] on Milhouse\\n", obs, "\\n")

miss = env.step("Search[Sistine]").observation
print("miss + similar titles\\n", miss)
"""
)

md(
    """
## 4. Replay Figure 1 with the real loop

The language model is scripted. Every Thought/Action below is a continuation the loop would have demanded from GPT-3 / PaLM. Observations come from the local wiki environment.
"""
)

code(
    """
question = "Which magazine was started first, Arthur's Magazine or First for Women?"
gold = "Arthur's Magazine"

react = run_example(question, gold, "react")
print("EM:", react.em, "| answer:", react.answer, "| calls:", react.n_calls)
print()
for i, step in enumerate(react.steps, start=1):
    print(f"Thought {i}: {step.thought}")
    print(f"Action {i}: {step.action}")
    print(f"Observation {i}: {step.observation}")
    print()
"""
)

md(
    """
## 5. Why thoughts are not optional: Act-only vs ReAct

Strip the thoughts, keep the tools. A weak Act policy searches the raw question (no entity decomposition) and finishes with a guess — the paper's "acting without reasoning" failure, compressed.
"""
)

code(
    """
env = LocalWikiEnv.from_fixture()
weak_act = ReactAgent(ScriptedLLM(list(WEAK_ACT_SCRIPTS[question])), env, method="act")
act_result = weak_act.run(question, gold=gold)

print("Act EM:", act_result.em, "| answer:", act_result.answer)
for i, step in enumerate(act_result.steps, start=1):
    print(f"Action {i}: {step.action}")
    print(f"Observation {i}: {step.observation}")
    print()
print("failure tag:", act_result.failure_tag)
"""
)

md(
    """
## 6. Why actions are not optional: CoT hallucination

Same question, no Wikipedia. The scripted CoT invents a 19th-century origin for *First for Women* and answers backwards. This is Table 2's dominant CoT failure (56% of CoT errors = hallucination). ReAct's hallucination rate in that study: 0%.
"""
)

code(
    """
env = LocalWikiEnv.from_fixture()
cot = ReactAgent(ScriptedLLM([COT_HALLUCINATED_MAGAZINES]), env, method="cot")
cot_result = cot.run(question, gold=gold)

print("CoT thought:\\n", cot_result.steps[0].thought)
print()
print("CoT answer:", cot_result.answer, "| gold:", gold, "| EM:", cot_result.em)
print("failure tag:", cot_result.failure_tag, "(paper Table 2)")
print("ReAct was grounded in observations 1844 and 1989; CoT never left parametric memory.")
"""
)

md(
    """
## 7. Mini benchmark (public multi-hop set)

Eight questions in HotpotQA's multi-hop style, including the paper example. Gold labels are short strings. Scoring is the official HotpotQA normalize + EM / token F1 from the ReAct `wrappers.py`.

This is **not** the paper's 500-dev PaLM run. It is a unit of research hygiene: same tasks, four methods, execution-based scoring. Scripted ReAct/CoT/Standard here are *competent* traces so you can see the loop and the metric. The interesting contrast is the hallucinated CoT and weak Act on question 1.
"""
)

code(
    """
rows = []
for method in ("standard", "cot", "act", "react"):
    summary = evaluate_mini(method)
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
print("Paper Table 1 (PaLM-540B, 500 HotpotQA dev, for calibration):")
print("Standard 28.7 | CoT 29.4 | Act 25.7 | ReAct 27.4 | ReAct→CoT-SC 35.1 | supervised SoTA 67.5")
"""
)

md(
    """
## 8. Per-question ReAct traces (local wiki)

Every finish is checked with `exact_match`. If you later plug in a live LLM, keep this cell and watch EM drop — that drop is the experiment.
"""
)

code(
    """
tasks = load_hotpot_mini()
for task in tasks:
    result = run_example(task.question, task.answer, "react")
    actions = " → ".join(step.action for step in result.steps)
    print(f"[{'PASS' if result.em else 'FAIL'}] {task.example_id}")
    print(f"  Q: {task.question}")
    print(f"  A: {result.answer!r}  gold={task.answer!r}  F1={result.f1:.2f}")
    print(f"  {actions}")
    print()
"""
)

md(
    """
## 9. Live Wikipedia (optional, network)

Same `search` / `lookup` mechanics as `wikienv.py` in the official repo. This does not need an LLM: you are testing that the *environment* matches the paper.
"""
)

code(
    """
try:
    live = LiveWikipediaEnv()
    live.reset()
    obs = live.step("Search[iPhone]").observation
    print("Live search[iPhone]:")
    print(obs[:800])
    print()
    look = live.step("Lookup[Apple]").observation
    print("Live lookup[Apple]:")
    print(look[:500])
except Exception as exc:
    print("Live Wikipedia skipped:", type(exc).__name__, exc)
"""
)

md(
    """
## 10. How to attach a real LLM (OpenRouter)

The original code used `text-davinci-002` **completions** with `stop=["\\nObservation i:"]`. On OpenRouter, use **chat** models via `OpenRouterLLM` — one user message per step, greedy decoding (`temperature=0`).

```python
from react_foundations.llm import OpenRouterLLM
from react_foundations.loop import ReactAgent
from react_foundations.wiki import LiveWikipediaEnv, load_hotpot_mini

# export OPENROUTER_API_KEY=...  OPENROUTER_MODEL=openai/gpt-4o-mini
llm = OpenRouterLLM.from_env()
agent = ReactAgent(llm, LiveWikipediaEnv(), method="react")
task = load_hotpot_mini()[0]
print(agent.run(task.question, gold=task.answer))
```

CLI: `python scripts/run_live_eval.py --method react --wiki live --limit 1`

Do not report scores as Table 1 unless the model, shot count, decoding, and 500-dev sample match. Report them as *your* baseline.

When you run a live model, tag failures with `{reasoning_error, search_result_error, hallucination, label_ambiguity, no_answer}` — Table 2, not MAST (MAST is multi-agent, later).
"""
)

md(
    """
## 11. Intuition checks (answer these without scrolling up)

1. Why can ReAct EM *lose* to CoT on HotpotQA and still be the more trustworthy method?
2. Why is a strong retriever a confounding change if your goal is to study ReAct?
3. Dense vs sparse thoughts: which schedule is ALFWorld, and why would an MCP agent copy it?
4. What does finetuning on 3,000 *correct-answer* traces teach that finetuning CoT does not?
5. Where would ReAct → CoT backoff show up in an MCP host?

Sketch answers: (1) Table 2 — CoT's EM includes false positives; ReAct is grounded. (2) The weak Wikipedia API *forces* language-side reformulation; a strong retriever hides that. (3) Sparse; long tool horizons should not spend a thought on every call. (4) A general skill of using an API, not memorized facts. (5) If the tool loop hits a step cap or empty observations, answer from parameters with self-consistency rather than inventing more calls.

Next: **Reflexion** (Shinn et al., 2023) — verbal self-critique *between episodes*.
"""
)

nb.cells = cells
out = Path(__file__).resolve().parent.parent / "notebooks" / "react_from_scratch.ipynb"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(nbf.writes(nb), encoding="utf-8")
print("wrote", out)
