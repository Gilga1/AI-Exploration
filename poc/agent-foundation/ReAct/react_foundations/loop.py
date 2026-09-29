"""ReAct loop: Thought_t → Action_t → Observation_t, max 7 steps (HotpotQA paper setting)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from react_foundations.llm import LLMClient
from react_foundations.metrics import exact_match, f1_score
from react_foundations.parser import canonicalize_action, parse_thought_action
from react_foundations.prompts import act_prompt, cot_prompt, react_prompt, standard_prompt
from react_foundations.wiki import WikiEnv

Method = Literal["react", "act", "cot", "standard"]

FAILURE_REASONING = "reasoning_error"
FAILURE_SEARCH = "search_result_error"
FAILURE_HALLUCINATION = "hallucination"
FAILURE_NO_ANSWER = "no_answer"
FAILURE_LABEL = "label_ambiguity"


@dataclass
class TrajectoryStep:
    thought: str | None
    action: str
    observation: str


@dataclass
class RunResult:
    question: str
    method: Method
    answer: str | None
    gold: str | None
    em: bool
    f1: float
    steps: list[TrajectoryStep] = field(default_factory=list)
    n_calls: int = 0
    n_badcalls: int = 0
    transcript: str = ""
    failure_tag: str | None = None

    def tag_failure(self) -> str | None:
        if self.em:
            return None
        if not self.answer:
            return FAILURE_NO_ANSWER
        search_misses = [
            step
            for step in self.steps
            if step.observation.startswith("Could not find")
            or step.observation.startswith("No more results")
        ]
        if search_misses and not any(
            step.observation and not step.observation.startswith("Could not find")
            for step in self.steps
            if step.action.lower().startswith("search")
        ):
            return FAILURE_SEARCH
        if self.method in {"cot", "standard"}:
            return FAILURE_HALLUCINATION
        if self.gold and self.answer and f1_score(self.answer, self.gold) >= 0.5:
            return FAILURE_LABEL
        return FAILURE_REASONING


class ReactAgent:
    """Few-shot ReAct / Act / CoT / Standard prompting over a WikiEnv."""

    def __init__(
        self,
        llm: LLMClient,
        env: WikiEnv,
        method: Method = "react",
        max_steps: int = 7,
    ) -> None:
        self.llm = llm
        self.env = env
        self.method = method
        self.max_steps = max_steps

    def _prefix(self) -> str:
        if self.method == "react":
            return react_prompt()
        if self.method == "act":
            return act_prompt()
        if self.method == "cot":
            return cot_prompt()
        return standard_prompt()

    def run(self, question: str, gold: str | None = None) -> RunResult:
        self.env.reset()
        prompt = self._prefix() + f"Question: {question}\n"
        steps: list[TrajectoryStep] = []
        n_calls = 0
        n_badcalls = 0
        answer: str | None = None

        if self.method in {"cot", "standard"}:
            n_calls += 1
            if self.method == "cot":
                text = self.llm.complete(prompt + "Thought:", stop=["\nQuestion:"])
                thought = text.strip()
                action = _extract_finish(thought) or f"Finish[{thought.rsplit()[-1]}]"
                result = self.env.step(canonicalize_action(action))
                steps.append(TrajectoryStep(thought=thought, action=action, observation=result.observation))
                answer = self.env.answer
                prompt += f"Thought: {thought}\n"
            else:
                text = self.llm.complete(prompt, stop=["\nQuestion:"])
                action = _extract_finish(text) or f"Finish[{text.strip()}]"
                result = self.env.step(canonicalize_action(action))
                steps.append(TrajectoryStep(thought=None, action=action, observation=result.observation))
                answer = self.env.answer
                prompt += text
        else:
            for index in range(1, self.max_steps + 1):
                n_calls += 1
                if self.method == "react":
                    generated = self.llm.complete(
                        prompt + f"Thought {index}:",
                        stop=[f"\nObservation {index}:"],
                    )
                    thought, action = parse_thought_action(generated, index)
                    if not action:
                        n_badcalls += 1
                        n_calls += 1
                        action = self.llm.complete(
                            prompt + f"Thought {index}: {thought}\nAction {index}:",
                            stop=["\n"],
                        ).strip()
                else:
                    thought = None
                    generated = self.llm.complete(
                        prompt + f"Action {index}:",
                        stop=[f"\nObservation {index}:"],
                    )
                    action = generated.strip()

                env_action = canonicalize_action(action)
                result = self.env.step(env_action)
                observation = result.observation.replace("\\n", "")
                steps.append(
                    TrajectoryStep(thought=thought, action=action, observation=observation)
                )
                if self.method == "react":
                    prompt += (
                        f"Thought {index}: {thought}\n"
                        f"Action {index}: {action}\n"
                        f"Observation {index}: {observation}\n"
                    )
                else:
                    prompt += f"Action {index}: {action}\nObservation {index}: {observation}\n"
                if result.done:
                    answer = self.env.answer
                    break
            if answer is None:
                result = self.env.step("finish[]")
                answer = self.env.answer
                steps.append(TrajectoryStep(thought=None, action="finish[]", observation=result.observation))

        em = exact_match(answer, gold) if gold is not None else False
        f1 = f1_score(answer, gold) if gold is not None else 0.0
        run = RunResult(
            question=question,
            method=self.method,
            answer=answer,
            gold=gold,
            em=em,
            f1=f1,
            steps=steps,
            n_calls=n_calls,
            n_badcalls=n_badcalls,
            transcript=prompt,
        )
        run.failure_tag = run.tag_failure()
        return run


def _extract_finish(text: str) -> str | None:
    for line in text.splitlines()[::-1]:
        stripped = line.strip()
        lower = stripped.lower()
        if lower.startswith("finish[") and stripped.endswith("]"):
            return stripped
        if lower.startswith("action") and "finish[" in lower:
            return stripped.split(":", 1)[-1].strip()
    marker = "so the answer is"
    if marker in text.lower():
        tail = text.lower().split(marker, 1)[1].strip().strip(".")
        original_tail = text[text.lower().rfind(marker) + len(marker) :].strip().strip(".")
        return f"Finish[{original_tail}]"
    return None
