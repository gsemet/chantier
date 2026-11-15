"""The eval sandbox: build its initial commit, publish a sandbox, and reset it to that commit.

    uv run --no-project python evals/kit/sandbox.py build [<dest>] [--record]
    uv run --no-project python evals/kit/sandbox.py publish <owner>/<name> [--yes]
    uv run --no-project python evals/kit/sandbox.py reset [--yes]
    uv run --no-project python evals/kit/sandbox.py merge <pr> [--workspace <dir>]

`build` turns `kit/sandbox/` into one root commit that is the same, down to its SHA-1, on every
machine, and compares that SHA-1 with `kit/sandbox.json`. `reset` puts the sandbox repository back
at the recorded commit: the only force push on the sandbox, and it does nothing without --yes; it
compares branches and tags only (GitHub keeps `refs/pull/*`), and refuses a repository that is not
a chantier eval sandbox (no `main`, or a ref whose history does not hold the recorded base).
`publish` creates a person's own public sandbox, pushes the base to it (a plain push to an empty
repository) and writes `sandbox.local.json`. `merge` is how the operator, who plays the user,
merges a run's PR: it is the kit's only merge, and `reset` stays the only force push.
One file names the repository (`sandbox.local.json`, else `sandbox.json`); no argument or variable
changes it, and `reset` refuses a repository whose history does not hold the recorded base.

Exit codes: 0 ok, 1 usage, 2 precondition, 4 external (git or gh failed).
Standard library only; POSIX and Windows.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

KIT = Path(__file__).resolve().parent
SOURCE = KIT / "sandbox"
RECORD = KIT / "sandbox.json"
LOCAL = KIT / "sandbox.local.json"  # git-ignored: a person's own sandbox
URL_OVERRIDE = None  # the dry run's local origin; nothing else sets it

BRANCH = "main"
NAME = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")

IDENTITY = "chantier eval kit <eval@example.com>"
DATE = "2026-11-12T00:00:00+00:00"
MESSAGE = "feat: shelf 0.1.0, the chantier eval sandbox\n"

SKIP_DIRS = {".venv", "__pycache__", ".pytest_cache"}
SKIP_NAMES = {"shelf.json"}

OK, USAGE, PRECONDITION, EXTERNAL = 0, 1, 2, 4
MERGE_WAIT, MERGE_TRIES = 5, 60  # seconds between two reads of an asynchronous merge, and reads


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


def resolve(cmd: list) -> list:
    """`gh` by its full path (`shutil.which` honours PATHEXT, so a `gh.cmd` launcher is found on
    Windows); None from `which` leaves the name, and the call says it is not on the PATH."""
    if cmd and cmd[0] == "gh":
        return [shutil.which("gh") or "gh", *cmd[1:]]
    return list(cmd)


def run(cmd, cwd=None, data=None, env=None, code=EXTERNAL):
    """Run a command; on failure raise Stop with the tool's own error text."""
    cmd = resolve(cmd)
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


