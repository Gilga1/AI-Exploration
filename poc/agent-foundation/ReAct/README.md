# ReAct from scratch

Bare-metal reproduction of **ReAct: Synergizing Reasoning and Acting in Language Models** (Yao et al., ICLR 2023 / arXiv:2210.03629). No LangChain, no agent framework — the loop is ~100 lines of Python.

This is Phase 1 of the GenAI research roadmap: internalize the ancestor of every later agent loop before adding Reflexion, memory, or orchestration.

## Why this paper

ReAct is not “an agent library.” It is a prompting paradigm that **augments the action space with language thoughts**:

\[
\hat{\mathcal{A}} = \mathcal{A} \cup \mathcal{L}
\]

Thoughts do not touch the environment. They update the context \(c_{t+1} = (c_t, \hat{a}_t)\) so later actions can be planned, revised, or grounded. That is the same structure as “reason → tool call → observe → reason again,” which later shows up in tool-calling APIs, MCP loops, and Deep Agents.

Read [`PAPER_NOTES.md`](PAPER_NOTES.md) before skimming the notebook. The notes are the research object; the code is how you falsify that you understood them.

## Layout

```
poc/agent-foundation/ReAct/
  PAPER_NOTES.md              # close reading, formalism, failure modes
  notebooks/react_from_scratch.ipynb
  react_foundations/          # importable implementation
  fixtures/
    prompts_naive.json        # official 6-shot prompts from ysymyth/ReAct
    local_wiki.json           # offline Wikipedia stand-in
    hotpotqa_mini.json        # 8 public multi-hop questions
  tests/
```

## Dataset

The paper’s knowledge-intensive experiments use **HotpotQA** (Yang et al., 2018) in a *question-only* setup: no supporting paragraphs are given; the model must `search` / `lookup` Wikipedia.

This folder ships an 8-question public mini-set in that style (including the paper’s Arthur’s Magazine vs First for Women example) plus a local wiki so the notebook is fully reproducible without an LLM API key. The original official code samples 500 HotpotQA dev examples against live Wikipedia with `text-davinci-002`.

## Run tests

```bash
cd poc/agent-foundation/ReAct
python -m pip install -e ".[dev]"
python -m pytest -m "not network"
python -m pytest -m network   # live en.wikipedia.org
```

## Run the notebook

```bash
cd poc/agent-foundation/ReAct
jupyter notebook notebooks/react_from_scratch.ipynb
```

The notebook runs end-to-end with **scripted** Thought/Action traces by default (no API key). For a **live model via OpenRouter**, copy `.env.example` to `.env`, set `OPENROUTER_API_KEY` and `OPENROUTER_MODEL`, then use `OpenRouterLLM.from_env()` or the CLI below.

### Live eval (OpenRouter)

```bash
cd poc/agent-foundation/ReAct
export OPENROUTER_API_KEY=...
export OPENROUTER_MODEL=openai/gpt-4o-mini   # or any chat model on OpenRouter
python scripts/run_live_eval.py --method react --wiki local
python scripts/run_live_eval.py --method react --wiki live --limit 2   # real Wikipedia
```

`REACT_LLM_BACKEND=openai_completions` plus `OPENAI_API_KEY` still works for legacy **instruct** models that expose `/v1/completions` (not most OpenRouter chat models).

**Branch:** `cursor/poc-agent-foundation-react-openrouter-55b7` (live LLM path). The earlier draft `cursor/poc-agent-foundation-react-d23e` is the scripted-only study branch.

## Official sources

- Paper: https://arxiv.org/abs/2210.03629
- Site: https://react-lm.github.io/
- Original GPT-3 notebooks: https://github.com/ysymyth/ReAct

## What this is not

- Not a claim that this mini-set reproduces PaLM-540B HotpotQA EM (27.4). That number needs the paper’s model, 6-shot prompts, and 500-dev sample.
- Not Phase 2 (pass^k harness, MAST tags on your MCP servers). This folder stops at: understand ReAct, implement the loop, score with execution-based EM/F1.
