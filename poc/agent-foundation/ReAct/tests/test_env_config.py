import os

from react_foundations.env_config import (
    load_dotenv_file,
    load_project_dotenv,
    react_package_root,
)


def test_load_dotenv_file_parses_key_value(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\nOPENROUTER_API_KEY=from-file\nOPENROUTER_MODEL=test/model\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    assert load_dotenv_file(env_file)
    assert os.environ["OPENROUTER_API_KEY"] == "from-file"
    assert os.environ["OPENROUTER_MODEL"] == "test/model"


def test_load_dotenv_file_strips_utf8_bom(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_bytes(
        b"\xef\xbb\xbfOPENROUTER_API_KEY=bom-key\nOPENROUTER_MODEL=m\n",
    )
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    load_dotenv_file(env_file)
    assert os.environ["OPENROUTER_API_KEY"] == "bom-key"


def test_load_project_dotenv_from_cwd(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("OPENROUTER_API_KEY=from-dotenv\nOPENROUTER_MODEL=test/model\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    loaded = load_project_dotenv()
    assert loaded == env_file
    assert os.environ["OPENROUTER_API_KEY"] == "from-dotenv"


def test_react_package_root_points_at_react_folder():
    root = react_package_root()
    assert (root / "pyproject.toml").is_file()
    assert (root / "react_foundations").is_dir()