def read_repository(path: Path) -> str:
    """The `repository` of a kit file, or a precondition stop naming the file."""
    try:
        name = json.loads(path.read_text(encoding="utf-8"))["repository"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise Stop(PRECONDITION, f"{path} is missing, not JSON or has no `repository` ({error}): "
                                 'it must be {"repository": "<owner>/<name>"}') from None
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise Stop(PRECONDITION, f"{path}: `repository` must be <owner>/<name>, not {name!r}")
    return name


def repository_source() -> tuple[str, str]:
    """The sandbox repository and the file it was read from: `sandbox.local.json` when it is
    there, else `sandbox.json`. The only reader; a malformed local file stops, it never falls back."""
    path = LOCAL if LOCAL.exists() else RECORD
    return read_repository(path), path.name


def repository() -> str:
    return repository_source()[0]


def url(name: str | None = None) -> str:
    return URL_OVERRIDE or f"https://github.com/{name or repository()}.git"


def announce(action: str) -> None:
    """The first line of a command that acts on the sandbox: which repository, read where."""
    name, source = repository_source()
    print(f"{action}: sandbox repository {name} (read from {source})", flush=True)


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
        keep = read_repository(RECORD)  # build records the base only; the repository stays as it is
        RECORD.write_text(json.dumps({"repository": keep, "base": sha}) + "\n", encoding="utf-8", newline="\n")
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
    """gh logged in with the `workflow` scope, and a git credential helper (not the repository)."""
    try:
        done = subprocess.run(resolve(["gh", "auth", "status"]), capture_output=True)
    except FileNotFoundError:
        raise Stop(PRECONDITION, "`gh` is not installed or not on the PATH") from None
    shown = (done.stdout + done.stderr).decode("utf-8", "replace")  # gh prints on either stream
    if done.returncode != 0:
        raise Stop(PRECONDITION, f"`gh auth status` failed: {shown.strip()}")
    scopes = next((line for line in shown.splitlines() if "scopes" in line.lower()), "")
    if "workflow" not in scopes.replace("'", " ").replace(",", " ").split():
        raise Stop(PRECONDITION, "the gh token lacks the `workflow` scope (needed to push "
                                 "`.github/workflows/`): run `gh auth refresh -s workflow`")
    helpers = subprocess.run(["git", "config", "--get-regexp", r"^credential\..*helper$"],
                             capture_output=True).stdout.decode("utf-8", "replace").strip()
    if not helpers:
        raise Stop(PRECONDITION, "git has no credential helper for github.com: run "
                                 "`gh auth setup-git` yourself (this script does not)")


def check_default_branch(name: str) -> None:
    default = json.loads(gh("repo", "view", name, "--json", "defaultBranchRef", code=PRECONDITION))
    if (default.get("defaultBranchRef") or {}).get("name") != BRANCH:
        raise Stop(PRECONDITION, f"the default branch of {name} is not {BRANCH}")


def parse_refs(text: str) -> dict[str, str]:
    """`git ls-remote` output as {ref: sha}, branches and tags only: no HEAD, no peeled tag, and
    nothing under refs/pull/ (GitHub keeps those forever and no push can delete them)."""
    refs = {}
    for line in text.splitlines():
        sha, _, ref = line.partition("\t")
        if ref.startswith(("refs/heads/", "refs/tags/")) and not ref.endswith("^{}"):
            refs[ref] = sha
    return refs


def remote_refs(where: str | None = None) -> dict[str, str]:
    """The refs of the sandbox (the parameter is for the evidence; no option sets it). `url()` is
    read at the call, so a dry run that rebinds the override is followed."""
    return parse_refs(run(["git", "ls-remote", where or url()], env=remote_env()))


def ref_problems(refs: dict, base: str) -> list[str]:
    """What keeps the refs from being only `main` at the base."""
    problems = []
    current = refs.get(f"refs/heads/{BRANCH}")
    if current != base:
        problems.append(f"main is at {current}, not {base}")
    others = sorted(r.removeprefix("refs/heads/") for r in refs
                    if r.startswith("refs/heads/") and r != f"refs/heads/{BRANCH}")
    tags = sorted(r.removeprefix("refs/tags/") for r in refs if r.startswith("refs/tags/"))
    if others:
        problems.append(f"branches other than main: {', '.join(others)}")
    if tags:
        problems.append(f"tags: {', '.join(tags)}")
    return problems


def open_prs() -> list[dict]:
    return json.loads(gh("pr", "list", "--repo", repository(), "--state", "open", "--limit", "1000",
                         "--json", "number,title,headRefName"))


def releases() -> list[str]:
    listed = json.loads(gh("release", "list", "--repo", repository(), "--limit", "1000", "--json", "tagName"))
    return [r["tagName"] for r in listed]


def holds_base(repo: Path, ref: str, base: str) -> bool:
    """Whether the sandbox's `ref` has the recorded base in its history: fetch it into the temporary
    build repository (which holds the base) and ask git. No other answer than yes or no."""
    run(["git", "fetch", "--quiet", "--no-tags", url(), ref], cwd=repo, env=remote_env())
    done = subprocess.run(["git", "merge-base", "--is-ancestor", base, "FETCH_HEAD^{commit}"],
                          cwd=repo, capture_output=True)
    if done.returncode not in (0, 1):
        return False  # not even a commit (a tag on a tree or a blob)
    return done.returncode == 0


def check_is_sandbox(repo: Path, refs: dict, base: str) -> None:
    """A precondition stop unless the repository is a chantier eval sandbox: it has `main`, and
    `main`, every other branch and every tag hold the recorded base. Changes nothing."""
    name = repository()
    if f"refs/heads/{BRANCH}" not in refs:
        raise Stop(PRECONDITION, f"no main on {name}: publish the base first (`sandbox.py publish`)")
    not_held = f"{name}'s main does not hold the recorded base {base}: not a chantier eval sandbox; nothing changed"
    for ref in [f"refs/heads/{BRANCH}", *sorted(r for r in refs if r != f"refs/heads/{BRANCH}")]:
        if not holds_base(repo, ref, base):
            raise Stop(PRECONDITION, not_held if ref == f"refs/heads/{BRANCH}" else
                       f"{name}'s {ref.removeprefix('refs/heads/').removeprefix('refs/tags/')} "
                       f"({ref}) does not hold the recorded base {base}: not a chantier eval "
                       "sandbox; nothing changed")


def cmd_reset(args) -> int:
    announce("reset")
    check_preconditions()
    sha, _, holder = build_in_temporary_folder()
    try:
        base = recorded_base()
        if sha != base:
            raise Stop(PRECONDITION, f"build gives {sha}, but sandbox.json records {base}: "
                                     "run build --record and commit sandbox.json")
        repo = holder / "repo"
        refs = remote_refs()
        check_is_sandbox(repo, refs, base)
        check_default_branch(repository())
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
        plan += [(f"close PR #{p['number']}", ["gh", "pr", "close", str(p["number"]), "--repo", repository()]) for p in prs]
        plan += [(f"delete release {t}", ["gh", "release", "delete", t, "--repo", repository(), "--yes"])
                 for t in release_tags]
        plan += [(f"delete tag {t}", ["git", "push", url(), "--delete", f"refs/tags/{t}"]) for t in tags]
        plan += [(f"delete branch {b}", ["git", "push", url(), "--delete", f"refs/heads/{b}"]) for b in branches]
        if current != base:
            plan.append((f"force-push {base} to {BRANCH}",
                         ["git", "push", "--force", url(), f"{base}:refs/heads/{BRANCH}"]))
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
    problems = ref_problems(remote_refs(), base)
    if open_prs():
        problems.append("a PR is still open")
    if releases():
        problems.append("a release is still there")
    if problems:
        raise Stop(EXTERNAL, "verification failed: " + "; ".join(problems))


# publish -----------------------------------------------------------------------------------------


def write_local(name: str) -> None:
    LOCAL.write_text(json.dumps({"repository": name}) + "\n", encoding="utf-8", newline="\n")


def repository_state(name: str) -> dict | None:
    """The repository as GitHub shows it (`isPrivate`, `defaultBranchRef`), or None if there is none."""
    try:
        done = subprocess.run(resolve(["gh", "repo", "view", name, "--json", "isPrivate,defaultBranchRef"]),
                              capture_output=True)
    except FileNotFoundError:
        raise Stop(PRECONDITION, "`gh` is not installed or not on the PATH") from None
    text = (done.stderr or done.stdout).decode("utf-8", "replace").strip()
    if done.returncode == 0:
        return json.loads(done.stdout.decode("utf-8", "replace"))
    if "could not resolve" in text.lower() or "not found" in text.lower():
        return None
    raise Stop(EXTERNAL, f"`gh repo view {name}` failed ({done.returncode}): {text}")


def cmd_publish(args) -> int:
    name = args.repository
    if not NAME.fullmatch(name):
        raise Stop(USAGE, f"publish takes <owner>/<name>, not {name!r}")
    print(f"publish: sandbox repository {name} (named by the argument; it will be written to "
          f"{LOCAL.name})", flush=True)
    check_preconditions()
    if LOCAL.exists():
        named = read_repository(LOCAL)
        if named != name:
            raise Stop(PRECONDITION, f"{LOCAL.name} already names {named}, not {name}: remove "
                                     f"{LOCAL} yourself to publish another sandbox")
    sha, _, holder = build_in_temporary_folder()
    try:
        base = recorded_base()
        if sha != base:
            raise Stop(PRECONDITION, f"build gives {sha}, but sandbox.json records {base}: "
                                     "run build --record and commit sandbox.json")
        found = repository_state(name)
        if found is not None:
            if found.get("isPrivate"):
                raise Stop(PRECONDITION, f"{name} is private: a chantier eval sandbox is public")
            refs = run(["git", "ls-remote", url(name)], env=remote_env()).strip()
            if refs:
                raise Stop(PRECONDITION, f"{name} is not empty (it has refs): publish never touches "
                                         "a repository with history; use `reset` on a sandbox")
        plan = ([f"create {name} (public)"] if found is None else [f"{name} exists, public and empty"])
        plan += [f"push the base {base} to refs/heads/{BRANCH} (a plain push)",
                 f"check {BRANCH} is the default branch and is not protected",
                 f"write {LOCAL} naming {name}"]
        for number, line in enumerate(plan, 1):
            print(f"plan {number}: {line}")
        if not args.yes:
            print("plan only: nothing changed; run publish --yes to run it")
            return OK
        if found is None:
            print(f"run: create {name}", flush=True)
            gh("repo", "create", name, "--public")
        print(f"run: push the base to {BRANCH}", flush=True)
        run(["git", "push", url(name), f"{base}:refs/heads/{BRANCH}"], cwd=holder / "repo",
            env=remote_env())
        check_default_branch(name)
        branch = json.loads(gh("api", f"repos/{name}/branches/{BRANCH}"))
        if branch.get("protected"):
            print(f"warning: {BRANCH} of {name} is protected; the sandbox's main is unprotected by "
                  "design: unprotect it yourself", file=sys.stderr)
        write_local(name)
        print(f"published {name}: main at {base}; named in {LOCAL}")
        print("next: uv run --no-project python evals/kit/setup.py <campaign> <workspace>   "
              "(no reset is needed after a publish)")
        return OK
    finally:
        remove(holder)


# merge -------------------------------------------------------------------------------------------


def checks_green(rollup: list[dict]) -> bool:
    """Every check passed: there is one, and each is `SUCCESS` (a skipped, neutral, pending or
    failed one is not green). The audit's J5 and `merge` share this rule."""
    return bool(rollup) and all((x.get("conclusion") or x.get("state")) == "SUCCESS" for x in rollup)


def merge_refusal(view: dict, prefix: str) -> str | None:
    """Why the PR is not merged (the first reason that holds), else None."""
    n, state = view.get("number"), str(view.get("state") or "")
    sha = str(view.get("headRefOid") or "")[:7]
    if state != "OPEN":
        return f"PR #{n} is {state.lower()}, not open"
    if not str(view.get("title") or "").startswith(prefix + " "):
        return f"PR #{n}'s title does not start with the run's prefix {prefix}"
    rollup = view.get("statusCheckRollup") or []
    if not checks_green(rollup):
        if not rollup:
            return f"PR #{n} has no check at its head {sha}"
        bad = [f"{x.get('name') or x.get('context')}={x.get('conclusion') or x.get('state') or 'pending'}"
               for x in rollup if (x.get("conclusion") or x.get("state")) != "SUCCESS"]
        return f"PR #{n}'s checks are not all green at its head {sha}: {', '.join(bad)}"
    return None


def pr_argument(text: str) -> str:
    """The PR number of `<n>` or of the sandbox's PR link."""
    if re.fullmatch(r"\d+", text):
        return text
    link = re.fullmatch(r"https://github\.com/([^/\s]+/[^/\s]+)/pull/(\d+)/?", text)
    if not link:
        raise Stop(USAGE, f"merge takes a PR number or the sandbox's PR link, not {text!r}")
    if link[1] != repository():
        raise Stop(PRECONDITION, f"merge works on {repository()} only: {text}")
    return link[2]


def cmd_merge(args) -> int:
    announce("merge")
    n = pr_argument(args.pr)
    workspace = Path(args.workspace).resolve() if args.workspace else Path.cwd().resolve()
    record = workspace.with_name(workspace.name + ".run.json")
    not_workspace = Stop(PRECONDITION, f"not a sandbox workspace: no {record.name} next to "
                                       f"{workspace.name}")
    try:
        run_record = json.loads(record.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise not_workspace from None
    if not isinstance(run_record, dict) or not run_record.get("prefix"):
        raise not_workspace
    if run_record.get("repository") != repository():
        raise Stop(PRECONDITION, f"the run record names {run_record.get('repository')}, not {repository()}")
    taken = merged_with(int(n))
    views = {}
    for m in taken:
        views[m] = json.loads(gh("pr", "view", str(m), "--repo", repository(), "--json",
                                 "number,state,title,headRefOid,statusCheckRollup"))
        refusal = merge_refusal(views[m], run_record["prefix"])
        if refusal:
            if m != int(n):
                refusal = f"PR #{n} is in a stack whose merge takes #{m}: {refusal}"
            print(f"sandbox.py: refused: {refusal}; nothing merged", file=sys.stderr)
            return PRECONDITION
    sha = views[int(n)]["headRefOid"]
    result = merge_async(n, sha)
    said = " ".join(f"#{m}" for m in taken)
    print(f"merged PR {said} at {sha[:7]} into {BRANCH} by rebase"
          + (f" (one stack merge, {result})" if len(taken) > 1 else f" ({result})"))
    return OK


def merged_with(n: int) -> list[int]:
    """The PRs a merge of #n takes, from the bottom: #n alone, or, when an open native stack
    holds it, each PR of that stack up to and including #n (GitHub merges them together)."""
    stacks = json.loads(gh("api", "-X", "GET", f"repos/{repository()}/stacks", "-F", "per_page=100"))
    for s in stacks if isinstance(stacks, list) else []:
        held = [p["number"] for p in s.get("pull_requests", []) if p.get("state") == "open"]
        if s.get("open") and n in held:
            return held[: held.index(n) + 1]
    return [n]


def merge_async(n: str, sha: str) -> str:
    """Merge by rebase through GitHub's asynchronous merge, the only merge that takes a PR in a
    native stack (and any other PR), then wait for its result; anything but merged stops."""
    path = f"repos/{repository()}/pulls/{n}/merge-async"
    try:
        answer = json.loads(gh("api", "-X", "PUT", path, "-f", "merge_method=rebase",
                               "-f", "merge_action=direct_merge", "-f", f"sha={sha}"))
        for _ in range(MERGE_TRIES):
            status = answer.get("status")
            details = answer.get("details") or {}
            if status == "merged":
                return "merged"
            if status != "pending":
                raise Stop(EXTERNAL, f"the asynchronous merge of PR #{n} ended {status}: "
                                     f"{details.get('message') or answer}")
            time.sleep(MERGE_WAIT)
            answer = json.loads(gh("api", "-X", "GET", f"{path}/{details['uuid']}"))
    except Stop as stop:
        raise Stop(stop.code, f"{stop}; nothing merged") from None
    raise Stop(EXTERNAL, f"the asynchronous merge of PR #{n} is still pending after "
                         f"{MERGE_TRIES * MERGE_WAIT} s; read the PR before merging again")


def main(argv=None) -> int:
    parser = Parser(prog="sandbox.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
    one = sub.add_parser("build", help="build the initial commit and compare it with sandbox.json")
    one.add_argument("dest", nargs="?", help="a new folder to leave the repository in")
    one.add_argument("--record", action="store_true", help="write the SHA-1 in sandbox.json")
    two = sub.add_parser("reset", help="put the sandbox back at the recorded commit")
    two.add_argument("--yes", action="store_true", help="run the plan (else print it only)")
    pub = sub.add_parser("publish", help="create your own public sandbox and point the kit at it")
    pub.add_argument("repository", help="<owner>/<name>")
    pub.add_argument("--yes", action="store_true", help="run the plan (else print it only)")
    three = sub.add_parser("merge", help="merge a run's PR by rebase, if it is open, prefixed and green")
    three.add_argument("pr", help="a PR number, or the sandbox's PR link")
    three.add_argument("--workspace", help="the sandbox workspace (default: the current folder)")
    args = parser.parse_args(argv)
    commands = {"build": cmd_build, "publish": cmd_publish, "reset": cmd_reset, "merge": cmd_merge}
    try:
        return commands[args.command](args)
    except Stop as stop:
        print(f"sandbox.py: {stop}", file=sys.stderr)
        return stop.code


if __name__ == "__main__":
    sys.exit(main())
