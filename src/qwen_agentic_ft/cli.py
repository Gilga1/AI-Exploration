from __future__ import annotations

import argparse
import json
from pathlib import Path

from qwen_agentic_ft.config import load_extraction_config, load_repo_config
from qwen_agentic_ft.extract.pipeline import run_extraction
from qwen_agentic_ft.repos import sync_repos


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract agentic code training data from GitHub repos")
    parser.add_argument("--skip-clone", action="store_true", help="Skip git clone/update step")
    parser.add_argument("--clone-only", action="store_true", help="Only clone repos, do not extract")
    parser.add_argument("--repos-config", type=Path, default=None)
    parser.add_argument("--extraction-config", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    repo_config = load_repo_config(args.repos_config)
    extraction_config = load_extraction_config(args.extraction_config)

    commits = {}
    if not args.skip_clone:
        commits = sync_repos(repo_config)
        print(json.dumps({"cloned": list(commits.keys()), "commits": commits}, indent=2))

    if args.clone_only:
        return 0

    result = run_extraction(repo_config, extraction_config)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
