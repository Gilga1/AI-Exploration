from react_foundations.evaluate import evaluate_with_llm
from react_foundations.loop import ReactAgent
from react_foundations.wiki import LocalWikiEnv, load_hotpot_mini
from tests.sequence_llm import SequenceLLM

MAGAZINE_Q = "Which magazine was started first, Arthur's Magazine or First for Women?"

REACT_MAGAZINE_COMPLETIONS = [
    "I need to search Arthur's Magazine and First for Women, and find which started first.\nAction 1: Search[Arthur's Magazine]",
    "Arthur's Magazine was started in 1844. I need to search First for Women next.\nAction 2: Search[First for Women]",
    "First for Women was started in 1989. 1844 < 1989, so Arthur's Magazine started first.\nAction 3: Finish[Arthur's Magazine]",
]

COT_HALLUCINATED = (
    "Let's think step by step. First for Women is a well-known magazine that started in the 19th century. "
    "Arthur's Magazine started much later. So the answer is First for Women."
)

WEAK_ACT_COMPLETIONS = [
    "Search[Which magazine was started first, Arthur's Magazine or First for Women?]",
    "Finish[First for Women]",
]


def test_react_solves_paper_example_with_sequence_llm():
    env = LocalWikiEnv.from_fixture()
    agent = ReactAgent(SequenceLLM(list(REACT_MAGAZINE_COMPLETIONS)), env, method="react")
    result = agent.run(MAGAZINE_Q, gold="Arthur's Magazine")
    assert result.em
    assert result.answer == "Arthur's Magazine"
    assert result.steps[0].action == "Search[Arthur's Magazine]"
    assert "1844" in result.steps[0].observation
    assert result.failure_tag is None


def test_cot_hallucination_is_wrong_and_tagged():
    env = LocalWikiEnv.from_fixture()
    agent = ReactAgent(SequenceLLM([COT_HALLUCINATED]), env, method="cot")
    result = agent.run(MAGAZINE_Q, gold="Arthur's Magazine")
    assert not result.em
    assert result.answer == "First for Women"
    assert result.failure_tag == "hallucination"


def test_act_without_reasoning_can_fail():
    env = LocalWikiEnv.from_fixture()
    agent = ReactAgent(SequenceLLM(list(WEAK_ACT_COMPLETIONS)), env, method="act")
    result = agent.run(MAGAZINE_Q, gold="Arthur's Magazine")
    assert not result.em
    assert result.steps[0].observation.startswith("Could not find")


def test_evaluate_with_llm_runs_all_tasks():
    llm = SequenceLLM(["Arthur's Magazine"] * 8)
    summary = evaluate_with_llm(llm, "standard")
    assert summary["n"] == 8
    assert 0.0 <= summary["em"] <= 1.0


def test_load_hotpot_mini_has_paper_example():
    tasks = load_hotpot_mini()
    assert tasks[0].question == MAGAZINE_Q
    assert tasks[0].answer == "Arthur's Magazine"
