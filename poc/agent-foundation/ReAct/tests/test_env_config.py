import os

from react_foundations.env_config import load_project_dotenv


def test_load_project_dotenv_from_package_root(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("OPENROUTER_API_KEY=from-dotenv\nOPENROUTER_MODEL=test/model\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    loaded = load_project_dotenv()
    assert loaded == env_file
    assert os.environ["OPENROUTER_API_KEY"] == "from-dotenv"
    assert os.environ["OPENROUTER_MODEL"] == "test/model"
