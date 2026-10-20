from react_foundations.wiki import LocalWikiEnv


def test_search_returns_first_sentences():
    env = LocalWikiEnv.from_fixture()
    env.reset()
    result = env.step("Search[Arthur's Magazine]")
    assert "1844" in result.observation
    assert not result.done


def test_lookup_ctrl_f():
    env = LocalWikiEnv.from_fixture()
    env.reset()
    env.step("search[Milhouse]")
    result = env.step("lookup[named after]")
    assert "Richard Nixon" in result.observation
    assert result.observation.startswith("(Result 1 /")


def test_unknown_entity_suggests_similar():
    env = LocalWikiEnv.from_fixture()
    env.reset()
    result = env.step("Search[Sistine]")
    assert result.observation.startswith("Could not find")
    assert "Sistine Chapel" in result.observation


def test_finish_stores_answer():
    env = LocalWikiEnv.from_fixture()
    env.reset()
    result = env.step("Finish[Harper Lee]")
    assert result.done
    assert result.info["answer"] == "Harper Lee"
