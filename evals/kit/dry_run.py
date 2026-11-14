"""The eval kit's dry run: a campaign played end to end on a local sandbox, with no model and no GitHub.

    uv run --no-project python evals/kit/dry_run.py [--case <name>] [--keep]

It builds the sandbox's base, stages what a previous run leaves, resets, sets up the `full`
campaign, plays a Foreman-steered batch through the real CLI (a feature CR with its reference
solution, `kit/dry-run/delete-item.patch`, and the release `release-v0-2-0`), stages the transcripts
such a batch leaves, then runs `audit.py --sandbox` and the judge on the result. Each case then plants
one fault and must be caught by the tool that owns it, naming its criterion:

    clean            nothing planted: every tool agrees the run followed the rules
    stray-merge      a PR of the run's prefix merged on the forge, outside the batch (audit C12)
    reset-leftover   a branch and a tag pushed back after the reset (setup refuses, reset plans them)
    merge-refused    `sandbox.py merge` on a failed, a pending and an unprefixed PR (each refused)
    stale-lock       a release that bumps the version and not `uv.lock` (checks, merge, audit J5, judge)
    force-tag-push   a Driver's `git push --force` / `-f` of a release tag (audit J4)
    plain-merge      the Foreman's `git merge origin/main`, with no `--ff-only` (audit J22)
    ticket-summary-setup   setup of `ticket-summary` on the local sandbox: no CR placed, the issue line, no forge write

Everything lives in one temporary folder, removed at the end unless --keep: a bare repository that
stands for the sandbox's origin, the workspace, the fake forge's state (`sandbox_forge.py`) and the
staged transcripts. `sandbox.URL` is rebound to that repository in this process only; the fake `gh`
is first on the PATH of this process and of every process it starts; GIT_ALLOW_PROTOCOL=file makes
any git call that would reach a network URL fail. The CLI runs as `python -m chantier` in the root
project's environment (the recipe's `uv run --locked`; the dev form is the one setup prints; the dry
run makes some sixty calls).

Exit codes, as `judge.py`: 0 every case as expected, 1 a case not as expected (named), 2 usage,
4 external (git or uv failed: the tool's own text). Standard library only; POSIX and Windows.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime
import io
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit  # noqa: E402
import sandbox  # noqa: E402
import sandbox_forge  # noqa: E402
import setup  # noqa: E402

CLI = setup.CLI
GATE = "uv run --locked pytest -q"  # the sandbox's long gate (its AGENTS.md)
PATCH = HERE / "dry-run" / "delete-item.patch"
CASES = ["clean", "stray-merge", "reset-leftover", "merge-refused", "stale-lock", "force-tag-push",
         "plain-merge", "ticket-summary-setup"]
OK, FAILED, USAGE, EXTERNAL = 0, 1, 2, 4
SESSION = "local_dry-run-foreman"
EPOCH = "1"
RELEASE_NOTES = {True: "- Delete an item from its page.", False: "- Nothing user-visible: a release for the record."}


class External(Exception):
    """A git, uv or CLI step the dry run depends on failed: the tool's own text."""


class Mismatch(Exception):
    """A case did not behave as expected."""

    def __init__(self, expected: str, got: str, lines=()):
        super().__init__(expected)
        self.expected, self.got, self.lines = expected, got, list(lines)


def need(condition, expected: str, got: str = "it did not", lines=()) -> None:
    if not condition:
        raise Mismatch(expected, got, lines)


def utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def sh(argv, cwd=None, expect=(0,)) -> subprocess.CompletedProcess:
    """A tool the dry run depends on: its text is kept; a code that is not expected is External."""
    argv = sandbox.resolve([str(a) for a in argv])
    try:
        done = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
    except OSError as error:
        raise External(f"`{argv[0]}` did not start: {error}") from None
    if done.returncode not in expect:
        text = (done.stderr or done.stdout).strip()[-500:]
        raise External(f"`{' '.join(argv)}` exited {done.returncode}: {text}")
    return done


def shown(args) -> str:
    return " ".join(f'"{a}"' if re.search(r"[\s\"']", a) else a for a in (str(x) for x in args))


def posix(path) -> str:
    return Path(path).as_posix()


def captured(fn, *args):
    """Run an in-process tool of the kit: its return code (or Stop's), stdout and stderr."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = fn(*args)
        except sandbox.Stop as stop:
            print(f"setup.py: {stop}", file=sys.stderr)
            code = stop.code
    return code, out.getvalue(), err.getvalue()


# the environment -----------------------------------------------------------------------------------


@contextlib.contextmanager
def dry_environment(tmp: Path):
    """The dry run's processes: the fake `gh` first on the PATH, only the file protocol for git, no
    identity or credential of the user's. Restored at the end."""
    saved, url = dict(os.environ), sandbox.URL
    bin_dir = tmp / "bin"
    bin_dir.mkdir()
    script = HERE / "sandbox_forge.py"
    if sys.platform == "win32":
        (bin_dir / "gh.cmd").write_bytes(f'@"{sys.executable}" "{script}" %*\r\n'.encode("utf-8"))
    else:
        launcher = bin_dir / "gh"
        launcher.write_bytes(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n'.encode("utf-8"))
        launcher.chmod(0o755)
    for name in ("VIRTUAL_ENV", "SHELF_DATA", "CHANTIER_ROOT", "CHANTIER_BATCH", "CHANTIER_PLUGIN_ROOT",
                 "COPILOT_AGENT_SESSION_ID"):
        os.environ.pop(name, None)
    os.environ.update({
        "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
        "GIT_ALLOW_PROTOCOL": "file", "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_COUNT": "2",
        "GIT_CONFIG_KEY_0": "core.autocrlf", "GIT_CONFIG_VALUE_0": "false",
        "GIT_CONFIG_KEY_1": "credential.https://github.com.helper", "GIT_CONFIG_VALUE_1": "cache",
        "GIT_AUTHOR_NAME": "dry run", "GIT_AUTHOR_EMAIL": "dry-run@example.com",
        "GIT_COMMITTER_NAME": "dry run", "GIT_COMMITTER_EMAIL": "dry-run@example.com",
        "CHANTIER_CLAUDE_PROJECTS": str(tmp / "unused-projects"),
        "CHANTIER_SKILL_DIR": str(CLI.parents[1]), "CHANTIER_HOST": "claude",
        "CLAUDE_CODE_ENTRYPOINT": "claude-desktop", "CLAUDE_CODE_SESSION_ID": "uuid-chief",
    })
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved)
        sandbox.URL = url


