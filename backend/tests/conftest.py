import os

os.environ.setdefault("APP_DATABASE_URL", "sqlite:///./test_traces.db")
os.environ.setdefault("APP_LLM_MODEL", "openai/gpt-4o-mini")
os.environ.setdefault("APP_LLM_BASE_URL", "https://openrouter.ai/api/v1")
os.environ.setdefault("APP_LLM_PROVIDER", "openrouter")
os.environ.setdefault("APP_AUTH_DISABLED", "true")
os.environ.setdefault("APP_ENVIRONMENT", "test")

import pytest


@pytest.fixture(autouse=True)
def clear_settings_cache():
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
