#!/usr/bin/env python3
"""Generate notebooks/react_from_scratch.ipynb with teaching markdown before each code cell."""

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


# --- Title -------------------------------------------------------------------

md(
    """
# ReAct from scratch — interactive study (Yao et al., 2022)

**Goal:** build intuition for *ReAct* — interleaving **language reasoning** with **tool actions** — without LangChain.

| Resource | Role |
|----------|------|
| [`PAPER_NOTES.md`](../PAPER_NOTES.md) | Formal close reading (read alongside this notebook) |
| `fixtures/prompts_naive.json` | **Official 6-shot demos** copied from [ysymyth/ReAct](https://github.com/ysymyth/ReAct) |
| `react_foundations/loop.py` | The actual agent loop (~200 lines) |
| **This notebook** | You run experiments; every model output comes from **your OpenRouter LLM** |

**Setup (once):** copy `.env.example` → `.env` in `poc/agent-foundation/ReAct/`, set `OPENROUTER_API_KEY` and `OPENROUTER_MODEL`, then `pip install -e ".[dev,notebook]"`. Restart the kernel after editing `.env`.

Paper: https://arxiv.org/abs/2210.03629
"""
)

# --- Cell 0: setup -----------------------------------------------------------

md(
    """
### What this cell does

1. Finds the project root (parent of `notebooks/` if you opened the `.ipynb` from there).
2. Loads **`.env`** so `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` reach `os.environ` (Jupyter does not do this automatically on Windows).
3. Constructs **`OpenRouterLLM`** — one HTTP **chat completion** per loop step, `temperature=0` (greedy, like the paper).

### Mental model

You are not “calling an agent API.” You are repeatedly:

1. Building a **single growing text prompt** (instructions + 6 examples + your question + past steps).
2. Asking the model to **continue** that text (e.g. after `Thought 1:`).
3. **Parsing** the continuation into Thought / Action, executing the Action on Wikipedia, appending **Observation** back into the prompt.

That is the same shape as modern tool-calling — only the format is 2022-style plain text instead of JSON tools.
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
from react_foundations.env_config import debug_env_status, load_dotenv_file, load_project_dotenv

env_path = ROOT / ".env"
if env_path.is_file():
    load_dotenv_file(env_path)
else:
    load_project_dotenv()

for key, value in debug_env_status().items():
    print(f"{key}: {value}")

llm = OpenRouterLLM.from_env()
print("model:", llm.model)
print("mini-set size:", len(load_hotpot_mini()))
"""
)

# --- Prompt inspection -------------------------------------------------------

md(
    """
### Where do the “prompts” come from?

ReAct is **few-shot prompted**. Before your question, the model always sees:

1. A short **instruction paragraph** (what Thought / Action / Observation mean).
2. **Six full worked examples** — real multi-hop Wikipedia trajectories from the authors’ repo (`webthink_simple6`, etc.).
3. Then **`Question: <yours>`** and the loop continues.

There is **no fine-tuned weights** in this notebook — only text in context. The 6 shots teach the *format* and *skill* of using `Search` / `Lookup` / `Finish`.

| Method | Instruction + few-shot key in `prompts_naive.json` | Uses Wikipedia during the run? |
|--------|---------------------------------------------------|--------------------------------|
| **react** | `REACT_INSTRUCTION` + `webthink_simple6` | Yes — after each Action |
| **act** | `ACT_INSTRUCTION` + `webact_simple6` | Yes — no Thought lines |
| **cot** | `COT_INSTRUCTION` + `cotqa_simple6` | **No** — only `Thought` then `Finish` |
| **standard** | `STANDARD_INSTRUCTION` + `webqa_simple6` | **No** — direct answer |

The next cell prints the **instruction** and the **start of example 1** so you can see exactly what prefixes every run.
"""
)

code(
    """
from react_foundations.prompts import (
    REACT_INSTRUCTION,
    react_prompt,
    act_prompt,
    cot_prompt,
    standard_prompt,
)

print("=== ReAct instruction (always at top of prompt) ===")
print(REACT_INSTRUCTION)
print("... + 6 full trajectories from webthink_simple6 (~tens of KB) ...")
print(f"Total react prefix length: {len(react_prompt())} characters\\n")

print("=== First 1200 chars of full ReAct prefix ===")
print(react_prompt()[:1200])
print("\\n[truncated]\\n")

print("Prefix lengths (chars):", {
    "react": len(react_prompt()),
    "act": len(act_prompt()),
    "cot": len(cot_prompt()),
    "standard": len(standard_prompt()),
})
"""
)

