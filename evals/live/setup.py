"""Stage a workspace for the live eval: the tasks-cli project, a bare origin, the local forge.

    uv run --no-project python evals/live/setup.py <workspace> [<cr-slug>…]

Creates `<workspace>` (a git repository on `main`, pushed to `<workspace>.origin.git`), the forge
state next to it in `<workspace>.forge/`, and `.claude/settings.local.json` so that every Claude
session in the workspace (the Foreman, its Drivers and workers) calls the local forge as `gh`.
The prepared CRs (all five by default) go to `.agents/changes/backlog/2-backlog/P1/`.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
IGNORE = shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache", "tasks.json")


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def main(dest: Path, slugs: list[str]) -> None:
    if dest.exists():
        raise SystemExit(f"{dest} already exists")
    origin = dest.with_name(dest.name + ".origin.git")
    forge = dest.with_name(dest.name + ".forge")
    shutil.copytree(HERE / "fixture", dest, ignore=IGNORE)
    git("init", "--quiet", "-b", "main", str(dest), cwd=dest.parent)
    git("config", "user.name", "eval user", cwd=dest)
    git("config", "user.email", "eval@example.com", cwd=dest)
    git("add", ".", cwd=dest)
    git("commit", "--quiet", "-m", "chore: tasks-cli", cwd=dest)
    git("init", "--quiet", "--bare", "-b", "main", str(origin), cwd=dest.parent)
    git("remote", "add", "origin", str(origin), cwd=dest)
    git("push", "--quiet", "-u", "origin", "main", cwd=dest)
    git("remote", "set-head", "origin", "main", cwd=dest)

    forge.mkdir()
    state = forge / "state.json"
    state.write_text(json.dumps({"next_pr": 1, "next_run": 1, "prs": {}, "ci": {}}))
    if sys.platform == "win32":
        gh = forge / "gh.cmd"
        gh.write_text(f'@"{sys.executable}" "{HERE / "forge.py"}" %*\r\n')
    else:
        gh = forge / "gh"
        gh.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{HERE / "forge.py"}" "$@"\n')
        gh.chmod(0o755)
    settings = dest / ".claude" / "settings.local.json"
    settings.write_text(json.dumps({"env": {
        "CHANTIER_GH": str(gh), "FAKE_GH_STATE": str(state), "LIVE_ORIGIN": str(origin),
        "CHANTIER_WAIT_INTERVAL": "15", "LIVE_CI_DELAY": "120"}}, indent=2) + "\n")

    backlog = dest / ".agents" / "changes" / "backlog" / "2-backlog" / "P1"
    for slug in slugs or sorted(p.name for p in (HERE / "crs").iterdir()):
        shutil.copytree(HERE / "crs" / slug, backlog / slug)
    subprocess.run(["uv", "sync", "--quiet"], cwd=dest, check=True)
    print(f"workspace {dest}\norigin    {origin}\nforge     {state}")


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(), sys.argv[2:])
