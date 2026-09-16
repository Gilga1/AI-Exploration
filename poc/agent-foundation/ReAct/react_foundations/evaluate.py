"""Run the mini HotpotQA-style set with a scripted or live LLM."""

from __future__ import annotations

from collections import Counter

from react_foundations.llm import LLMClient, ScriptedLLM
from react_foundations.loop import Method, ReactAgent, RunResult
from react_foundations.policies import (
    COT_SCRIPTS,
    REACT_SCRIPTS,
    STANDARD_SCRIPTS,
    act_scripts,
)
from react_foundations.wiki import LocalWikiEnv, WikiEnv, load_hotpot_mini


def scripted_llm_for(question: str, method: Method) -> ScriptedLLM:
    if method == "react":
        return ScriptedLLM(list(REACT_SCRIPTS[question]))
    if method == "act":
        return ScriptedLLM(list(act_scripts()[question]))
    if method == "cot":
        return ScriptedLLM([COT_SCRIPTS[question]])
    return ScriptedLLM([STANDARD_SCRIPTS[question]])


def run_example(question: str, gold: str, method: Method, env: WikiEnv | None = None) -> RunResult:
    agent = ReactAgent(scripted_llm_for(question, method), env or LocalWikiEnv.from_fixture(), method=method)
    return agent.run(question, gold=gold)


def evaluate_mini(method: Method = "react", env: WikiEnv | None = None) -> dict:
    tasks = load_hotpot_mini()
    wiki = env or LocalWikiEnv.from_fixture()
    results = [run_example(task.question, task.answer, method, wiki) for task in tasks]
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


def evaluate_with_llm(llm: LLMClient, method: Method, env: WikiEnv | None = None) -> dict:
    tasks = load_hotpot_mini()
    wiki = env or LocalWikiEnv.from_fixture()
    results = []
    for task in tasks:
        agent = ReactAgent(llm, wiki, method=method)
        results.append(agent.run(task.question, gold=task.answer))
    em = sum(result.em for result in results) / len(results)
    f1 = sum(result.f1 for result in results) / len(results)
    return {"method": method, "n": len(results), "em": em, "f1": f1, "results": results}
