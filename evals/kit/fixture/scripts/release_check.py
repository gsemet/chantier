"""The heavy check before a release: the whole suite, then what only a release needs."""
from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    subprocess.run(["uv", "run", "pytest", "-q"], cwd=ROOT, check=True)
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    p = subprocess.run([sys.executable, "-m", "tasks_cli.cli", "--version"], cwd=ROOT,
                       env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, capture_output=True,
                       text=True)
    expected = f"tasks {project['version']}"
    if p.stdout.strip() != expected:
        print(f"FAIL `tasks --version` must print `{expected}`: exit {p.returncode}, "
              f"{(p.stdout + p.stderr).strip()[-200:]}")
        return 1
    print("release check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