# --- Wikipedia env -----------------------------------------------------------

md(
    """
### The “environment” = a fake Wikipedia API

The paper deliberately uses a **weak** retriever (search box + Ctrl+F), not vector RAG. That forces the **language model** to:

- pick **entity names** for `Search[entity]` (not paste the whole question),
- use `Lookup[keyword]` to find the next sentence **on the current page** (second hop).

**Actions (only three):**

| Action | Effect |
|--------|--------|
| `Search[entity]` | Open page; return ~first paragraph (local JSON or live wiki) |
| `Lookup[keyword]` | Next sentence containing `keyword` on the **current** page |
| `Finish[answer]` | End episode; `answer` is scored with HotpotQA **EM / F1** |

This cell **does not call the LLM**. It only shows how observations look when actions succeed, fail, or suggest similar titles.
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

# --- ReAct loop explainer ----------------------------------------------------

md(
    """
### One ReAct step (what the code does per LLM call)

For method=`react`, after the few-shot prefix and `Question: ...`, step `i` works like this:

```
prompt ends with:  ... Question: <q> \\n Thought 1: ... Observation 1: ... Thought 2:
LLM continues:     <reasoning> \\n Action 2: Search[First for Women]
stop sequence:     \\nObservation 2:   (model must NOT hallucinate the observation)
env executes:      Search[First for Women]  →  observation text appended to prompt
```

Important details from `ReactAgent.run`:

- **Max 7 steps** on HotpotQA (paper setting).
- **Thoughts never touch Wikipedia** — only Actions do (thoughts are extra tokens in context).
- If the model forgets `Action i:`, the code makes a **second** LLM call (counts as `n_badcalls`).
- **`result.transcript`** holds the full prompt+generations (useful for debugging).

### Figure 1 question

> Which magazine was started first, Arthur's Magazine or First for Women?

**Gold answer:** `Arthur's Magazine` (1844 vs 1989).

**What to look for in the output:** before `Finish[...]`, do **Observations** contain the founding years from the wiki — not from model memory?
"""
)

code(
    """
question = "Which magazine was started first, Arthur's Magazine or First for Women?"
gold = "Arthur's Magazine"

react = run_example(question, gold, "react", llm)
print("EM:", react.em, "| answer:", react.answer, "| LLM calls:", react.n_calls, "| tag:", react.failure_tag)
for i, step in enumerate(react.steps, start=1):
    print(f"Thought {i}: {step.thought}")
    print(f"Action {i}: {step.action}")
    print(f"Observation {i}: {step.observation[:200]}")
    print()

# Peek at tail of full prompt the model saw (last ~1500 chars)
print("=== tail of transcript (what context looked like at the end) ===")
print(react.transcript[-1500:])
"""
)

# --- Act vs CoT --------------------------------------------------------------

md(
    """
### Same question, two ablations (paper Figure 1 & Table 2)

**Act-only** (`method="act"`)

- Prompt = `ACT_INSTRUCTION` + `webact_simple6` (examples **without** Thought lines).
- Same Wikipedia tools, but the model must choose actions **without** an explicit reasoning channel.
- Typical failure mode: `Search[<entire question>]` → “Could not find …” → guess → **`search_result_error`**.

**Chain-of-Thought** (`method="cot"`)

- Prompt = `COT_INSTRUCTION` + `cotqa_simple6` (thoughts + `Finish`, **no** Search/Lookup in the loop).
- The model answers from **parametric memory** only.
- Can sound confident and still be wrong → we tag **`hallucination`** when EM fails (CoT has no observations to ground on).

**ReAct** sits in the middle: thoughts **plan**; actions **ground**; observations **constrain** the next thought.

Run both below and compare traces to the ReAct cell above.
"""
)

code(
    """
act_result = run_example(question, gold, "act", llm)
print("=== ACT ===")
print("EM:", act_result.em, "answer:", act_result.answer, "tag:", act_result.failure_tag)
for i, step in enumerate(act_result.steps, start=1):
    print(f"Action {i}: {step.action}")
    print(f"Observation {i}: {step.observation[:160]}")
print()

cot_result = run_example(question, gold, "cot", llm)
print("=== CoT ===")
print("EM:", cot_result.em, "answer:", cot_result.answer, "tag:", cot_result.failure_tag)
print("Thought (excerpt):", (cot_result.steps[0].thought or "")[:500])
"""
)

# --- Mini benchmark ----------------------------------------------------------

md(
    """
### Mini benchmark — four prompting methods × 8 questions

**Dataset:** `fixtures/hotpotqa_mini.json` — eight **public** multi-hop questions in HotpotQA style (short string answers). Includes the magazine question plus hops like iPhone → Apple → Cupertino.

**Scoring (not “LLM as judge”):**

- **EM (exact match):** normalized string equality with gold.
- **F1:** token overlap — partial credit if the answer is close.

Each row below runs **your** model with a **different few-shot prefix** (`react` / `act` / `cot` / `standard`). Expect **many LLM calls** (roughly 1–7 per question per method). This can take several minutes and costs tokens.

**Calibration:** paper Table 1 (PaLM-540B, 500 dev questions) is printed for reference — your numbers will differ.
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

print(f"{'method':<10} {'n':>3} {'EM':>6} {'F1':>6}  failure_tags")
for row in rows:
    print(f"{row['method']:<10} {row['n']:>3} {row['EM']:>6.3f} {row['F1']:>6.3f}  {row['failures']}")

print()
print("Paper Table 1 (PaLM-540B, 500 HotpotQA dev): Standard 28.7 | CoT 29.4 | Act 25.7 | ReAct 27.4")
"""
)

# --- Per-question traces -----------------------------------------------------

md(
    """
### Read ReAct traces like a researcher (Table 2 mindset)

For each failure, ask:

1. Did a **Search** return nothing useful? → search / tool issue.
2. Did the model **ignore** a correct observation? → reasoning / rigid trace.
3. Is the answer **close** but not exact? → `label_ambiguity` (normalization).
4. For CoT/Standard only: wrong with no tools → **hallucination**.

This cell runs **ReAct only** on all 8 questions and prints the action chain. Use it to connect EM numbers to *behavior*.
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

# --- Live Wikipedia ----------------------------------------------------------

md(
    """
### Live Wikipedia (optional, needs network)

`LocalWikiEnv` uses a tiny JSON corpus so experiments are fast and stable. **`LiveWikipediaEnv`** calls real `en.wikipedia.org` (same action strings).

Differences you should expect:

- Longer, noisier observations.
- Search disambiguation (“iPhone” vs “IPhone (disambiguation)”).
- Higher latency and more tokens.

We run **one** multi-hop question from the mini-set (iPhone headquarters). Compare whether your model still decomposes into entity searches.
"""
)

code(
    """
live_env = LiveWikipediaEnv()
task = load_hotpot_mini()[1]
agent = ReactAgent(llm, live_env, method="react")
result = agent.run(task.question, gold=task.answer)
print("Q:", task.question)
print("EM:", result.em, "answer:", result.answer, "tag:", result.failure_tag)
for step in result.steps:
    print(step.action, "→", step.observation[:100].replace("\\n", " "))
"""
)

# --- Closing -----------------------------------------------------------------

md(
    """
### Intuition checklist (answer in your own words)

1. **Augmented action space:** In ReAct, what is in $\\hat{\\mathcal{A}}$ that is *not* in the Wikipedia API?
2. **Grounding:** Why can CoT beat ReAct on EM but still be less *trustworthy* on fact-heavy tasks?
3. **Weak retriever:** Why did the authors avoid BM25/RAG for this experiment?
4. **Dense thoughts:** Why one Thought per Action on HotpotQA — and when would you *not* do that in an MCP agent?
5. **Backoff:** What is “ReAct → CoT-SC” in Table 1, and when would a product need that?

**Next in the roadmap:** [Reflexion](https://arxiv.org/abs/2303.11366) — verbal critique **between episodes**, not between tool calls.

**Debug tip:** On any `RunResult`, inspect `result.transcript` — that is the entire few-shot prefix plus every Thought/Action/Observation your model actually produced.
"""
)

nb.cells = cells
out = Path(__file__).resolve().parent.parent / "notebooks" / "react_from_scratch.ipynb"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(nbf.writes(nb), encoding="utf-8")
print("wrote", out)
