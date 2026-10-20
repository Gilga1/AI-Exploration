#!/usr/bin/env python3
"""Run the HotpotQA mini-set with OpenRouter (requires OPENROUTER_API_KEY + OPENROUTER_MODEL)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `python scripts/run_live_eval.py` without installing the package.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from react_foundations.evaluate import evaluate_with_llm
from react_foundations.llm import llm_from_env
from react_foundations.loop import Method
from react_foundations.wiki import LiveWikipediaEnv, LocalWikiEnv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--method",
        choices=("react", "act", "cot", "standard"),
        default="react",
        help="Prompting method (default: react)",
    )
    parser.add_argument(
        "--wiki",
        choices=("local", "live"),
        default="local",
        help="local = fixtures/local_wiki.json; live = en.wikipedia.org",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max questions (0 = all in hotpotqa_mini.json)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON (includes per-question transcripts)",
    )
    args = parser.parse_args()

    llm = llm_from_env()
    env = LiveWikipediaEnv() if args.wiki == "live" else LocalWikiEnv.from_fixture()
    method: Method = args.method

    summary = evaluate_with_llm(llm, method, env=env)
    if args.limit and args.limit < summary["n"]:
        summary["results"] = summary["results"][: args.limit]
        summary["n"] = len(summary["results"])
        summary["em"] = sum(r.em for r in summary["results"]) / summary["n"]
        summary["f1"] = sum(r.f1 for r in summary["results"]) / summary["n"]

    if args.json:
        print(
            json.dumps(
                {
                    "method": summary["method"],
                    "n": summary["n"],
                    "em": summary["em"],
                    "f1": summary["f1"],
                    "failure_tags": summary.get("failure_tags"),
                    "results": [
                        {
                            "question": r.question,
                            "answer": r.answer,
                            "gold": r.gold,
                            "em": r.em,
                            "f1": r.f1,
                            "failure_tag": r.failure_tag,
                            "n_calls": r.n_calls,
                        }
                        for r in summary["results"]
                    ],
                },
                indent=2,
            )
        )
        return

    print(f"method={summary['method']} wiki={args.wiki} n={summary['n']}")
    print(f"EM={summary['em']:.3f}  F1={summary['f1']:.3f}")
    if summary.get("failure_tags"):
        print("failure_tags:", summary["failure_tags"])
    for result in summary["results"]:
        mark = "OK" if result.em else "MISS"
        print(f"  [{mark}] {result.question[:70]}...")
        print(f"       pred={result.answer!r} gold={result.gold!r} tag={result.failure_tag}")


if __name__ == "__main__":
    main()
