"""A local forge for the live eval, called as `gh` (first on the agents' `PATH`).

Pull requests live in $FAKE_GH_STATE; branches in the bare repository $LIVE_ORIGIN. A PR's checks
are real: the long gate runs on the PR's head in a fresh clone, once per commit. With
$LIVE_CI_CONTRACTS (a folder holding `contracts.json`, `{"<word>": "<test file>"}`), a branch
whose name contains a word also gets that test file in its clone's `tests/`: a contract only CI
checks. Every call is logged in `<state>.calls`. The Drivers open and edit the PRs and watch
their checks (`pr checks --watch`); `pr merge --rebase` merges a PR whose head is green, for the
Foreman; the audit checks that only what the user allowed was merged. `auth status` answers
that the user is logged in (exit 0) and needs no pull request state. Anything else an agent
must never do here (close, say) is refused, and the log keeps it for the audit.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

STATE = Path(os.environ["FAKE_GH_STATE"])
ORIGIN = os.environ["LIVE_ORIGIN"]
CI = os.environ.get("LIVE_CI", "uv run pytest -q")
DELAY = float(os.environ.get("LIVE_CI_DELAY", "0"))  # seconds a new commit's checks stay pending
CONTRACTS = os.environ.get("LIVE_CI_CONTRACTS")
URL = "https://forge.local/tasks-cli"


class Locked:
    """One caller at a time: Drivers ship and wait in parallel."""

    def __enter__(self):
        self.path = STATE.with_suffix(".lock")
        for _ in range(600):
            try:
                self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                return self
            except FileExistsError:
                time.sleep(0.1)
        raise SystemExit("fake forge: state locked for a minute")

    def __exit__(self, *exc):
        os.close(self.fd)
        os.unlink(self.path)


def load() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else \
        {"next_pr": 1, "next_run": 1, "prs": {}, "ci": {}}


def save(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def flag(args: list[str], name: str) -> str | None:
    return args[args.index(name) + 1] if name in args else None


def pr_number(ref: str) -> str:
    return ref.rstrip("/").rsplit("/", 1)[-1]


def head_sha(branch: str) -> str:
    out = subprocess.run(["git", "ls-remote", ORIGIN, f"refs/heads/{branch}"],
                         capture_output=True, text=True).stdout.split()
    if not out:
        raise SystemExit(f"fake forge: no branch {branch} on origin")
    return out[0]


def run_ci(state: dict, sha: str, branch: str) -> dict:
    """The long gate on one commit, in a fresh clone; the result is kept per commit."""
    if sha in state["ci"]:
        return state["ci"][sha]
    with tempfile.TemporaryDirectory(prefix="forge-ci-") as tmp:
        subprocess.run(["git", "clone", "--quiet", ORIGIN, tmp], check=True)
        subprocess.run(["git", "checkout", "--quiet", sha], cwd=tmp, check=True)
        if CONTRACTS:
            folder = Path(CONTRACTS)
            for word, test in json.loads((folder / "contracts.json").read_text()).items():
                if word in branch:
                    shutil.copy(folder / test, Path(tmp) / "tests" / test)
        p = subprocess.run(CI, shell=True, cwd=tmp, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    run = state["next_run"]
    state["next_run"] = run + 1
    state["ci"][sha] = {"bucket": "pass" if p.returncode == 0 else "fail", "run": run,
                        "log": (p.stderr + p.stdout)[-4000:]}  # pytest's summary last
    return state["ci"][sha]


def merge(state: dict, n: str, method: str) -> str | None:
    """Rebase a green PR on its base, in a fresh clone; what stops it, or None."""
    pr = state["prs"][n]
    sha = head_sha(pr["head"])
    if method != "--rebase" or pr["state"] != "open" or state["ci"].get(sha, {}).get("bucket") != "pass":
        return f"PR {n} ({pr['state']}, {method}): only an open, green PR merges, by rebase"
    git = ["git", "-c", "user.name=forge", "-c", "user.email=forge@example.com"]
    with tempfile.TemporaryDirectory(prefix="forge-merge-") as tmp:
        subprocess.run(["git", "clone", "--quiet", ORIGIN, tmp], check=True)
        for step in (["checkout", "--quiet", pr["head"]], ["rebase", f"origin/{pr['base']}"],
                     ["checkout", "--quiet", pr["base"]], ["merge", "--ff-only", pr["head"]],
                     ["push", "--quiet", "origin", pr["base"]]):
            p = subprocess.run(git + step, cwd=tmp, capture_output=True, text=True)
            if p.returncode:
                return f"PR {n}: git {step[0]} failed: {(p.stderr + p.stdout)[-300:]}"
    pr["state"] = "merged"
    return None


def body_of(args: list[str]) -> str | None:
    if flag(args, "--body-file"):
        return Path(flag(args, "--body-file")).read_text(encoding="utf-8")
    return flag(args, "--body")


def print_checks(args: list[str], checks: list[dict]) -> None:
    """As `gh` does: a table, or JSON with `--json`."""
    if "--json" in args:
        print(json.dumps(checks))
    else:
        for c in checks:
            print(f"{c['name']}\t{c['bucket']}\t{c['link']}")


def main(args: list[str]) -> int:
    with open(STATE.with_suffix(".calls"), "a", encoding="utf-8") as log:
        log.write(json.dumps({"t": time.strftime("%H:%M:%S"), "cwd": os.getcwd(),
                              "args": args}) + "\n")
    while True:
        with Locked():
            state = load()
            if args[:2] == ["pr", "checks"]:  # outside the lock while it waits
                n = pr_number(args[2])
                sha = head_sha(state["prs"][n]["head"])
                first = state.setdefault("seen", {}).setdefault(sha, time.time())
                save(state)
                pending = time.time() - first < DELAY  # CI takes a while, as a real one does
            if not (args[:2] == ["pr", "checks"] and pending and "--watch" in args):
                break
        time.sleep(1)
    with Locked():
        state = load()
        if args[:2] == ["pr", "create"]:
            n = str(state["next_pr"])
            state["next_pr"] += 1
            state["prs"][n] = {"head": flag(args, "--head"), "base": flag(args, "--base"),
                               "title": flag(args, "--title"), "state": "open",
                               "body": body_of(args) or ""}
            save(state)
            print(f"{URL}/pull/{n}")
        elif args[:2] == ["pr", "edit"]:
            pr = state["prs"][pr_number(args[2])]
            if flag(args, "--base"):
                pr["base"] = flag(args, "--base")
            if flag(args, "--title"):
                pr["title"] = flag(args, "--title")
            if body_of(args) is not None:
                pr["body"] = body_of(args)
            save(state)
            print(args[2])
        elif args[:2] == ["pr", "checks"]:
            if pending:
                print_checks(args, [{"name": "pytest", "bucket": "pending", "link": ""}])
                return 0
            ci = run_ci(state, sha, state["prs"][n]["head"])
            save(state)
            print_checks(args, [{"name": "pytest", "bucket": ci["bucket"],
                                 "link": f"{URL}/actions/runs/{ci['run']}/job/1"}])
            return 0 if "--json" in args or ci["bucket"] == "pass" else 1  # as `gh` does
        elif args[:2] == ["pr", "merge"]:
            problem = merge(state, pr_number(args[2]), args[3] if len(args) > 3 else "")
            if problem:
                print(f"fake forge: {problem}", file=sys.stderr)
                return 1
            save(state)
            print(f"merged {args[2]}")
        elif args[:2] == ["pr", "view"]:
            n = pr_number(args[2])
            pr = state["prs"][n]
            print(json.dumps({"number": int(n), "url": f"{URL}/pull/{n}", "state": pr["state"].upper(),
                              "headRefName": pr["head"], "baseRefName": pr["base"],
                              "title": pr["title"]}))
        elif args[:2] == ["auth", "status"]:  # an agent checks it can reach the forge
            print("Logged in to forge.local as eval (fake forge)")
        elif args[:2] == ["run", "list"]:
            print("[]")  # main is never red here
        elif args[:2] == ["run", "view"]:
            run = int(args[2])
            print(next((c["log"] for c in state["ci"].values() if c["run"] == run), ""))
        elif args[:2] == ["run", "rerun"]:  # CI is deterministic here: the same result again
            print(f"rerun {args[2]}")
        else:
            print(f"fake forge: `gh {' '.join(args)}` is not allowed here", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
