from __future__ import annotations

import subprocess
from pathlib import Path

from qwen_agentic_ft.config import REPOS_DIR


def clone_or_update_repo(url: str, dest: Path, branch: str | None = "main", depth: int = 1) -> None:
    if dest.exists() and (dest / ".git").exists():
        subprocess.run(
            ["git", "-C", str(dest), "fetch", "--depth", str(depth), "origin"],
            check=True,
            capture_output=True,
            text=True,
        )
        if branch:
            subprocess.run(
                ["git", "-C", str(dest), "checkout", branch],
                check=False,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(dest), "reset", "--hard", f"origin/{branch}"],
                check=False,
                capture_output=True,
                text=True,
            )
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    clone_cmd = ["git", "clone", "--depth", str(depth), url, str(dest)]
    if branch:
        clone_cmd = ["git", "clone", "--depth", str(depth), "--branch", branch, url, str(dest)]

    result = subprocess.run(clone_cmd, capture_output=True, text=True)
    if result.returncode != 0 and branch:
        # Fallback to default branch when configured branch name differs.
        subprocess.run(
            ["git", "clone", "--depth", str(depth), url, str(dest)],
            check=True,
            capture_output=True,
            text=True,
        )
    elif result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, clone_cmd, result.stdout, result.stderr)


def get_repo_commit(repo_dir: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def sync_repos(repo_config: dict, repos_root: Path = REPOS_DIR) -> dict[str, str]:
    defaults = repo_config.get("defaults", {})
    branch = defaults.get("branch", "main")
    commits: dict[str, str] = {}

    for repo in repo_config.get("repos", []):
        name = repo["name"]
        dest = repos_root / name
        clone_or_update_repo(repo["url"], dest, branch=repo.get("branch", branch))
        commits[name] = get_repo_commit(dest)

    return commits
