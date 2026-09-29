import pytest

from react_foundations.wiki import LiveWikipediaEnv


@pytest.mark.network
def test_live_wikipedia_search_iphone():
    env = LiveWikipediaEnv()
    env.reset()
    result = env.step("Search[iPhone]")
    assert "Apple" in result.observation or "smartphone" in result.observation.lower()
    lookup = env.step("Lookup[Apple]")
    assert "Apple" in lookup.observation or lookup.observation.startswith("No more results")
