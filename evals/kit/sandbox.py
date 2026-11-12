"""The eval sandbox: build its initial commit, and reset the sandbox to it.

    uv run --no-project python evals/kit/sandbox.py build [<dest>] [--record]
    uv run --no-project python evals/kit/sandbox.py reset [--yes]

`build` turns `kit/sandbox/` into one root commit that is the same, down to its SHA-1, on every
machine, and compares that SHA-1 with `kit/sandbox.json`. `reset` puts the sandbox repository back
at the recorded commit: the only force push on the sandbox, and it does nothing without --yes.
The repository is a constant: no argument or variable changes it.

Exit codes: 0 ok, 1 usage, 2 precondition, 4 external (git or gh failed).
Standard library only; POSIX and Windows.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parent
SOURCE = KIT / "sandbox"
RECORD = KIT / "sandbox.json"

REPO = "gsemet/chantier-eval-sandbox"
URL = f"https://github.com/{REPO}.git"
BRANCH = "main"

IDENTITY = "chantier eval kit <eval@example.com>"
DATE = "2026-11-12T00:00:00+00:00"
MESSAGE = "feat: shelf 0.1.0, the chantier eval sandbox\n"

SKIP_DIRS = {".venv", "__pycache__", ".pytest_cache"}
SKIP_NAMES = {"shelf.json"}

OK, USAGE, PRECONDITION, EXTERNAL = 0, 1, 2, 4


class Stop(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"sandbox.py: {message}", file=sys.stderr)
        raise SystemExit(USAGE)


def git_env() -> dict:
    """The user's git config reaches nothing: no autocrlf, no signing, no template, no hooks."""
    env = dict(os.environ)
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
    return env


def remote_env() -> dict:
    """Talking to GitHub keeps the user's git config (credential helper); it never prompts."""
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def run(cmd, cwd=None, data=None, env=None, code=EXTERNAL):
    """Run a command; on failure raise Stop with the tool's own error text."""
    try:
        done = subprocess.run(cmd, cwd=cwd, input=data, capture_output=True, env=env)
    except FileNotFoundError:
        raise Stop(code, f"`{cmd[0]}` is not installed or not on the PATH") from None
    if done.returncode != 0:
        text = (done.stderr or done.stdout).decode("utf-8", "replace").strip()
        raise Stop(code, f"`{' '.join(cmd)}` failed ({done.returncode}): {text}")
    return done.stdout.decode("utf-8", "replace")


def remove(path: Path) -> None:
    """Delete a folder with a git repository in it (its objects are read-only on Windows)."""
    for item in [path, *path.rglob("*")]:
        try:
            os.chmod(item, stat.S_IRWXU)
        except OSError:
            pass
    shutil.rmtree(path, ignore_errors=True)


def project_files() -> dict[str, bytes]:
    """Every file of the project, by posix path, with LF line ends."""
    files = {}
    for folder, dirs, names in os.walk(SOURCE):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in names:
            if name in SKIP_NAMES or name.endswith(".pyc"):
                continue
            path = Path(folder) / name
            files[path.relative_to(SOURCE).as_posix()] = path.read_bytes().replace(b"\r\n", b"\n")
    return dict(sorted(files.items()))


def write_tree(repo: Path, entries: dict, env: dict) -> str:
    lines = []
    for name, value in sorted(entries.items()):
        if isinstance(value, dict):
            lines.append(f"040000 tree {write_tree(repo, value, env)}\t{name}")
        else:
            blob = run(["git", "hash-object", "-t", "blob", "-w", "--no-filters", "--stdin"],
                       cwd=repo, data=value, env=env).strip()
            lines.append(f"100644 blob {blob}\t{name}")
    return run(["git", "mktree"], cwd=repo, data=("\n".join(lines) + "\n").encode("utf-8"), env=env).strip()


def commit_object(tree: str) -> bytes:
    stamp = f"{int(datetime.datetime.fromisoformat(DATE).timestamp())} +0000"
    text = f"tree {tree}\nauthor {IDENTITY} {stamp}\ncommitter {IDENTITY} {stamp}\n\n{MESSAGE}"
    return text.encode("utf-8")


