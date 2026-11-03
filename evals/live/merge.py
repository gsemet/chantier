"""The evaluator merges a pull request on the local forge, as the user would.

    uv run --no-project python evals/live/merge.py <workspace> <pr-number>

Merges the PR's branch into `main` on the bare origin (a merge commit, in a fresh clone) and marks
the PR merged. A conflict merges nothing.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True).stdout.strip()


def main(workspace: Path, number: str) -> None:
    origin = workspace.with_name(workspace.name + ".origin.git")
    state_path = workspace.with_name(workspace.name + ".forge") / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    pr = state["prs"][number]
    if pr["state"] != "open":
        raise SystemExit(f"PR {number} is {pr['state']}")
    with tempfile.TemporaryDirectory(prefix="forge-merge-") as tmp:
        git("clone", "--quiet", str(origin), tmp, cwd=workspace.parent)
        git("config", "user.name", "eval user", cwd=tmp)
        git("config", "user.email", "eval@example.com", cwd=tmp)
        git("checkout", "--quiet", pr["base"], cwd=tmp)
        try:
            git("merge", "--no-ff", "-m", f"Merge pull request #{number}", f"origin/{pr['head']}",
                cwd=tmp)
        except subprocess.CalledProcessError as e:
            raise SystemExit(f"PR {number} does not merge cleanly: {e.stdout}{e.stderr}") from e
        git("push", "--quiet", "origin", pr["base"], cwd=tmp)
    pr["state"] = "merged"
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"merged PR {number} ({pr['head']}) into {pr['base']}")


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(), sys.argv[2])
