"""The heavy check before a release: the tests, then the three places a version lives."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    tests = subprocess.run(["uv", "run", "--locked", "pytest", "-q"], cwd=ROOT)
    failures = []
    if tests.returncode != 0:
        failures.append("FAIL tests: `uv run --locked pytest -q` did not pass")

    sys.path.insert(0, str(ROOT / "src"))
    import shelf
    from shelf.app import app

    pinned = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    if pinned != shelf.__version__:
        failures.append(f"FAIL version: pyproject.toml has {pinned}, shelf.__version__ is {shelf.__version__}")

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    heading = re.search(r"^## (.+?)\s*$", changelog, re.MULTILINE)
    if not heading or heading.group(1) != shelf.__version__:
        found = heading.group(1) if heading else "none"
        failures.append(f"FAIL changelog: the first heading is {found}, not {shelf.__version__}")

    reported = _healthz(app)
    if reported != shelf.__version__:
        failures.append(f"FAIL healthz: it reports {reported}, not {shelf.__version__}")

    for line in failures:
        print(line)
    if failures:
        return 1
    print("release check passed")
    return 0


def _healthz(app) -> str | None:
    environ = {"REQUEST_METHOD": "GET", "PATH_INFO": "/healthz", "QUERY_STRING": ""}
    started = []
    body = b"".join(app(environ, lambda status, headers: started.append(status)))
    try:
        return json.loads(body)["version"]
    except (ValueError, KeyError, TypeError):
        return None


if __name__ == "__main__":
    sys.exit(main())
