#!/usr/bin/env python3
"""Cross-platform environment setup (Windows, macOS, Linux)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def venv_python(venv_dir: Path) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def run(cmd: list[str], *, cwd: Path | None = None) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=cwd or ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create venv and install project dependencies")
    parser.add_argument(
        "--extra",
        choices=["dev", "train", "agents", "all"],
        default="dev",
        help="Optional dependency group to install (default: dev)",
    )
    parser.add_argument(
        "--venv",
        type=Path,
        default=ROOT / ".venv",
        help="Virtual environment directory (default: .venv)",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete and recreate the virtual environment",
    )
    args = parser.parse_args()

    if args.recreate and args.venv.exists():
        import shutil

        shutil.rmtree(args.venv)

    if not args.venv.exists():
        run([sys.executable, "-m", "venv", str(args.venv)])

    py = venv_python(args.venv)
    if not py.exists():
        print(f"Expected venv python at {py}", file=sys.stderr)
        return 1

    run([str(py), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])

    if args.extra == "all":
        extras = "dev,train,agents"
    else:
        extras = args.extra
    run([str(py), "-m", "pip", "install", "-e", f".[{extras}]"])

    activate_hint = (
        f"{args.venv}\\Scripts\\activate"
        if sys.platform == "win32"
        else f"source {args.venv}/bin/activate"
    )
    print("\nSetup complete.")
    print(f"Activate the environment: {activate_hint}")
    print("Then run:")
    print("  python scripts/extract_data.py")
    print("  python scripts/train.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
