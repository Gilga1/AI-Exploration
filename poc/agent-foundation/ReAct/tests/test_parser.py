from react_foundations.parser import canonicalize_action, parse_action, parse_thought_action


def test_parse_search_action():
    parsed = parse_action("Search[Arthur's Magazine]")
    assert parsed.name == "search"
    assert parsed.argument == "Arthur's Magazine"
    assert canonicalize_action("Search[Arthur's Magazine]") == "search[Arthur's Magazine]"


def test_parse_thought_action_official_format():
    generated = (
        "I need to search Arthur's Magazine and First for Women.\n"
        "Action 1: Search[Arthur's Magazine]"
    )
    thought, action = parse_thought_action(generated, 1)
    assert "Arthur's Magazine" in thought
    assert action == "Search[Arthur's Magazine]"


def test_parse_thought_action_recovers_thought_without_action():
    thought, action = parse_thought_action("maybe look up the date", 2)
    assert thought == "maybe look up the date"
    assert action == ""
