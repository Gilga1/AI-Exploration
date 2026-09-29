"""Optional live OpenRouter smoke test (set OPENROUTER_API_KEY + OPENROUTER_MODEL)."""

import os

import pytest

from react_foundations.llm import OpenRouterLLM
from react_foundations.loop import ReactAgent
from react_foundations.wiki import LocalWikiEnv

pytestmark = pytest.mark.network


@pytest.mark.skipif(not os.environ.get("OPENROUTER_API_KEY"), reason="OPENROUTER_API_KEY not set")
@pytest.mark.skipif(not os.environ.get("OPENROUTER_MODEL"), reason="OPENROUTER_MODEL not set")
def test_openrouter_react_one_step():
    llm = OpenRouterLLM.from_env()
    env = LocalWikiEnv.from_fixture()
    agent = ReactAgent(llm, env, method="react", max_steps=1)
    result = agent.run(
        "Which magazine was started first, Arthur's Magazine or First for Women?",
        gold="Arthur's Magazine",
    )
    assert result.steps
    assert result.steps[0].action.lower().startswith("search")