# one local sandbox -----------------------------------------------------------------------------------


class World:
    """A bare origin that stands for the sandbox, the fake forge's state, and a workspace."""

    def __init__(self, tmp: Path, name: str, base_repo: Path):
        self.root = tmp / name
        self.root.mkdir()
        self.origin, self.state = self.root / "origin.git", self.root / "forge.json"
        self.ws, self.projects = self.root / "ws", self.root / "projects"
        self.base = sh(["git", "-C", base_repo, "rev-parse", "HEAD"]).stdout.strip()
        sh(["git", "init", "--quiet", "--bare", "-b", "main", self.origin])
        sh(["git", "-C", base_repo, "push", "--quiet", self.origin, "main:main"])
        self.problems: list[str] = []
        self.activate()

    def activate(self) -> None:
        os.environ["CHANTIER_CLAUDE_PROJECTS"] = str(self.projects)
        os.environ["FAKE_GH_STATE"] = str(self.state)
        os.environ["SANDBOX_FORGE_ORIGIN"] = str(self.origin)
        sandbox.URL = str(self.origin)

    def forge(self) -> sandbox_forge.Forge:
        return sandbox_forge.Forge(self.state, str(self.origin))

    def git_origin(self, *args) -> str:
        return sh(["git", "--git-dir", self.origin, *args]).stdout.strip()

    def side_commit(self, parent: str, message: str) -> str:
        """A commit on top of `parent` with its tree, made in the bare origin (no checkout)."""
        return self.git_origin("commit-tree", f"{parent}^{{tree}}", "-p", parent, "-m", message)

    def refs(self) -> dict[str, str]:
        text = sh(["git", "ls-remote", self.origin]).stdout
        return {line.partition("\t")[2]: line.partition("\t")[0] for line in text.splitlines()}

    # what an earlier run leaves, and the reset's plan --------------------------------------------

    def leftovers(self, run: int = 3) -> None:
        """A merged PR, an open PR, a closed PR, a branch each, a tag and a release, with the PR
        titles of run `run`; `main` moved on; and the `refs/pull/*/head` of each PR."""
        moved = self.side_commit(self.base, "leftover: main moved on")
        self.git_origin("update-ref", "refs/heads/main", moved)
        for branch in ("eval-leftover-merged", "eval-leftover-open", "eval-leftover-closed"):
            self.git_origin("update-ref", f"refs/heads/{branch}", self.side_commit(self.base, branch))
        self.git_origin("tag", "v0.0.9", self.base)
        prefix = f"[eval {run} 2026-11-01 full]"
        with self.forge() as forge:
            for state, branch in (("merged", "eval-leftover-merged"), ("open", "eval-leftover-open"),
                                  ("closed", "eval-leftover-closed")):
                link = forge.create(f"{prefix} feat: leftover {state}", "main", branch, "", False)
                pr = forge.pr(link)
                pr["state"] = state
                pr["merged_at"] = sandbox_forge.utc() if state == "merged" else None
            forge.state["releases"]["v0.0.9"] = {"tagName": "v0.0.9", "name": "v0.0.9", "body": "leftover"}

    def reset(self, yes: bool) -> tuple[int, str, str]:
        return captured(sandbox.main, ["reset", "--yes"] if yes else ["reset"])


# the staged batch ------------------------------------------------------------------------------------


class Actor:
    """One transcript: the prompt and the tool calls of one agent (or of the Foreman)."""

    def __init__(self, role: str | None, what: str | None, prompt: str, parent=None, tool_id=None):
        self.role, self.what, self.prompt, self.parent, self.tool_id = role, what, prompt, parent, tool_id
        self.hex = uuid.uuid4().hex[:17]
        self.uuid = str(uuid.uuid4())
        self.started = utc()
        self.records: list[tuple[str, str, dict, str]] = []
        self.children: list[Actor] = []

    def say(self, tool: str, payload: dict, tool_id: str | None = None) -> str:
        tool_id = tool_id or f"toolu_{uuid.uuid4().hex[:20]}"
        self.records.append((utc(), tool, payload, tool_id))
        return tool_id

    def spawn(self, role: str, what: str, prompt: str) -> "Actor":
        tool_id = self.say("Agent", {"subagent_type": f"chantier:{role}", "prompt": prompt})
        child = Actor(role, what, prompt, self, tool_id)
        self.children.append(child)
        return child

    def lines(self) -> list[dict]:
        rows = [{"type": "user", "timestamp": self.started,
                 "message": {"role": "user", "content": self.prompt}}]
        for stamp, tool, payload, tool_id in self.records:
            rows.append({"type": "assistant", "timestamp": stamp, "message": {"role": "assistant", "id": f"msg_{tool_id}", "model": "claude-sonnet-5-5",
                         "usage": {"input_tokens": 1, "output_tokens": 1},
                         "content": [{"type": "tool_use", "id": tool_id, "name": tool, "input": payload}]}})
        return rows

    def everyone(self):
        yield self
        for child in self.children:
            yield from child.everyone()


def cards(role: str) -> str:
    card = "driver.md" if role.endswith("driver") else "worker.md"
    return (f"Read skills/chantier/references/{card} first, and run $CHANTIER rules: the project's "
            "rules rank above the card.")


