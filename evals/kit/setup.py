"""Stage a workspace for one eval campaign: the tasks-cli project, a bare origin, the local forge.

    uv run --no-project python evals/kit/setup.py <campaign> <workspace>

Creates `<workspace>` (a git repository on `main`, pushed to `<workspace>.origin.git`) and the
forge state next to it in `<workspace>.forge/`. The campaign sets which prepared CRs go to
`.agents/changes/2-backlog/P1/`, which review steps the project's `AGENTS.md` declares,
and which CI contracts the forge adds. On Claude, `.claude/settings.local.json` puts the forge's
folder first on `PATH` for every session in the workspace (the Foreman, its Drivers and
workers): their `gh` is the local forge.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
IGNORE = shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache", "tasks.json")
REVIEWS = {
    "docs-review": ("chantier-eval-docs-reviewer", "every new or changed CLI command or option "
                    "is documented in README.md, with an example"),
    "style-review": ("chantier-eval-strict-reviewer", "the house style of the command line"),
}
CAMPAIGNS = {
    "claude-smoke": {"host": "claude", "crs": ["done-unknown-id"], "reviews": ["docs-review"]},
    "claude-full": {"host": "claude",
                    "crs": ["add-priority", "done-unknown-id", "list-json", "delete-command",
                            "export-csv", "stats-command", "release-v0-2-0", "version-option"],
                    "reviews": ["docs-review", "style-review"], "contracts": True,
                    "release": "RELEASING.md"},
    "copilot": {"host": "copilot", "crs": ["done-unknown-id"], "reviews": []},
}


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def main(campaign: str, dest: Path) -> None:
    if campaign not in CAMPAIGNS:
        raise SystemExit(f"campaign: one of {', '.join(CAMPAIGNS)}")
    spec = CAMPAIGNS[campaign]
    if dest.exists():
        raise SystemExit(f"{dest} already exists")
    origin = dest.with_name(dest.name + ".origin.git")
    forge = dest.with_name(dest.name + ".forge")
    shutil.copytree(HERE / "fixture", dest, ignore=IGNORE)
    if spec["reviews"]:
        with (dest / "AGENTS.md").open("a", encoding="utf-8") as f:
            f.write("\n## chantier\n\n" + "".join(
                f"- {name}: `{REVIEWS[name][0]}`, after the Inspector: {REVIEWS[name][1]}\n"
                for name in spec["reviews"]))
            if spec.get("release"):
                f.write(f"- release: {spec['release']}\n")
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
    # the Drivers and the Foreman call `gh` themselves: the forge's folder comes first on PATH
    env = {"FAKE_GH_STATE": str(state), "LIVE_ORIGIN": str(origin),
           "LIVE_CI_DELAY": "120", "PATH": str(forge) + os.pathsep + os.environ.get("PATH", "")}
    if spec.get("contracts"):
        env["LIVE_CI_CONTRACTS"] = str(HERE / "contracts")
    if spec["host"] == "claude":
        settings = dest / ".claude" / "settings.local.json"
        settings.write_text(json.dumps({"env": env}, indent=2) + "\n")

    backlog = dest / ".agents" / "changes" / "2-backlog" / "P1"
    for slug in spec["crs"]:
        shutil.copytree(HERE / "crs" / slug, backlog / slug)
    subprocess.run(["uv", "sync", "--quiet"], cwd=dest, check=True)
    print(f"campaign  {campaign}\nworkspace {dest}\norigin    {origin}\nforge     {state}")
    if spec["host"] != "claude":
        print("environment for every session of the batch:")
        print("".join(f"  {k}={v}\n" for k, v in env.items()), end="")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], Path(sys.argv[2]).resolve())
