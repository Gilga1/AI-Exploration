# ReAct from scratch

Bare-metal **ReAct** (Yao et al., ICLR 2023 / arXiv:2210.03629). No LangChain, no scripted trajectories — every run uses a **live LLM** (OpenRouter by default).

Read [`PAPER_NOTES.md`](PAPER_NOTES.md) before the notebook.

## Setup

```bash
cd poc/agent-foundation/ReAct
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,notebook]"
cp .env.example .env   # Windows: copy .env.example .env
# Edit .env in THIS folder (next to pyproject.toml): OPENROUTER_API_KEY, OPENROUTER_MODEL
pip install -e ".[dev,notebook]"   # installs python-dotenv — required to read .env
```

**Windows / Jupyter:** If cell 0 still fails, set vars in the same terminal that launched Jupyter, or in PowerShell before `jupyter notebook`:

```powershell
$env:OPENROUTER_API_KEY="sk-or-..."
$env:OPENROUTER_MODEL="openai/gpt-4o-mini"
```

Restart the notebook kernel after changing `.env`.

## Notebook (recommended)

```bash
bash scripts/start_notebook.sh
# open notebooks/react_from_scratch.ipynb — run cells top to bottom
```

Or CLI:

```bash
export OPENROUTER_API_KEY=...
export OPENROUTER_MODEL=openai/gpt-4o-mini
python scripts/run_live_eval.py --method react --wiki local
python scripts/run_live_eval.py --method react --wiki live --limit 2
```

## Tests

Unit tests mock HTTP / use a test-only `SequenceLLM` under `tests/` — not used in the notebook or CLI.

```bash
python -m pytest -m "not network"
```

Optional live smoke test (costs tokens):

```bash
export OPENROUTER_API_KEY=... OPENROUTER_MODEL=...
python -m pytest -m network
```

## Layout

```
react_foundations/   # loop, wiki env, metrics, OpenRouterLLM
fixtures/            # local wiki + 8-question mini-set + official few-shot prompts
notebooks/
scripts/run_live_eval.py
```

**Branch:** `cursor/poc-agent-foundation-react-openrouter-55b7`

## What this is not

- Not Table 1 reproduction (needs paper model, 500 dev, exact decoding).
- Not runnable without API credentials — intentional.
