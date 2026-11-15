"""A local stand-in for GitHub's `gh`, for the eval kit's dry run: it answers for the sandbox
repository `sandbox.py` names (`sandbox.local.json`, else `sandbox.json`) and for no other, and
never reaches the network.

    gh <command>        called as `gh` (first on the PATH); $FAKE_GH_STATE is its JSON state,
                        $SANDBOX_FORGE_ORIGIN the bare repository that stands for the sandbox,
                        $SANDBOX_FORGE_REPOSITORY (the dry run only) the name it answers for

What it keeps of GitHub: pull requests, with a `refs/pull/<n>/head` in the origin when one opens or
its head moves (never deleted, as on GitHub); real checks (`uv run --locked pytest -q` on the PR's
head in a fresh clone, once per commit; a head marked pending stays pending, one marked pending for its
first k reads is pending for k reads of its rollup, then has its real checks); a rebase merge that
does not wait for the checks (the repository has no branch protection); releases. It answers
`auth status` (with the `workflow` scope), `repo view|create`, `pr create|view|list|checks|merge|close|edit`,
`release create|list|view|delete`, and `api` for the stacks (none) and the asynchronous merge;
anything else exits 1. Every call is logged in
`<state>.calls`. Standard library only.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sandbox  # noqa: E402  (the one reader of the sandbox repository's name)


def repo_name() -> str:
    """The repository this fake answers for: the one `sandbox.py` names. $SANDBOX_FORGE_REPOSITORY
    is the dry run's only handle on it, since the fake runs as a process of its own."""
    return os.environ.get("SANDBOX_FORGE_REPOSITORY") or sandbox.repository()


def pr_url() -> str:
    return f"https://github.com/{repo_name()}/pull/"


CI_COMMAND = ["uv", "run", "--locked", "pytest", "-q", "-p", "no:cacheprovider"]
GIT = ["git", "-c", "core.autocrlf=false", "-c", "user.name=sandbox forge",
       "-c", "user.email=forge@example.com"]


class Refused(Exception):
    """A call the fake does not take: its text goes to stderr, the exit is 1."""


def utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git(*args, cwd=None, check=True) -> str:
    done = subprocess.run([*GIT, *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    if check and done.returncode:
        raise Refused(f"git {' '.join(args[:2])} failed: {(done.stderr or done.stdout).strip()[-300:]}")
    return done.stdout.strip()


class Forge:
    """The state and the origin of one fake sandbox."""

    def __init__(self, state: Path, origin: str):
        self.state_path, self.origin = Path(state), str(origin)

    # state, one caller at a time -----------------------------------------------------------------

    def __enter__(self):
        lock = self.state_path.with_suffix(".lock")
        for _ in range(600):
            try:
                self.fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except FileExistsError:
                time.sleep(0.1)
        else:
            raise Refused("the state stayed locked for a minute")
        self.lock = lock
        self.state = (json.loads(self.state_path.read_text(encoding="utf-8")) if self.state_path.exists()
                      else {"next_pr": 1, "next_run": 1, "prs": {}, "ci": {}, "pending": [], "pending_reads": {},
                            "releases": {}})
        return self

    def __exit__(self, *exc):
        if exc[0] is None:
            self.state_path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
        os.close(self.fd)
        os.unlink(self.lock)

    def log(self, args: list[str]) -> None:
        with open(self.state_path.with_suffix(".calls"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": utc(), "cwd": os.getcwd(), "args": args}) + "\n")

    # the origin ----------------------------------------------------------------------------------

    def branch_sha(self, branch: str) -> str:
        out = git("--git-dir", self.origin, "rev-parse", "--verify", "--quiet",
                  f"refs/heads/{branch}^{{commit}}", check=False)
        if not out:
            raise Refused(f"no branch {branch} on the origin")
        return out

    def pull_ref(self, n: str, sha: str) -> None:
        git("--git-dir", self.origin, "update-ref", f"refs/pull/{n}/head", sha)

    def head(self, pr: dict) -> str:
        """The PR's head: the branch's tip while the PR is open, else the one it last had."""
        if pr["state"] == "open":
            try:
                sha = self.branch_sha(pr["head"])
            except Refused:
                return pr["head_sha"]
            if sha != pr["head_sha"]:
                pr["head_sha"] = sha
                self.pull_ref(str(pr["number"]), sha)
        return pr["head_sha"]

    # checks --------------------------------------------------------------------------------------

    def checks(self, pr: dict) -> list[dict]:
        """`statusCheckRollup` of the PR's head: run the tests there once; a pending head has none yet."""
        sha = self.head(pr)
        if sha in self.state["pending"]:
            return [{"name": "pytest", "workflowName": "ci", "status": "IN_PROGRESS", "conclusion": ""}]
        reads = self.state.setdefault("pending_reads", {})
        if reads.get(sha, 0) > 0:
            reads[sha] -= 1
            return [{"name": "pytest", "workflowName": "ci", "status": "IN_PROGRESS", "conclusion": ""}]
        if sha not in self.state["ci"]:
            self.state["ci"][sha] = self.run_ci(sha)
        return [{"name": "pytest", "workflowName": "ci", "status": "COMPLETED",
                 "conclusion": self.state["ci"][sha]["conclusion"]}]

    def run_ci(self, sha: str) -> dict:
        with tempfile.TemporaryDirectory(prefix="forge-ci-") as tmp:
            try:
                git("clone", "--quiet", "--no-checkout", self.origin, tmp)
                git("fetch", "--quiet", "origin", "+refs/pull/*/head:refs/remotes/origin/pull/*", cwd=tmp)
                git("checkout", "--quiet", "--detach", sha, cwd=tmp)
                env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "SHELF_DATA")}
                done = subprocess.run(CI_COMMAND, cwd=tmp, capture_output=True, text=True,
                                      encoding="utf-8", errors="replace", env=env)
                ok, log = done.returncode == 0, (done.stdout + done.stderr)[-2000:]
            finally:
                for root, dirs, files in os.walk(tmp):  # git objects are read-only on Windows
                    for name in dirs + files:
                        try:
                            os.chmod(os.path.join(root, name), 0o700)
                        except OSError:
                            pass
        run = self.state["next_run"]
        self.state["next_run"] = run + 1
        return {"conclusion": "SUCCESS" if ok else "FAILURE", "run": run, "log": log}

    # pull requests -------------------------------------------------------------------------------

    def create(self, title: str, base: str, head: str, body: str, draft: bool) -> str:
        n = self.state["next_pr"]
        self.state["next_pr"] = n + 1
        sha = self.branch_sha(head)
        self.state["prs"][str(n)] = {"number": n, "title": title, "base": base, "head": head,
                                     "head_sha": sha, "body": body, "state": "open", "draft": draft,
                                     "merged_at": None}
        self.pull_ref(str(n), sha)
        return f"{pr_url()}{n}"

    def pr(self, ref: str) -> dict:
        m = re.fullmatch(rf"(?:https://github\.com/{re.escape(repo_name())}/pull/)?(\d+)/?", ref)
        if not m:
            raise Refused(f"{ref!r} is not a pull request of {repo_name()}")
        if m[1] not in self.state["prs"]:
            raise Refused(f"no pull request #{m[1]} in {repo_name()}")
        return self.state["prs"][m[1]]

    def fields(self, pr: dict, names: list[str]) -> dict:
        out = {}
        for name in names:
            if name == "number":
                out[name] = pr["number"]
            elif name == "url":
                out[name] = f"{pr_url()}{pr['number']}"
            elif name == "title":
                out[name] = pr["title"]
            elif name == "body":
                out[name] = pr["body"]
            elif name == "state":
                out[name] = pr["state"].upper()
            elif name == "isDraft":
                out[name] = pr["draft"]
            elif name == "baseRefName":
                out[name] = pr["base"]
            elif name == "headRefName":
                out[name] = pr["head"]
            elif name == "headRefOid":
                out[name] = self.head(pr)
            elif name == "mergedAt":
                out[name] = pr["merged_at"]
            elif name == "autoMergeRequest":
                out[name] = None
            elif name == "statusCheckRollup":
                out[name] = self.checks(pr)
            else:
                raise Refused(f"unknown JSON field {name!r}")
        return out

    def merge(self, pr: dict, match: str | None) -> None:
        """A rebase merge, as GitHub does it: the PR's commits on top of the base, then pushed."""
        if pr["state"] != "open":
            raise Refused(f"pull request #{pr['number']} is {pr['state']}, not open")
        sha = self.head(pr)
        if match and sha != match:
            raise Refused(f"head commit {match} is not the head of #{pr['number']} ({sha})")
        with tempfile.TemporaryDirectory(prefix="forge-merge-") as tmp:
            try:
                git("clone", "--quiet", "--no-checkout", self.origin, tmp)
                git("checkout", "--quiet", "-B", "work", sha, cwd=tmp)
                git("rebase", "--quiet", f"origin/{pr['base']}", cwd=tmp)
                git("push", "--quiet", "origin", f"HEAD:refs/heads/{pr['base']}", cwd=tmp)
            finally:
                for root, dirs, files in os.walk(tmp):
                    for name in dirs + files:
                        try:
                            os.chmod(os.path.join(root, name), 0o700)
                        except OSError:
                            pass
        pr["state"], pr["merged_at"] = "merged", utc()

    # the staging the dry run does directly -------------------------------------------------------

    def mark_pending(self, ref: str) -> None:
        """The checks of this PR's head never end (a campaign's CI that is still running)."""
        self.state["pending"].append(self.head(self.pr(ref)))

    def mark_pending_for(self, ref: str, reads: int) -> None:
        """The checks of this PR's head are pending for its first `reads` reads of the rollup (a
        restack's CI that is still running), then are its real ones."""
        self.state.setdefault("pending_reads", {})[self.head(self.pr(ref))] = reads


# the command line ----------------------------------------------------------------------------------


def option(args: list[str], name: str) -> str | None:
    return args[args.index(name) + 1] if name in args else None


def positional(args: list[str], skip: int = 2) -> str:
    """The first argument after the command words that is no option nor an option's value."""
    valued = {"--repo", "-R", "--json", "--state", "--limit", "--title", "--body", "--body-file",
              "--base", "--head", "--match-head-commit", "--notes", "--notes-file", "-t", "-F", "-n"}
    rest, skip_next = [], False
    for arg in args[skip:]:
        if skip_next:
            skip_next = False
        elif arg in valued:
            skip_next = True
        elif not arg.startswith("-"):
            rest.append(arg)
    if not rest:
        raise Refused(f"`gh {' '.join(args[:skip])}` needs an argument")
    return rest[0]


def text_of(args: list[str], inline: str, from_file: str) -> str:
    path = option(args, from_file)
    return Path(path).read_text(encoding="utf-8") if path else (option(args, inline) or "")


def api(forge: Forge, args: list[str]) -> str:
    """The REST calls `sandbox.py merge` makes: the stacks (none: the fake makes no native
    stack) and the asynchronous rebase merge, which ends at once."""
    method = option(args, "-X") or "GET"
    path = next((a for a in args[1:] if a.startswith("repos/")), "")
    fields = dict(f.split("=", 1) for i, f in enumerate(args) if i and args[i - 1] in ("-f", "-F"))
    if method == "GET" and path == f"repos/{repo_name()}/stacks":
        return "[]"
    if method == "GET" and path == f"repos/{repo_name()}/branches/main":
        return json.dumps({"name": "main", "protected": False})
    m = re.fullmatch(rf"repos/{re.escape(repo_name())}/pulls/(\d+)/merge-async", path)
    if method == "PUT" and m:
        if fields.get("merge_method") != "rebase":
            raise Refused("this repository merges by rebase: merge_method=rebase")
        pr = forge.pr(m[1])
        forge.merge(pr, fields.get("sha"))
        return json.dumps({"status": "merged", "details": {"sha": pr["head_sha"]}})
    raise Refused(f"`gh {' '.join(args)}` is not something this fake forge does")


def handle(forge: Forge, args: list[str]) -> str | int:
    """One call. Returns the text to print, or an exit code (after printing its own text)."""
    repo = option(args, "--repo") or option(args, "-R")
    if repo and repo != repo_name():
        raise Refused(f"this fake forge answers for {repo_name()} only, not {repo}")
    words = args[:2]
    if words == ["auth", "status"]:
        return ("github.com\n  Logged in to github.com account eval (fake forge)\n"
                "  - Token scopes: 'gist', 'read:org', 'repo', 'workflow'")
    if words == ["repo", "view"]:
        name = positional(args)
        if name != repo_name():
            raise Refused(f"this fake forge answers for {repo_name()} only, not {name}")
        if forge.state.get("repo_missing"):
            raise Refused(f"GraphQL: Could not resolve to a Repository with the name '{name}'.")
        has_main = bool(git("--git-dir", forge.origin, "for-each-ref", "refs/heads/main"))
        return json.dumps({"isPrivate": False, "defaultBranchRef": {"name": "main"} if has_main else None})
    if words == ["repo", "create"]:
        name = positional(args, 2)
        if name != repo_name() or "--public" not in args:
            raise Refused(f"this fake forge creates {repo_name()} as a public repository only")
        if not forge.state.get("repo_missing"):
            raise Refused(f"{name} already exists")
        forge.state["repo_missing"] = False
        return f"https://github.com/{name}"
    if words == ["pr", "create"]:
        title, base, head = option(args, "--title"), option(args, "--base") or "main", option(args, "--head")
        if not title or not head:
            raise Refused("pr create needs --title and --head")
        return forge.create(title, base, head, text_of(args, "--body", "--body-file"), "--draft" in args)
    if words == ["pr", "list"]:
        state = option(args, "--state") or "open"
        wanted = {"open": {"open"}, "closed": {"closed"}, "merged": {"merged"},
                  "all": {"open", "closed", "merged"}}.get(state)
        if wanted is None:
            raise Refused(f"unknown --state {state}")
        names = (option(args, "--json") or "number,title,headRefName").split(",")
        rows = [forge.fields(p, names) for p in forge.state["prs"].values() if p["state"] in wanted]
        return json.dumps(rows[:int(option(args, "--limit") or 30)])
    if words == ["pr", "view"]:
        pr = forge.pr(positional(args))
        names = (option(args, "--json") or "number,title,state,url").split(",")
        return json.dumps(forge.fields(pr, names))
    if words == ["pr", "checks"]:
        pr = forge.pr(positional(args))
        rows = forge.checks(pr)
        buckets = [{"pass": "pass", "SUCCESS": "pass", "": "pending"}.get(r["conclusion"], "fail")
                   for r in rows]
        if "--json" in args:
            print(json.dumps([{"name": r["name"], "state": r["conclusion"] or r["status"], "bucket": b}
                              for r, b in zip(rows, buckets)]))
        else:
            for r, b in zip(rows, buckets):
                print(f"{r['name']}\t{b}\t{pr_url()}{pr['number']}/checks")
        return 8 if "pending" in buckets else 1 if "fail" in buckets else 0
    if words == ["pr", "merge"]:
        if "--rebase" not in args:
            raise Refused("this repository merges by rebase: use --rebase")
        pr = forge.pr(positional(args))
        forge.merge(pr, option(args, "--match-head-commit"))
        return f"merged #{pr['number']}"
    if args[:1] == ["api"]:
        return api(forge, args)
    if words == ["pr", "close"]:
        pr = forge.pr(positional(args))
        if pr["state"] == "merged":
            raise Refused(f"pull request #{pr['number']} is merged")
        pr["state"] = "closed"
        return f"closed #{pr['number']}"
    if words == ["pr", "edit"]:
        pr = forge.pr(positional(args))
        for flag, key in (("--title", "title"), ("--base", "base")):
            if option(args, flag):
                pr[key] = option(args, flag)
        if "--body" in args or "--body-file" in args:
            pr["body"] = text_of(args, "--body", "--body-file")
        return f"{pr_url()}{pr['number']}"
    if words == ["release", "create"]:
        tag = positional(args)
        tags = git("--git-dir", forge.origin, "tag", "--list", tag)
        if "--verify-tag" in args and not tags:
            raise Refused(f"tag {tag} is not on the origin")
        forge.state["releases"][tag] = {"tagName": tag, "name": option(args, "--title") or tag,
                                        "body": text_of(args, "--notes", "--notes-file")}
        return f"https://github.com/{repo_name()}/releases/tag/{tag}"
    if words == ["release", "list"]:
        names = (option(args, "--json") or "tagName").split(",")
        return json.dumps([{k: v[k] for k in names} for v in forge.state["releases"].values()])
    if words == ["release", "view"]:
        tag = positional(args)
        if tag not in forge.state["releases"]:
            raise Refused("release not found")
        names = (option(args, "--json") or "tagName,name,body").split(",")
        return json.dumps({k: forge.state["releases"][tag][k] for k in names})
    if words == ["release", "delete"]:
        tag = positional(args)
        if tag not in forge.state["releases"]:
            raise Refused("release not found")
        del forge.state["releases"][tag]
        return f"deleted release {tag}"
    raise Refused(f"`gh {' '.join(args)}` is not something this fake forge does")


def main(argv: list[str]) -> int:
    state, origin = os.environ.get("FAKE_GH_STATE"), os.environ.get("SANDBOX_FORGE_ORIGIN")
    if not state or not origin:
        print("fake forge: FAKE_GH_STATE and SANDBOX_FORGE_ORIGIN are not set", file=sys.stderr)
        return 1
    forge = Forge(Path(state), origin)
    forge.log(argv)
    try:
        with forge:
            out = handle(forge, argv)
    except Refused as why:
        print(f"gh (fake forge): {why}", file=sys.stderr)
        return 1
    if isinstance(out, int):
        return out
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