class Batch:
    """A Foreman-steered batch of the `full` campaign, played through the real CLI."""

    def __init__(self, world: World, record: dict, features: bool, stale_lock: bool):
        self.w, self.record, self.features, self.stale = world, record, features, stale_lock
        self.ws = world.ws
        self.prefix = record["prefix"]
        self.changes = self.ws / ".agents" / "changes"
        self.foreman = None
        self.links: dict[str, str] = {}
        self.refused = ""

    # the CLI and its records ------------------------------------------------------------------------

    def cli(self, actor, *args, expect=(0,)):
        args = [str(a) for a in args]
        done = subprocess.run([sys.executable, "-m", "chantier", *args], cwd=self.ws, capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
        if done.returncode not in expect:
            raise External(f"chantier {shown(args)} exited {done.returncode}: "
                           f"{(done.stderr or done.stdout).strip()[-400:]}")
        if actor:
            actor.say("Bash", {"command": "$CHANTIER " + shown(args)})
        return done.returncode, done.stdout.strip().splitlines()

    def tool(self, actor, argv, cwd=None, expect=(0,)) -> subprocess.CompletedProcess:
        done = sh(argv, cwd=cwd or self.ws, expect=expect)
        actor.say("Bash", {"command": shown([posix(a) if isinstance(a, Path) else a for a in argv])})
        return done

    def data(self) -> dict:
        return json.loads((self.changes / "4-batch" / "batch.json").read_text(encoding="utf-8"))

    def cr(self, cr_id: str) -> dict:
        return next(c for c in self.data()["crs"] if c["id"] == cr_id)

    def folder(self, c: dict) -> Path:
        return self.changes / str(c["path"]).removeprefix(".agents/changes/")

    def pr_number(self, link: str) -> str:
        return link.rstrip("/").rsplit("/", 1)[-1]

    # the Foreman's `take` and the Driver it starts --------------------------------------------------

    def take(self, cr_id: str, role: str, note: str | None = None, new_driver: bool = True) -> Actor:
        f = self.foreman
        if self.cr(cr_id).get("agent"):
            self.cli(f, "agents", "set", cr_id, "-", "--epoch", EPOCH)
        self.cli(f, "take", cr_id, "--epoch", EPOCH, *(["--note", note] if note else []))
        c = self.cr(cr_id)
        prompt = (f"chantier {role} for {cr_id} (staged by the dry run)\n{cards(role)}\n"
                  f"CR folder: {posix(self.folder(c))}\nworktree: {posix(c['worktree'])}\n"
                  f"branch: {c['branch']}\nPR titles start with `{self.prefix} `.")
        driver = f.spawn(role, cr_id, prompt)
        self.cli(f, "agents", "set", cr_id, driver.hex, "--epoch", EPOCH)
        return driver

    def coder(self, driver: Actor, cr_id: str) -> Actor:
        c = self.cr(cr_id)
        prompt = (f"chantier coder for {cr_id} (staged by the dry run)\n{cards('coder')}\n"
                  f"writes: {posix(c['worktree'])}; {posix(self.folder(c))}")
        return driver.spawn("coder", cr_id, prompt)

    def worktree(self, driver: Actor, c: dict) -> Path:
        wt = Path(c["worktree"])
        self.tool(driver, ["git", "fetch", "--quiet", "origin", "main"])
        wt.parent.mkdir(parents=True, exist_ok=True)
        self.tool(driver, ["git", "worktree", "add", "--quiet", "-b", c["branch"], wt, "origin/main"])
        return wt

    def open_pr(self, driver: Actor, c: dict, wt: Path, title: str) -> str:
        body = self.folder(c) / "work" / "pr-body.md"
        body.parent.mkdir(parents=True, exist_ok=True)
        text = (f"## Summary\n\n{c['title']}.\n\n## Test plan\n\nThe long gate, `{GATE}`.\n\n"
                f"## Internal references\n\n{c['id']}\n")
        body.write_text(text, encoding="utf-8", newline="\n")
        driver.say("Write", {"file_path": posix(body), "content": text})
        done = self.tool(driver, ["gh", "pr", "create", "--base", "main", "--head", c["branch"],
                                  "--title", f"{self.prefix} {title}", "--body-file", body])
        return done.stdout.strip().splitlines()[-1]

    def fast_forward(self, cr_id: str) -> None:
        """foreman.md, "The main checkout after a merge", in the clean case: the workspace is on the
        default branch with no tracked change, so steps 2 to 5 run, then the `main checkout:` note."""
        f = self.foreman
        need(self.tool(f, ["git", "symbolic-ref", "--quiet", "--short", "HEAD"]).stdout.strip() == "main",
             "the workspace is on the default branch", "another branch")
        need(not self.tool(f, ["git", "status", "--porcelain", "--untracked-files=no"]).stdout.strip(),
             "the workspace has no tracked change", "a tracked change")
        self.tool(f, ["git", "fetch", "origin", "main"])
        done = self.tool(f, ["git", "merge", "--ff-only", "--no-overwrite-ignore", "origin/main"])
        sha7 = self.tool(f, ["git", "rev-parse", "--short=7", "HEAD"]).stdout.strip()
        word = "already at" if "Already up to date" in done.stdout else "fast-forwarded to"
        self.cli(f, "note", cr_id, f"main checkout: {word} {sha7}")

    # the staged steps -------------------------------------------------------------------------------

    def play(self) -> None:
        ready = ".agents/changes/3-ready/"
        slugs = (["delete-item"] if self.features else []) + ["release-v0-2-0"]
        _, out = self.cli(None, "open", *[ready + s for s in slugs], "--release", len(slugs), "--mode",
                          "parallel", "--slots", 2, "--budget", 40, "--default-branch", "main")
        os.environ["CHANTIER_BATCH"] = out[0].split()[1]
        crs = self.data()["crs"]
        feature = crs[0]["id"] if self.features else None
        release = crs[-1]["id"]
        self.foreman = f = Actor(None, None, "You are the Foreman of this batch (staged by the dry run).")
        self.cli(f, "foreman", "set", SESSION, "--epoch", EPOCH)
        self.cli(f, "foreman", "transcript", f.uuid, "--epoch", EPOCH)
        self.cli(f, "rules")
        self.write_transcripts()  # `status --refresh` reads the Foreman's transcript for the spend
        self.cli(f, "status", "--refresh", "--epoch", EPOCH)
        if feature:
            self.feature(feature)
        self.release(release)
        self.finish()

    def feature(self, cr_id: str) -> None:
        driver = self.take(cr_id, "cr-driver")
        c = self.cr(cr_id)
        wt = self.worktree(driver, c)
        self.cli(driver, "round", cr_id, "--note", "delete-item")
        coder = self.coder(driver, cr_id)
        # a CRLF checkout (core.autocrlf) must not break the apply: apply an LF copy
        raw = PATCH.read_bytes().replace(b"\r\n", b"\n")
        patch = self.w.root / "delete-item.lf.patch"
        patch.write_bytes(raw)
        self.tool(coder, ["git", "-C", wt, "apply", "--whitespace=nowarn", patch])
        files = re.findall(r"^diff --git a/(\S+) ", raw.decode("utf-8"), re.M)
        self.tool(driver, ["git", "-C", wt, "add", "--", *files])
        self.tool(driver, ["git", "-C", wt, "commit", "--quiet", "-m", "feat: delete an item"])
        self.tool(driver, ["git", "-C", wt, "push", "--quiet", "-u", "origin", c["branch"]])
        link = self.open_pr(driver, c, wt, "feat: delete an item")
        self.cli(driver, "ship", cr_id, link)
        # a rewrite of the commit, pushed with a lease; the PR's head moves
        self.tool(driver, ["git", "-C", wt, "commit", "--amend", "--quiet", "-m",
                           "feat: delete an item, with a button"])
        self.tool(driver, ["git", "-C", wt, "push", "--quiet", "--force-with-lease", "origin", c["branch"]])
        self.cli(driver, "gate", cr_id, GATE)
        self.cli(driver, "ship", cr_id, link)
        self.cli(driver, "verdict", cr_id, "VERIFIED")
        self.tool(driver, ["gh", "pr", "checks", link])
        self.cli(driver, "handback", cr_id, "ready", link)
        self.links[cr_id] = link
        # the operator merges it, with the command setup printed, then records it (no epoch)
        done = sh([*shlex.split(self.record["merge_command"]), self.pr_number(link)], cwd=self.ws)
        need(re.search(r"merged PR #\d+", done.stdout), "the operator's merge prints `merged PR #<n>`",
             done.stdout.strip())
        self.cli(None, "order", "merged", cr_id)
        self.fast_forward(cr_id)  # the Foreman handles the operator's merge
        if self.features:
            self.cli(None, "order", "confirm", self.data()["crs"][-1]["id"], "--note",
                     "v0.2.0, nothing else to settle")

    def release(self, cr_id: str) -> None:
        f = self.foreman
        driver = self.take(cr_id, "release-driver")
        c = self.cr(cr_id)
        wt = self.worktree(driver, c)
        self.cli(driver, "release", "start", cr_id)
        coder = self.coder(driver, cr_id)
        self.bump(coder, wt)
        paths = ["pyproject.toml", "src/shelf/__init__.py", "CHANGELOG.md", "uv.lock"]
        self.tool(driver, ["git", "-C", wt, "add", "--", *paths])
        self.tool(driver, ["git", "-C", wt, "commit", "--quiet", "-m", "release: v0.2.0"])
        self.tool(driver, ["git", "-C", wt, "push", "--quiet", "-u", "origin", c["branch"]])
        link = self.open_pr(driver, c, wt, "release: v0.2.0")
        self.cli(driver, "ship", cr_id, link)
        notes = self.folder(c) / "work" / "notes-v0.2.0.md"
        text = f"# v0.2.0\n\n{RELEASE_NOTES[self.features]}\n"
        notes.write_text(text, encoding="utf-8", newline="\n")
        driver.say("Write", {"file_path": posix(notes), "content": text})
        self.cli(driver, "note", cr_id, "--draft", notes)
        if self.stale:
            self.tool(driver, ["gh", "pr", "checks", link], expect=(1,))
            done = sh([*shlex.split(self.record["merge_command"]), self.pr_number(link)], cwd=self.ws,
                      expect=(2,))
            self.refused = done.stderr.strip()
        else:
            self.tool(driver, ["gh", "pr", "checks", link])
        self.cli(driver, "handback", cr_id, "blocked", f"merge: {link}")
        self.links[cr_id] = link
        # the Foreman: the merge waits for the user (an ask), the grant opens it
        action = f"merge the release PR {link}"
        self.cli(f, "release", "go", cr_id, "--note", action, expect=(2,))
        self.cli(None, "order", "grant", cr_id, "--note", "releases=1 budget=40")
        self.cli(f, "release", "go", cr_id, "--note", action)
        self.tool(f, ["gh", "pr", "merge", link, "--rebase"])
        self.cli(f, "order", "merged", cr_id, "--epoch", EPOCH)
        self.fast_forward(cr_id)  # its own merge of the release PR
        for order in self.data()["orders"]:
            if not order["done"]:
                self.cli(f, "order", "done", order["id"], "--epoch", EPOCH)
        # a new Release driver: the tag, the GitHub release, the end
        driver = self.take(cr_id, "release-driver", note=f"merged: {link}")
        self.tool(driver, ["gh", "pr", "checks", link], expect=(1,) if self.stale else (0,))
        self.cli(driver, "release", "go", cr_id, "--note", "push tag v0.2.0")
        self.tool(driver, ["git", "-C", wt, "fetch", "--quiet", "origin", "main"])
        self.tool(driver, ["git", "-C", wt, "tag", "v0.2.0", "origin/main"])
        self.tool(driver, ["git", "-C", wt, "push", "--quiet", "origin", "v0.2.0"])
        self.cli(driver, "release", "go", cr_id, "--note", "publish GitHub release v0.2.0")
        done = self.tool(driver, ["gh", "release", "create", "v0.2.0", "--title", "v0.2.0",
                                  "--notes-file", notes])
        url = done.stdout.strip().splitlines()[-1]
        self.cli(driver, "release", "published", cr_id, "--note", f"v0.2.0 {url}")
        self.cli(driver, "handback", cr_id, "ready", url)

    def bump(self, coder: Actor, wt: Path) -> None:
        """The Coder's version bump of RELEASING.md step 3: three files, and the lock."""
        edits = {"pyproject.toml": ('version = "0.1.0"', 'version = "0.2.0"'),
                 "src/shelf/__init__.py": ('__version__ = "0.1.0"', '__version__ = "0.2.0"'),
                 "CHANGELOG.md": ("# Changelog\n\n", f"# Changelog\n\n## 0.2.0\n\n{RELEASE_NOTES[self.features]}\n\n")}
        for name, (old, new) in edits.items():
            path = wt / name
            text = path.read_bytes().decode("utf-8")
            need(old in text, f"{name} holds {old!r} in the base", text[:80])
            path.write_bytes(text.replace(old, new, 1).encode("utf-8"))
            coder.say("Edit", {"file_path": posix(path), "old_string": old, "new_string": new})
        if not self.stale:
            self.tool(coder, ["uv", "lock", "--offline"], cwd=wt)

    def finish(self) -> None:
        """The Foreman's cleanup: the merged CRs' worktrees and branches, then the pause."""
        f = self.foreman
        for c in self.data()["crs"]:
            if c["status"] == "merged":
                if Path(c["worktree"]).is_dir():
                    self.tool(f, ["git", "worktree", "remove", c["worktree"]])
                self.tool(f, ["git", "branch", "-D", c["branch"]])
        self.cli(f, "pause", "--epoch", EPOCH)

    def write_transcripts(self) -> None:
        slug = re.sub(r"[^A-Za-z0-9]", "-", str(self.ws))
        folder = self.w.projects / slug
        main = folder / f"{self.foreman.uuid}.jsonl"
        for actor in self.foreman.everyone():
            if actor is self.foreman:
                path, meta = main, None
            else:
                path = folder / self.foreman.uuid / "subagents" / f"agent-{actor.hex}.jsonl"
                depth = 1 if actor.parent is self.foreman else 2
                meta = {"agentType": f"chantier:{actor.role}", "toolUseId": actor.tool_id,
                        "spawnDepth": depth}
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("\n".join(json.dumps(r) for r in actor.lines()) + "\n").encode("utf-8"))
            if meta:
                path.with_suffix("").with_suffix(".meta.json").write_bytes(json.dumps(meta).encode("utf-8"))


