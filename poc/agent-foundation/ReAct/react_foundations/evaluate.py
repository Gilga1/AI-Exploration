"""Run the mini HotpotQA-style set with a live LLM."""

from __future__ import annotations

from collections import Counter

from react_foundations.llm import LLMClient
from react_foundations.loop import Method, ReactAgent, RunResult
from react_foundations.wiki import LocalWikiEnv, WikiEnv, load_hotpot_mini


def run_example(
    question: str,
    gold: str,
    method: Method,
    llm: LLMClient,
    env: WikiEnv | None = None,
) -> RunResult:
    agent = ReactAgent(llm, env or LocalWikiEnv.from_fixture(), method=method)
    return agent.run(question, gold=gold)


def evaluate_mini(
    method: Method,
    llm: LLMClient,
    env: WikiEnv | None = None,
) -> dict:
    return evaluate_with_llm(llm, method, env=env)


def evaluate_with_llm(llm: LLMClient, method: Method, env: WikiEnv | None = None) -> dict:
    tasks = load_hotpot_mini()
    wiki = env or LocalWikiEnv.from_fixture()
    results = []
    for task in tasks:
        agent = ReactAgent(llm, wiki, method=method)
        results.append(agent.run(task.question, gold=task.answer))
    em = sum(result.em for result in results) / len(results)
    f1 = sum(result.f1 for result in results) / len(results)
    tags = Counter(result.failure_tag for result in results if result.failure_tag)
    return {
        "method": method,
        "n": len(results),
        "em": em,
        "f1": f1,
        "failure_tags": dict(tags),
        "results": results,
    }
