from react_foundations.evaluate import evaluate_mini, run_example
from react_foundations.llm import ScriptedLLM
from react_foundations.loop import ReactAgent
from react_foundations.policies import COT_HALLUCINATED_MAGAZINES, WEAK_ACT_SCRIPTS
from react_foundations.wiki import LocalWikiEnv, load_hotpot_mini


MAGAZINE_Q = "Which magazine was started first, Arthur's Magazine or First for Women?"


def test_react_solves_paper_example():
    result = run_example(MAGAZINE_Q, "Arthur's Magazine", "react")
    assert result.em
    assert result.answer == "Arthur's Magazine"
    assert result.steps[0].action == "Search[Arthur's Magazine]"
    assert "1844" in result.steps[0].observation
    assert result.steps[1].action == "Search[First for Women]"
    assert "1989" in result.steps[1].observation
    assert result.failure_tag is None


def test_cot_hallucination_is_wrong_and_tagged():
    env = LocalWikiEnv.from_fixture()
    agent = ReactAgent(ScriptedLLM([COT_HALLUCINATED_MAGAZINES]), env, method="cot")
    result = agent.run(MAGAZINE_Q, gold="Arthur's Magazine")
    assert not result.em
    assert result.answer == "First for Women"
    assert result.failure_tag == "hallucination"


def test_act_without_reasoning_can_fail():
    env = LocalWikiEnv.from_fixture()
    agent = ReactAgent(ScriptedLLM(list(WEAK_ACT_SCRIPTS[MAGAZINE_Q])), env, method="act")
    result = agent.run(MAGAZINE_Q, gold="Arthur's Magazine")
    assert not result.em
    assert result.steps[0].observation.startswith("Could not find")


def test_scripted_react_solves_entire_mini_set():
    summary = evaluate_mini("react")
    assert summary["n"] == 8
    assert summary["em"] == 1.0
    assert summary["f1"] == 1.0


def test_load_hotpot_mini_has_paper_example():
    tasks = load_hotpot_mini()
    assert tasks[0].question == MAGAZINE_Q
    assert tasks[0].answer == "Arthur's Magazine"