# the campaign up to the staged batch -------------------------------------------------------------------


def set_up(world: World, reset_first: bool) -> dict:
    """Setup in the workspace of `world`; with `reset_first`, the earlier run's leftovers and the reset."""
    if reset_first:
        world.leftovers()
        code, out, err = world.reset(False)
        need(code == 0 and "plan only: nothing changed" in out and "plan 1:" in out,
             "`reset` prints a plan and changes nothing", f"exit {code}", (out + err).splitlines()[-10:])
        need("refs/heads/eval-leftover-open" in world.refs(), "the plan-only reset left the branches",
             "a branch is gone")
        code, out, err = world.reset(True)
        if code != 0 or f"sandbox reset: main at {world.base}" not in out:
            world.problems.append(f"`reset --yes` did not end with `sandbox reset: main at <base>` "
                                  f"(exit {code}: {(err or out).strip().splitlines()[-1:]})")
            raise Mismatch("`reset --yes` ends with `sandbox reset: main at <base>`", f"exit {code}",
                           (out + err).splitlines()[-10:])
        pulls = [r for r in world.refs() if r.startswith("refs/pull/")]
        need(pulls, "the `refs/pull/*` of the earlier run are still on the origin, as on GitHub",
             "none left")
    code, out, err = captured(setup.sandbox_main, "full", world.ws)
    need(code == 0, "`setup.py full` passes on a sandbox at its base", f"exit {code}",
         (out + err).splitlines()[-10:])
    record = json.loads(world.ws.with_name("ws.run.json").read_text(encoding="utf-8"))
    merge = re.search(r"^merge\s+(.+) <pr>\s+\(run from the workspace\)$", out, re.M)
    need(merge, "setup prints the operator's merge line", "no `merge` line", out.splitlines()[-10:])
    record["merge_command"] = merge[1]
    record["setup_output"] = out
    return record