def build(dest: Path) -> tuple[str, int]:
    """Make the initial commit in a new repository at dest; return its SHA-1 and its file count."""
    files = project_files()
    if not files:
        raise Stop(PRECONDITION, f"no file under {SOURCE}")
    nested: dict = {}
    for path, data in files.items():
        *folders, name = path.split("/")
        node = nested
        for folder in folders:
            node = node.setdefault(folder, {})
        node[name] = data
    env = git_env()
    run(["git", "init", "-q", "-b", BRANCH, "--template=", str(dest)], env=env)
    tree = write_tree(dest, nested, env)
    sha = run(["git", "hash-object", "-t", "commit", "-w", "--stdin"], cwd=dest,
              data=commit_object(tree), env=env).strip()
    run(["git", "update-ref", f"refs/heads/{BRANCH}", sha], cwd=dest, env=env)
    run(["git", "reset", "-q", "--hard", sha], cwd=dest, env=env)
    return sha, len(files)


def build_in_temporary_folder() -> tuple[str, int, Path]:
    """Build somewhere temporary; the caller removes the returned folder."""
    holder = Path(tempfile.mkdtemp(prefix="chantier-sandbox-"))
    try:
        sha, count = build(holder / "repo")
    except BaseException:
        remove(holder)
        raise
    return sha, count, holder


def recorded_base() -> str:
    try:
        return json.loads(RECORD.read_text(encoding="utf-8"))["base"]
    except (OSError, ValueError, KeyError) as error:
        raise Stop(PRECONDITION, f"{RECORD} is missing or has no `base` ({error}); "
                                 "run build --record") from None


def cmd_build(args) -> int:
    holder = None
    if args.dest:
        dest = Path(args.dest)
        if dest.exists():
            raise Stop(PRECONDITION, f"{dest} already exists")
        sha, count = build(dest)
    else:
        sha, count, holder = build_in_temporary_folder()
    if holder:
        remove(holder)
    print(f"base {sha}")
    print(f"{count} files")
    if args.record:
        RECORD.write_text(json.dumps({"repository": REPO, "base": sha}) + "\n", encoding="utf-8", newline="\n")
        print(f"recorded in {RECORD}")
        return OK
    try:
        recorded = recorded_base()
    except Stop:
        recorded = None
    if recorded != sha:
        print(f"built:    {sha}")
        print(f"recorded: {recorded}")
        print("run build --record and commit sandbox.json")
        return PRECONDITION
    return OK


# reset -------------------------------------------------------------------------------------------


def gh(*args, code=EXTERNAL) -> str:
    return run(["gh", *args], code=code)


def check_preconditions() -> None:
    try:
        done = subprocess.run(["gh", "auth", "status"], capture_output=True)
    except FileNotFoundError:
        raise Stop(PRECONDITION, "`gh` is not installed or not on the PATH") from None
    shown = (done.stdout + done.stderr).decode("utf-8", "replace")  # gh prints on either stream
    if done.returncode != 0:
        raise Stop(PRECONDITION, f"`gh auth status` failed: {shown.strip()}")
    scopes = next((line for line in shown.splitlines() if "scopes" in line.lower()), "")
    if "workflow" not in scopes.replace("'", " ").replace(",", " ").split():
        raise Stop(PRECONDITION, "the gh token lacks the `workflow` scope (needed to push "
                                 "`.github/workflows/`): run `gh auth refresh -s workflow`")
    default = json.loads(gh("repo", "view", REPO, "--json", "defaultBranchRef", code=PRECONDITION))
    if (default.get("defaultBranchRef") or {}).get("name") != BRANCH:
        raise Stop(PRECONDITION, f"the default branch of {REPO} is not {BRANCH}")
    helpers = subprocess.run(["git", "config", "--get-regexp", r"^credential\..*helper$"],
                             capture_output=True).stdout.decode("utf-8", "replace").strip()
    if not helpers:
        raise Stop(PRECONDITION, "git has no credential helper for github.com: run "
                                 "`gh auth setup-git` yourself (this script does not)")


def remote_refs() -> dict[str, str]:
    refs = {}
    for line in run(["git", "ls-remote", URL], env=remote_env()).splitlines():
        sha, _, ref = line.partition("\t")
        if ref != "HEAD" and not ref.endswith("^{}"):
            refs[ref] = sha
    return refs


def open_prs() -> list[dict]:
    return json.loads(gh("pr", "list", "--repo", REPO, "--state", "open", "--limit", "1000",
                         "--json", "number,title,headRefName"))


def releases() -> list[str]:
    listed = json.loads(gh("release", "list", "--repo", REPO, "--limit", "1000", "--json", "tagName"))
    return [r["tagName"] for r in listed]


def cmd_reset(args) -> int:
    check_preconditions()
    sha, _, holder = build_in_temporary_folder()
    try:
        base = recorded_base()
        if sha != base:
            raise Stop(PRECONDITION, f"build gives {sha}, but sandbox.json records {base}: "
                                     "run build --record and commit sandbox.json")
        repo = holder / "repo"
        refs = remote_refs()
        prs, release_tags = open_prs(), releases()
        tags = sorted(r.removeprefix("refs/tags/") for r in refs if r.startswith("refs/tags/"))
        branches = sorted(r.removeprefix("refs/heads/") for r in refs
                          if r.startswith("refs/heads/") and r != f"refs/heads/{BRANCH}")
        current = refs.get(f"refs/heads/{BRANCH}")

        print(f"main is at {current}")
        shown_prs = [f"#{p['number']} {p['title']} ({p['headRefName']})" for p in prs]
        print(f"open PRs: {', '.join(shown_prs) or 'none'}")
        print(f"branches other than main: {', '.join(branches) or 'none'}")
        print(f"tags: {', '.join(tags) or 'none'}")
        print(f"releases: {', '.join(release_tags) or 'none'}")

        plan = []
        plan += [(f"close PR #{p['number']}", ["gh", "pr", "close", str(p["number"]), "--repo", REPO]) for p in prs]
        plan += [(f"delete release {t}", ["gh", "release", "delete", t, "--repo", REPO, "--yes"])
                 for t in release_tags]
        plan += [(f"delete tag {t}", ["git", "push", URL, "--delete", f"refs/tags/{t}"]) for t in tags]
        plan += [(f"delete branch {b}", ["git", "push", URL, "--delete", f"refs/heads/{b}"]) for b in branches]
        if current != base:
            plan.append((f"force-push {base} to {BRANCH}",
                         ["git", "push", "--force", URL, f"{base}:refs/heads/{BRANCH}"]))
        if not plan:
            print(f"sandbox already at {base}: nothing to do")
            return OK
        for number, (line, _) in enumerate(plan, 1):
            print(f"plan {number}: {line}")
        if not args.yes:
            print("plan only: nothing changed; run reset --yes to run it")
            return OK
        for line, cmd in plan:
            print(f"run: {line}", flush=True)
            run(cmd, cwd=repo, env=remote_env())
        verify(base)
        print(f"sandbox reset: main at {base}")
        return OK
    finally:
        remove(holder)


def verify(base: str) -> None:
    problems = []
    refs = remote_refs()
    if refs != {f"refs/heads/{BRANCH}": base}:
        problems.append(f"refs are {refs}, expected only refs/heads/{BRANCH} at {base}")
    if open_prs():
        problems.append("a PR is still open")
    if releases():
        problems.append("a release is still there")
    if problems:
        raise Stop(EXTERNAL, "verification failed: " + "; ".join(problems))


def main(argv=None) -> int:
    parser = Parser(prog="sandbox.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
    one = sub.add_parser("build", help="build the initial commit and compare it with sandbox.json")
    one.add_argument("dest", nargs="?", help="a new folder to leave the repository in")
    one.add_argument("--record", action="store_true", help="write the SHA-1 in sandbox.json")
    two = sub.add_parser("reset", help="put the sandbox back at the recorded commit")
    two.add_argument("--yes", action="store_true", help="run the plan (else print it only)")
    args = parser.parse_args(argv)
    try:
        return cmd_build(args) if args.command == "build" else cmd_reset(args)
    except Stop as stop:
        print(f"sandbox.py: {stop}", file=sys.stderr)
        return stop.code


if __name__ == "__main__":
    sys.exit(main())