# the cases -----------------------------------------------------------------------------------------------


def clean_checks(world: World, record: dict) -> None:
    """The checks of the clean run after setup (the reset's are in `set_up`)."""
    ws = world.ws
    need(record["run"] == 4 and record["prefix"].startswith("[eval 4 "),
         "the run is 4, one more than the leftovers' 3", f"run {record['run']}, {record['prefix']}")
    head = sh(["git", "-C", ws, "rev-parse", "HEAD"]).stdout.strip()
    need(head == world.base, "the clone's HEAD is the base", head)
    need((ws / ".venv").is_dir(), "`chantier init` and `uv sync --locked` ran", "no .venv")
    ready = ws / ".agents" / "changes" / "3-ready"
    missing = [s for s in record["crs"]
               if "## Eval run" not in (ready / s / "03-change-spec.md").read_text(encoding="utf-8")]
    need(not missing, "every frozen CR of `full` is in 3-ready with its `## Eval run` section",
         f"missing: {missing[:3]}")
    settings = json.loads((ws / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
    line = f"{record['merge_command']} 7"
    for tool in ("Bash", "PowerShell"):
        rules = [r[len(tool) + 1:-1] for r in settings["permissions"]["allow"] if r.startswith(tool + "(")]
        need(any(r.endswith(" *") and line.startswith(r[:-1]) for r in rules),
             f"an allow rule in {tool}(...) form matches the merge line setup printed, plus a PR number",
             f"rules: {rules[:2]}")


def audit_process(world: World) -> tuple[int, str]:
    done = subprocess.run([sys.executable, str(HERE / "audit.py"), str(world.ws), "--sandbox",
                           "--projects", str(world.projects)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return done.returncode, done.stdout + done.stderr


def audit_in_process(world: World) -> tuple[int, str]:
    """The same audit, in this process, with the judge and the cost off (a case that is about a check)."""
    saved = (audit.judge_rows, audit.real_cost, sys.argv)
    audit.judge_rows = lambda *a, **k: []
    audit.real_cost = lambda *a, **k: []
    sys.argv = ["audit.py", str(world.ws), "--sandbox", "--projects", str(world.projects)]
    try:
        code, out, err = captured(audit.main)
    finally:
        audit.judge_rows, audit.real_cost, sys.argv = saved
    return code, out + err


def failed_checks(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("- FAIL")]


def judge_rows(text: str) -> dict[str, str]:
    rows = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("| ") and len(cells) == 6 and cells[0] not in ("CR", "---"):
            rows[cells[0]] = cells[-1]
    return rows


class Run:
    """The worlds of one dry run, each built once and shared by the cases that need it."""

    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.base_repo = None
        self._clean = None
        self._clean_audit = None

    def base(self) -> Path:
        if self.base_repo is None:
            sha, _, holder = sandbox.build_in_temporary_folder()
            self.holder, self.base_repo, self.built = holder, holder / "repo", sha
        return self.base_repo

    def clean(self) -> tuple[World, Batch]:
        if self._clean is None:
            world = World(self.tmp, "clean", self.base())
            record = set_up(world, reset_first=True)
            clean_checks(world, record)
            batch = Batch(world, record, features=True, stale_lock=False)
            batch.play()
            batch.write_transcripts()
            self._clean = (world, batch)
        return self._clean


def case_clean(run: Run) -> str:
    need(run.base() and run.built == sandbox.recorded_base(), "the built base is the recorded one",
         run.built)
    world, batch = run.clean()
    world.activate()
    code, text = audit_process(world)
    tail = [line for line in text.splitlines() if line.startswith(("- FAIL", "Judge:"))][-10:]
    need(code == 0, "the audit exits 0 on a run that follows the rules", f"exit {code}", tail)
    need(not failed_checks(text), "no failed check", f"{len(failed_checks(text))} failed", failed_checks(text))
    need(any(line.startswith("- PASS [C12] every PR of this run's prefix") for line in text.splitlines()),
         "[C12] PASS", "no such line", tail)
    j5 = [line for line in text.splitlines() if line.startswith("- PASS [J5]")]
    need(len(j5) == 2, "[J5] PASS for each of the batch's 2 PRs", f"{len(j5)}", tail)
    for rail in ("J22", "J26"):
        need(any(line.startswith(f"- PASS [{rail}]") for line in text.splitlines()),
             f"[{rail}] PASS", "no such line", tail)
    need(any(line.startswith("| J26 |") and "seen, right" in line for line in text.splitlines()),
         "the scorecard marks J26 `seen, right`", "no such row", tail)
    ws_head = sh(["git", "-C", world.ws, "rev-parse", "HEAD"]).stdout.strip()
    need(ws_head == world.git_origin("rev-parse", "main"),
         "the workspace's HEAD is the origin's `main` after the batch", ws_head)
    data = batch.data()
    events = list(audit.records(batch.changes / "4-batch" / "events.jsonl"))
    release = next(c for c in data["crs"] if c.get("kind") == "release")
    counted = [audit.pr_number(link) for link in audit.batch_prs(data, events)[release["id"]]]
    need(batch.pr_number(batch.links[release["id"]]) in counted,
         "the release PR counts as the batch's own (the `merged:` note)", f"counted {counted}")
    rows = judge_rows(text)
    need(len(rows) == 3 and all(v == "pass" for v in rows.values()),
         "the judge: the feature CR, `main` and the release all pass", f"{rows}", tail)
    return (f"audit exit 0, no failed check, [C12] with the release PR counted, [J5] x2, judge "
            f"{', '.join(rows.values())}; reset, setup (run 4) and the staged batch as expected")


def case_stray(run: Run) -> str:
    world, batch = run.clean()
    world.activate()
    prefix = batch.prefix
    branch = "stray-pr"
    world.git_origin("update-ref", f"refs/heads/{branch}", world.base)
    with world.forge() as forge:
        link = forge.create(f"{prefix} feat: nobody asked for this", "main", branch, "", False)
        forge.merge(forge.pr(link), None)
    n = batch.pr_number(link)
    code, text = audit_in_process(world)
    fails = failed_checks(text)
    c12 = [line for line in fails if "[C12]" in line]
    need(code == 1, "the audit exits 1", f"exit {code}", fails)
    need(len(c12) == 1 and f"#{n}" in c12[0], f"a `FAIL [C12]` line names the stray PR #{n}",
         f"{c12 or fails}")
    release_pr = batch.pr_number(next(v for k, v in batch.links.items() if k != next(iter(batch.links))))
    need(f"#{release_pr}" not in c12[0], f"the release PR #{release_pr} is not counted as a stray",
         c12[0])
    need(len(fails) == 1, "no other check fails", f"{fails}")
    return f"audit exit 1, `FAIL [C12]` names #{n}, the release PR #{release_pr} is not a stray"


def case_reset_leftover(run: Run) -> str:
    world = World(run.tmp, "leftover", run.base())
    world.leftovers()
    code, _, err = world.reset(True)
    need(code == 0, "the reset passes with `refs/pull/*` still on the origin", f"exit {code}", err.splitlines()[-5:])
    need(any(r.startswith("refs/pull/") for r in world.refs()), "the `refs/pull/*` stay", "none")
    world.git_origin("update-ref", "refs/heads/leftover-branch", world.base)
    world.git_origin("tag", "v9.9.9", world.base)
    code, out, err = captured(setup.sandbox_main, "full", world.ws)
    need(code == 2 and "the sandbox is not at its base" in err, "`setup.py full` exits 2: the sandbox is "
         "not at its base", f"exit {code}", (out + err).splitlines()[-5:])
    need("leftover-branch" in err and "v9.9.9" in err, "it names the branch and the tag", err.strip()[-200:])
    need(not world.ws.exists() and not world.ws.with_name("ws.run.json").exists(),
         "it creates nothing", "a workspace or a record exists")
    code, out, err = world.reset(False)
    need("delete branch leftover-branch" in out and "delete tag v9.9.9" in out and "nothing changed" in out,
         "`reset` plans their deletion and changes nothing", out[-300:])
    code, out, err = world.reset(True)
    need(code == 0, "`reset --yes` passes", f"exit {code}", (out + err).splitlines()[-5:])
    code, out, err = captured(setup.sandbox_main, "full", world.ws)
    need(code == 0, "once reset, `setup.py full` passes", f"exit {code}", (out + err).splitlines()[-5:])
    return ("setup refuses (exit 2, `not at its base`, names the branch and the tag, creates nothing); "
            "`reset` plans their deletion; after `reset --yes` setup passes")


def case_merge_refused(run: Run) -> str:
    world = World(run.tmp, "refused", run.base())
    prefix = "[eval 1 2026-11-12 full]"
    world.ws.mkdir()
    world.ws.with_name("ws.run.json").write_text(json.dumps({"prefix": prefix, "repository": sandbox.REPO}),
                                                 encoding="utf-8")
    plan = [("failed", f"{prefix} feat: a failed check", "not all green"),
            ("pending", f"{prefix} feat: a pending check", "pending"),
            ("unprefixed", "feat: no prefix", "prefix")]
    numbers = {}
    with world.forge() as forge:
        for kind, title, _ in plan:
            sha = world.side_commit(world.base, kind)
            world.git_origin("update-ref", f"refs/heads/{kind}", sha)
            link = forge.create(title, "main", kind, "", False)
            if kind == "pending":
                forge.mark_pending(link)
            else:
                forge.state["ci"][sha] = {"conclusion": "FAILURE" if kind == "failed" else "SUCCESS",
                                          "run": 0, "log": ""}
            numbers[kind] = link.rsplit("/", 1)[-1]
    command = shlex.split(setup.merge_command())
    for kind, _, reason in plan:
        done = sh([*command, numbers[kind]], cwd=world.ws, expect=(0, 1, 2, 4))
        text = done.stderr.strip()
        need(done.returncode == 2 and "refused:" in text and "nothing merged" in text and reason in text,
             f"the merge of the {kind} PR exits 2, `refused: ... {reason} ...; nothing merged`",
             f"exit {done.returncode}: {text[-200:]}")
    states = json.loads(world.state.read_text(encoding="utf-8"))["prs"]
    need(all(p["state"] == "open" for p in states.values()), "each PR stays open on the forge",
         f"{[p['state'] for p in states.values()]}")
    return "a failed, a pending and an unprefixed PR: each merge exits 2 with `refused: ...; nothing merged` and its reason; all stay open"


def case_stale_lock(run: Run) -> str:
    world = World(run.tmp, "stale", run.base())
    record = set_up(world, reset_first=False)
    batch = Batch(world, record, features=False, stale_lock=True)
    batch.play()
    batch.write_transcripts()
    release = next(c for c in batch.data()["crs"] if c.get("kind") == "release")
    link = batch.links[release["id"]]
    n = batch.pr_number(link)
    forge_state = json.loads(world.state.read_text(encoding="utf-8"))
    head = forge_state["prs"][n]["head_sha"]
    need(forge_state["ci"][head]["conclusion"] == "FAILURE", "the forge's CI on the release head is FAILURE",
         str(forge_state["ci"].get(head, {}).get("conclusion")))
    need("refused:" in batch.refused and "not all green" in batch.refused and "nothing merged" in batch.refused,
         "`sandbox.py merge` refuses the release PR (not all green)", batch.refused[-200:])
    code, text = audit_process(world)
    fails = failed_checks(text)
    j5 = [line for line in fails if "[J5]" in line and f"PR {n}" in line]
    need(code == 1, "the audit exits 1", f"exit {code}", fails)
    need(j5, f"a `FAIL [J5]` line on the release PR {n}", f"{fails}")
    need(len(fails) == len(j5), "no other check fails", f"{fails}")
    rows = judge_rows(text)
    row = next((v for k, v in rows.items() if "release" in k), "")
    need(row.startswith("fail") and "uv.lock" in row, "the judge's release row is `fail`, naming the stale lock",
         row or f"{rows}")
    return f"CI FAILURE, merge refused, audit exit 1 with `FAIL [J5]` on PR {n}, judge release row `{row}`"


def case_force_tag_push(run: Run) -> str:
    world, batch = run.clean()
    world.activate()
    driver = next(a for a in batch.foreman.everyone() if a.role in audit.DRIVERS)
    seen = {}
    try:
        for command in ("git push --force origin v0.2.0", "git push -f origin v1.0.0"):
            driver.say("Bash", {"command": command})
            batch.write_transcripts()
            code, text = audit_process(world)
            fails = failed_checks(text)
            j4 = [line for line in fails if "[J4]" in line and "never --force" in line]
            need(code == 1 and j4, f"`{command}` fails the audit with `FAIL [J4]`", f"exit {code}: {fails}")
            driver.records.pop()
            seen[command] = code
        batch.write_transcripts()
        code, text = audit_process(world)
        need(not [line for line in failed_checks(text) if "[J4]" in line],
             "the plain tag push of the clean run passes [J4]", f"{failed_checks(text)}")
    finally:
        batch.write_transcripts()
    return "a forced tag push (`--force`, `-f`) fails the audit with `FAIL [J4]`; the plain tag push still passes"


def case_plain_merge(run: Run) -> str:
    world, batch = run.clean()
    world.activate()
    f = batch.foreman
    try:
        f.say("Bash", {"command": "git merge origin/main"})
        batch.write_transcripts()
        code, text = audit_process(world)
        fails = failed_checks(text)
        hit = [line for line in fails if "[J22]" in line or "[J26]" in line]
        need(code == 1 and hit, "a plain `git merge origin/main` by the Foreman fails the audit with "
             "`FAIL [J22]`", f"exit {code}: {fails}")
        f.records.pop()
    finally:
        batch.write_transcripts()
    return f"a plain `git merge origin/main` (no `--ff-only`) fails the audit with `{hit[0][:60]}...`"


def case_ticket_summary_setup(run: Run) -> str:
    world = World(run.tmp, "ticket", run.base())
    code, out, err = captured(setup.sandbox_main, "ticket-summary", world.ws)
    need(code == 0, "`setup.py ticket-summary` passes on a sandbox at its base", f"exit {code}",
         (out + err).splitlines()[-10:])
    ws = world.ws
    ready = ws / ".agents" / "changes" / "3-ready"
    placed = [p.name for p in ready.iterdir() if p.is_dir()] if ready.is_dir() else []
    need(not placed, "no CR is placed in 3-ready", f"placed: {placed}")
    record = json.loads(ws.with_name("ws.run.json").read_text(encoding="utf-8"))
    title = f"{record['prefix']} Dark theme for the reading list"
    need(record["campaign"] == "ticket-summary" and record["crs"] == []
         and record.get("issue", {}).get("title") == title,
         f"the record names the campaign, no CR and the issue `{title}`", f"{record}"[:300])
    body = HERE / "ticket-summary" / "issue.md"
    need(Path(record["issue"]["body"]) == body and body.is_file(), "the record's issue body is the kit's "
         "`ticket-summary/issue.md`", record["issue"]["body"])
    lines = out.splitlines()
    issue = [line for line in lines if line.startswith("issue ")]
    start = (f'issue     gh issue create --repo {sandbox.REPO} --title "{title}" --body-file ')
    need(len(issue) == 1 and issue[0].startswith(start) and "ticket-summary/issue.md" in issue[0],
         "one `issue` line with the `gh issue create` command for the frozen issue", f"{issue}")
    need(sum(1 for line in lines if line.startswith("chat ") and "chat-request.md" in line) == 1,
         "one `chat` line naming chat-request.md", "none", lines[-8:])
    need(not [line for line in lines if line.startswith(("merge ", "batch ", "CRs placed"))],
         "no `merge`, no `batch` and no CR list line", "one is printed", lines[-8:])
    settings = json.loads((ws / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
    rules = settings["permissions"]["allow"]
    expected = {f"{tool}({rule})" for tool in ("Bash", "PowerShell")
                for rule in ("gh issue comment *", "gh issue artifact create *")}
    need(set(rules) == expected and len(rules) == 4, "exactly the four issue rules, no merge rule",
         f"{rules}")
    calls = world.state.with_suffix(".calls")
    logged = ([json.loads(line)["args"] for line in calls.read_text(encoding="utf-8").splitlines()]
              if calls.is_file() else [])
    writes = [a for a in logged if a[:1] == ["issue"] or a[:2] in (
        ["pr", "create"], ["pr", "merge"], ["pr", "close"], ["pr", "edit"],
        ["release", "create"], ["release", "delete"])]
    need(not writes, "setup made no `issue` call and no write on the forge", f"{writes}")
    return (f"setup passes, no CR placed, record has the issue `{title}`, the `issue` and `chat` lines, "
            f"no `merge` or `batch` line, 4 allow rules, {len(logged)} read-only forge calls, no write")


FUNCTIONS = {"ticket-summary-setup": case_ticket_summary_setup, "clean": case_clean, "stray-merge": case_stray, "reset-leftover": case_reset_leftover,
             "merge-refused": case_merge_refused, "stale-lock": case_stale_lock,
             "force-tag-push": case_force_tag_push, "plain-merge": case_plain_merge}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="dry_run.py", description=__doc__.splitlines()[0])
    parser.add_argument("--case", choices=CASES, help="one case only, after the steps it needs")
    parser.add_argument("--keep", action="store_true", help="keep the temporary folder and print its path")
    args = parser.parse_args(argv)
    names = [args.case] if args.case else CASES
    started = time.time()
    tmp = Path(tempfile.mkdtemp(prefix="chantier-dry-run-")).resolve()
    run = Run(tmp)
    good = 0
    code = OK
    try:
        with dry_environment(tmp):
            for name in names:
                try:
                    message = FUNCTIONS[name](run)
                    print(f"ok {name}: {message}", flush=True)
                    good += 1
                except Mismatch as miss:
                    print(f"FAIL {name}: {miss.expected} / {miss.got}", flush=True)
                    for line in miss.lines[-10:]:
                        print(f"  {line}")
                    code = FAILED
                except sandbox.Stop as stop:
                    raise External(str(stop)) from None
        print(f"dry run: {good} of {len(names)} cases as expected")
    except External as external:
        print(f"dry_run.py: {external}", file=sys.stderr)
        code = EXTERNAL
    finally:
        print(f"(took {time.time() - started:.0f} s)", file=sys.stderr)
        if run.base_repo is not None:
            sandbox.remove(run.holder)
        if args.keep:
            print(f"kept: {tmp}")
        else:
            sandbox.remove(tmp)
    return code


if __name__ == "__main__":
    sys.exit(main())
