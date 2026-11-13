#!/usr/bin/env python3
"""Global scenario: one whole chantier batch, end to end, through the real CLI.

A scripted Foreman reads the batch's state and does what its card leaves it (fills the slots,
asks the Chief of Staff, merges what the user allowed, cleans up, pauses); scripted
Drivers create their worktree, commit, rebase, push and open their PRs against a bare origin and
a fake `gh` (or `glab`), and use the CLI for its record (`round`, `gate`, `ship`, `handback`).
The Chief of Staff steers with `chantier order`. Nothing calls a model: the scripted agents prove
the frame, and the checks are on what the CLI refuses, records and reports.

    uv run --no-project python scenario/run_scenario.py [--forge gitlab] [--keep] [--verbose]

Exit 0 when every check passes; the transcript is written to scenario/results/<forge>-<time>.md (ignored by git).
"""
from __future__ import annotations

import argparse
import html
import json
import os
import queue
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent / "skills" / "chantier"
FAKE = {"github": ("gh", Path(__file__).with_name("fake_gh.py")),
        "gitlab": ("glab", Path(__file__).with_name("fake_glab.py"))}
PR_LINK = {"github": "https://github.com/acme/demo/pull/",
           "gitlab": "https://gitlab.example.com/acme/demo/-/merge_requests/"}
FAKE_USAGE = Path(__file__).with_name("fake_session_usage.py")
LOG: list[str] = []
CHECKS = {"pass": 0, "fail": 0}
GATE = "uv run --no-project python -m compileall -q ."  # what the project's AGENTS.md names
FROM_AGENTS_MD = ("--default-branch", "main")
TRAILER = "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
BODY = ("## Summary\n\n{title}.\n\n## Deliverables\n\nNone.\n\n## Blast radius\n\nGrade: 1\n\n"
        "## Autonomous decisions\n\nNone.\n\n## Known gaps\n\nNone.\n\n"
        "<details>\n<summary>Details</summary>\n\n"
        "## Changes\n\nNone.\n\n## Impacts\n\nNone.\n\n## Test plan\n\nNone.\n\n"
        "## Internal references\n\n{cr}\n\n</details>\n")
LIVE = {"working"}
ENDED = {"merged", "cancelled"}
BACK_NOTES = ("rebase:", "merged:")
OPENED: dict[str, str] = {}  # the PR the scripted Driver opened for a CR


def note(line: str) -> None:
    LOG.append(line)
    if ARGS.verbose:
        print(line)


def check(label: str, ok: bool, detail: str = "") -> None:
    CHECKS["pass" if ok else "fail"] += 1
    note(f"- [{'x' if ok else ' '}] {label}{'' if ok else f' — {detail}'}")
    if not ok and not ARGS.verbose:
        print(f"FAIL {label}: {detail}")


class World:
    def __init__(self, root: Path):
        self.root = root
        self.work = root / "proj"
        self.state = self.work / ".agents" / "changes"
        self.gh_state = root / "gh-state.json"
        exe, _ = FAKE[ARGS.forge]
        self.fake = root / "bin" / (f"{exe}.cmd" if sys.platform == "win32" else exe)
        self.env = {**os.environ, "PYTHONPATH": str(SKILL / "scripts" / "cli" / "src"),
                    "CHANTIER_SKILL_DIR": str(SKILL), "FAKE_GH_STATE": str(self.gh_state),
                    "CHANTIER_CLAUDE_PROJECTS": str(root / "claude-projects"),
                    "CLAUDE_CODE_ENTRYPOINT": "claude-desktop", "CHANTIER_HOST": "claude",
                    "CLAUDE_CODE_SESSION_ID": "uuid-chief"}  # the Chief of Staff's session
        for var in ("CHANTIER_ROOT", "CHANTIER_BATCH", "CHANTIER_PLUGIN_ROOT",
                    "COPILOT_AGENT_SESSION_ID"):
            self.env.pop(var, None)
        self.last_stderr = ""
        self.last_out: list[str] = []
        self.name = ""  # the running batch's id, `batch-<n>`: the CLI numbers it

    def sh(self, *args, cwd=None):
        return subprocess.run(args, cwd=cwd or self.work, check=True, capture_output=True,
                              text=True).stdout.strip()

    def build(self) -> None:
        origin = self.root / "origin.git"
        self.sh("git", "init", "--quiet", "--bare", "-b", "main", str(origin), cwd=self.root)
        self.sh("git", "init", "--quiet", "-b", "main", str(self.work), cwd=self.root)
        self.sh("git", "config", "user.name", "scenario")
        self.sh("git", "config", "user.email", "scenario@example.com")
        (self.work / "app.py").write_text("def login():\n    return True\n")
        (self.work / "AGENTS.md").write_text(
            f"# Project instructions\n\nDefault branch: `main`. Remote: `origin`.\n"
            f"Long gate, before a PR: `{GATE}`. Merge by rebase.\n"
            "Commits and PRs: see [CONTRIBUTING.md](CONTRIBUTING.md).\n")
        (self.work / "CONTRIBUTING.md").write_text(
            "# Contributing\n\nPR titles: `feat: <subject>`. Fill every section of the PR template.\n")
        (self.work / ".gitignore").write_text("__pycache__/\n")
        self.sh("git", "add", ".")
        self.sh("git", "commit", "--quiet", "-m", "init", "-m", TRAILER)
        self.sh("git", "remote", "add", "origin", str(origin))
        self.sh("git", "push", "--quiet", "-u", "origin", "main")
        _, script = FAKE[ARGS.forge]
        gh = self.fake
        gh.parent.mkdir()
        if sys.platform == "win32":
            gh.write_text(f'@"{sys.executable}" "{script}" %*\r\n')
        else:
            gh.write_text(f"#!/bin/sh\nexec {sys.executable} {script} \"$@\"\n")
            gh.chmod(0o755)
        self.gh(next_pr=40)

    def gh(self, **kw) -> None:
        d = json.loads(self.gh_state.read_text()) if self.gh_state.exists() else {}
        d.update(kw)
        self.gh_state.write_text(json.dumps(d))

    def forge(self, *args) -> tuple[int, str, str]:
        """The Driver's or the Foreman's own call to the forge's CLI (the fake one)."""
        p = subprocess.run([str(self.fake), *args], cwd=self.work, env=self.env,
                           capture_output=True, text=True, encoding="utf-8")
        note(f"    $ {FAKE[ARGS.forge][0]} {' '.join(args[:4])}…  → exit {p.returncode}")
        return p.returncode, p.stdout.strip(), p.stderr.strip()

    def chantier(self, *args, env=None, expect=0, cwd=None):
        p = subprocess.run([sys.executable, "-m", "chantier", *map(str, args)], cwd=cwd or self.work,
                           env={**self.env, **(env or {})}, capture_output=True, text=True,
                           encoding="utf-8")
        out = p.stdout.strip().splitlines()
        self.last_stderr = p.stderr.strip()
        self.last_out = out
        note(f"    $ chantier {' '.join(map(str, args))}  → exit {p.returncode}")
        for ln in out + ([f"stderr: {self.last_stderr}"] if self.last_stderr else []):
            note(f"      {ln}")
        if expect is not None and p.returncode != expect:
            check(f"chantier {' '.join(map(str, args))} exits {expect}", False,
                  f"exit {p.returncode}: {self.last_stderr[:200]}")
        return p.returncode, out

    def ready(self, cr, link, expect=0):
        """The Driver's end: the long gate and the Verifier's verdict at the head, then `handback ready`."""
        self.chantier("gate", cr, GATE, expect=None)
        self.chantier("verdict", cr, "VERIFIED", expect=None)
        return self.chantier("handback", cr, "ready", link, expect=expect)

    def batch(self):
        return json.loads((self.folder() / "batch.json").read_text())

    def folder(self, name=None):
        return self.state / "4-batch"

    def start(self, *args, **kw):
        """`open` takes no name: the batch is `batch-<n>`, and it is the one running batch."""
        code, out = self.chantier("open", *args, **kw)
        if code == 0:
            self.name = out[0].split()[1]
        return code, out

    def reset(self) -> None:
        """Sweep what an earlier case left open: `open` refuses a second batch."""
        if (self.state / "4-batch").is_dir():
            shutil.rmtree(self.state / "4-batch")

    def cr(self, cr_id):
        return next(c for c in self.batch()["crs"] if c["id"] == cr_id)

    def at(self, path):
        """A recorded CR path in the planning folder; the older `.agents/changes/` form reads too."""
        return self.state / str(path).removeprefix(".agents/changes/")


def open_pr(w: World, cr_id: str, title: str, base: str = "main") -> str:
    """The Driver opens the PR with the forge's CLI, from the body it wrote."""
    c = w.cr(cr_id)
    body = w.at(c["path"]) / "work" / "pr-body.md"
    if ARGS.forge == "github":
        _, out, _ = w.forge("pr", "create", "--base", base, "--head", c["branch"], "--title",
                            title, "--body-file", str(body))
        return out.splitlines()[-1]
    _, out, _ = w.forge("api", "projects/local/merge_requests", "--method", "POST",
                        "--raw-field", f"source_branch={c['branch']}", "--raw-field",
                        f"target_branch={base}", "--raw-field", f"title={title}")
    return json.loads(out)["web_url"]


def merge_pr(w: World, pr: str) -> tuple[int, str]:
    """A merge with the forge's CLI, by the project's method (rebase)."""
    if ARGS.forge == "github":
        code, _, err = w.forge("pr", "merge", pr, "--rebase")
    else:
        code, _, err = w.forge("api", f"projects/local/merge_requests/{pr.rsplit('/', 1)[-1]}/merge",
                               "--method", "PUT")
    return code, err


def land(w: World, branch: str, extra: tuple[str, str] | None = None) -> str:
    """The user's merge reaches the bare origin: the CR's commits land on `main` by rebase (the
    project's method), with git from a scratch clone outside the project, never through the fake
    forge. With `extra` (a path and its content), a commit adding that file lands instead."""
    scratch = w.root / "landing"
    if not scratch.is_dir():
        w.sh("git", "clone", "--quiet", str(w.root / "origin.git"), str(scratch), cwd=w.root)
        w.sh("git", "config", "user.name", "scenario", cwd=scratch)
        w.sh("git", "config", "user.email", "scenario@example.com", cwd=scratch)
    w.sh("git", "fetch", "--quiet", "origin", cwd=scratch)
    if extra:
        w.sh("git", "checkout", "--quiet", "--detach", "origin/main", cwd=scratch)
        (scratch / extra[0]).write_text(extra[1])
        w.sh("git", "add", "-f", "--", extra[0], cwd=scratch)
        w.sh("git", "commit", "--quiet", "-m", f"add {extra[0]}", "-m", TRAILER, cwd=scratch)
    else:
        w.sh("git", "checkout", "--quiet", "--detach", f"origin/{branch}", cwd=scratch)
        w.sh("git", "rebase", "--quiet", "origin/main", cwd=scratch)
    w.sh("git", "push", "--quiet", "origin", "HEAD:main", cwd=scratch)
    return w.sh("git", "rev-parse", "HEAD", cwd=scratch)


class Foreman:
    """Does what foreman.md leaves it, from `batch.json` (a real one reads `chantier status`):
    the pending orders, the asks, the merges the user allowed, the free slots, the QA drivers,
    the cleanup, the pause."""

    def __init__(self, w: World, epoch: int):
        self.w, self.epoch = w, epoch
        self.started: list[str] = []
        self.asked: list[str] = []
        self.messages: list[str] = []
        self.cancelled: list[str] = []
        self.qa: list[str] = []  # the folders of the QA drivers it started
        self.told: set = set()
        self.facts: list[str] = []
        self.paused = False
        self.git_main: list[tuple[str, ...]] = []  # every git command it ran in the main checkout

    def git(self, *args: str) -> subprocess.CompletedProcess:
        """The Foreman's git in the main checkout; the commands are kept for a check."""
        self.git_main.append(args)
        return subprocess.run(["git", *args], cwd=self.w.work, capture_output=True, text=True,
                              encoding="utf-8")

    def fast_forward(self, cr: str) -> str:
        """foreman.md, "The main checkout after a merge": steps 2 to 5 (step 1 reads the rules,
        which say nothing against it here), then the `main checkout:` note on the CR."""
        remote, default = "origin", "main"
        why = None
        branch = self.git("symbolic-ref", "--quiet", "--short", "HEAD").stdout.strip()
        if branch != default:
            why = f"on {branch}, not {default}" if branch else "detached HEAD"
        if why is None:
            dirty = [ln[3:] for ln in self.git("status", "--porcelain",
                                               "--untracked-files=no").stdout.splitlines()]
            if dirty:
                why = f"tracked changes: {', '.join(dirty[:3])}"
        if why is None:
            p = self.git("fetch", remote, default)
            if p.returncode:
                why = f"fetch failed: {p.stderr.strip()}"
        line = None
        if why is None:
            p = self.git("merge", "--ff-only", "--no-overwrite-ignore", f"{remote}/{default}")
            sha7 = self.git("rev-parse", "--short=7", "HEAD").stdout.strip()
            text = p.stdout + p.stderr
            if p.returncode == 0:
                line = (f"already at {sha7}" if "Already up to date" in text
                        else f"fast-forwarded to {sha7}")
            elif "Not possible to fast-forward" in text or "diverging" in text:
                why = f"diverged from {remote}/{default}"
            elif "untracked working tree files would be overwritten" in text:
                paths = [ln.strip() for ln in text.splitlines() if ln.startswith(("\t", " "))
                         and ln.strip() and not ln.strip().startswith(("Please", "Aborting"))]
                why = f"untracked file in the way: {paths[0] if paths else '?'}"
            else:
                why = text.strip().splitlines()[0] if text.strip() else "git refused"
        if line is None:
            line = f"not fast-forwarded: {why}"
        self.w.chantier("note", cr, f"main checkout: {line}")
        return line

    def worktree_check(self, session: str, cwd: Path | None = None) -> bool:
        """foreman.md's worktree check, before the epoch is claimed: in a linked worktree (`--git-dir`
        differs from `--git-common-dir`) take no CR and ask; else claim the epoch."""
        cwd = cwd or self.w.work
        git_dir, common = (
            (cwd / ln).resolve() for ln in self.w.sh("git", "rev-parse", "--git-dir",
                                                     "--git-common-dir", cwd=cwd).splitlines())
        if git_dir != common:
            self.ask(f"blocked {self.w.name} this session is in the worktree {cwd}; "
                     "start the Foreman on the main checkout")
            return False
        self.w.chantier("foreman", "set", session, "--epoch", self.epoch, cwd=cwd)
        return True

    def ask(self, text: str) -> None:
        self.asked.append(text)
        self.w.chantier("asks", "--", *text.split(" "))

    def ask_once(self, key: tuple, text: str) -> None:
        if key not in self.told:
            self.told.add(key)
            self.ask(text)

    def take(self, target: str, note_: str | None = None) -> int:
        """`take`, then the Driver (a scripted one) with the facts in its prompt. The id of the
        Driver that ended is cleared first, as the card says: `take` refuses a recorded one."""
        if target != "stack" and self.w.cr(target).get("agent"):
            self.w.chantier("agents", "set", target, "-", "--epoch", self.epoch)
        code, facts = self.w.chantier("take", target, "--epoch", self.epoch,
                                      *(["--note", note_] if note_ else []), expect=None)
        if code:
            return code
        self.facts = facts
        self.started.append(f"{target} {note_}" if note_ else target)
        self.w.chantier("agents", "set", target, f"agent-{len(self.started)}",
                        "--epoch", self.epoch)
        if target != "stack":
            start_driver(self.w, target)
        return 0

    def remove_merged(self) -> None:
        """Before `pause`: the merged CRs' worktrees and branches, the Foreman's own hands."""
        for c in self.w.batch()["crs"]:
            if c["status"] != "merged":
                continue
            if Path(c["worktree"]).is_dir():
                self.git("worktree", "remove", c["worktree"])
            # the PR is merged (status above), the check the card asks for; -d would refuse
            # after a rebase or squash merge
            self.git("branch", "-D", c["branch"])

    def merge(self, c: dict) -> None:
        """What the user allowed the Foreman to merge: a release's fix under the grant, the
        release PR after `release go`. Done with the forge's CLI, recorded with `order merged`."""
        cr = c["id"]
        if c.get("kind") in ("release", "fix"):
            action = f"merge the {c['kind']} PR {c['pr']}"
            code, out = self.w.chantier("release", "go", cr, "--note", action, expect=None)
            if code == 5:
                self.ask_once((cr, "budget"), f"budget {out[0]}")
                return
            if code:
                self.ask_once((cr, "approval", c["pr"]), f"blocked {cr} approval: {action}")
                return
        code, err = merge_pr(self.w, c["pr"])
        if code:
            self.ask_once((cr, "refused", err), f"refused {cr} {err}")
            return
        self.w.chantier("order", "merged", cr, "--epoch", self.epoch)
        self.fast_forward(cr)
        self.ask(f"merged {cr} {c['pr']}")

    def do_order(self, d: dict, o: dict) -> bool:
        """The Foreman's part; False when the order stays pending until a Driver takes it."""
        c = next((x for x in d["crs"] if x["id"] == o["cr"]), None)
        rel = next((x for x in d["crs"] if x["id"] == o.get("fix_for")), None)
        if o["kind"] == "qa":  # the order stays pending until its QA driver ends
            if o["cr"] not in self.qa:
                self.qa.append(o["cr"])
            return False
        if o["kind"] == "drop" and c and c["status"] in LIVE:
            self.cancelled.append(c["id"])
            self.w.chantier("cancel", c["id"], "--epoch", self.epoch)
        elif o["kind"] == "note" and c and c["status"] in LIVE:
            self.messages.append(f"{c['id']} {o['note']}")
        elif o["kind"] in ("note", "rounds", "approve", "grant") and c \
                and c["status"] in {"ready", "blocked"} \
                and not (c.get("blocked_reason") or "").startswith(("fix:", "merge:")):
            return False  # a Driver takes it with that note; the order is done then
        elif o["kind"] == "budget" and any(
                x["status"] == "blocked" and (x.get("blocked_reason") or "").startswith("budget")
                for x in d["crs"]):
            return False
        elif o["kind"] == "add" and rel and rel["status"] in LIVE:
            self.messages.append(f"{rel['id']} fix {d['crs'][-1]['id']}")
        self.w.chantier("order", "done", o["id"], "--epoch", self.epoch)
        return True

    def candidates(self, d: dict) -> list[tuple[dict, str | None, dict | None]]:
        """Who a free slot goes to, in order: a queued CR (with the note that says why it is
        back), then a ready or blocked CR a pending order sends back."""
        out = []
        pending = [o for o in d["orders"] if not o["done"]]
        for c in sorted(d["crs"], key=lambda c: c["order"]):
            reason = c.get("blocked_reason") or ""
            if c["status"] == "queued":
                last = next((n for n in reversed(c.get("notes") or [])
                             if not n.startswith("main checkout:")), "")
                out.append((c, last if last.startswith(BACK_NOTES) else None, None))
            elif c["status"] == "blocked" and reason.startswith("fix:"):
                fixes = [x for x in d["crs"] if x.get("fix_for") == c["id"]]
                if fixes and all(x["status"] == "merged" for x in fixes):
                    out.append((c, f"fix merged: {reason}", None))
            elif c["status"] in {"ready", "blocked"}:
                o = next((o for o in pending if o["cr"] == c["id"]
                          and o["kind"] in ("note", "rounds", "approve", "grant")), None)
                if o is None and reason.startswith("budget"):
                    o = next((o for o in pending if o["kind"] == "budget"), None)
                if o and not reason.startswith(("fix:", "merge:")):
                    out.append((c, f"{o['kind']}: {o['note']}", o))
        return out

    def turn(self) -> None:
        d = self.w.batch()
        merged = [o for o in d["orders"] if not o["done"] and o["kind"] == "merged"]
        if merged:  # the user's merges: one attempt after the last, before any `order done`
            self.fast_forward(merged[-1]["cr"])
        for o in d["orders"]:
            if not o["done"]:
                self.do_order(d, o)
        d = self.w.batch()
        for c in sorted(d["crs"], key=lambda c: c["order"]):
            reason = c.get("blocked_reason") or ""
            if c["status"] == "blocked":
                if c.get("kind") == "release" and reason.startswith("merge:"):
                    self.merge(c)  # what the user allowed
                    continue
                self.ask_once((c["id"], "blocked", reason), f"blocked {c['id']} {reason}")
            elif c["status"] == "ready":
                grant = d.get("release") or {}
                if (c.get("kind") == "release" and c.get("pr")
                        and grant.get("autonomous", 0) > grant.get("published", 0)):
                    self.merge(c)  # the release PR's merge, only under the grant
                    continue
                if (c["id"], "ready", c.get("pr")) in self.told:
                    continue
                self.told.add((c["id"], "ready", c.get("pr")))
                if c.get("kind") == "fix" and (d.get("release") or {}).get("fixes"):
                    self.merge(c)
                else:
                    self.ask(f"ready {c['id']} {c['pr']}")
        d = self.w.batch()
        # a slot is a running Driver: a CR working, or a QA order not done
        live = sum(c["status"] in LIVE for c in d["crs"]) \
            + sum(o["kind"] == "qa" and not o["done"] for o in d["orders"])
        for c, note_, o in self.candidates(d):
            if live >= d["slots"]:
                break
            code = self.take(c["id"], note_)
            if code == 0:
                live += 1
                if o:
                    self.w.chantier("order", "done", o["id"], "--epoch", self.epoch)
            elif code == 5:
                self.ask(f"budget {self.w.last_stderr}")
                break
            elif c.get("kind") != "release":
                self.ask(f"refused {c['id']} {self.w.last_stderr}")
        d = self.w.batch()
        if d["status"] != "paused" and d["crs"] and all(c["status"] in ENDED for c in d["crs"]) \
                and all(o["done"] for o in d["orders"]):
            self.remove_merged()
            self.w.chantier("pause", "--epoch", self.epoch)
            self.paused = True

    def driver_died(self, cr: str) -> None:
        """A task ended with no hand-back: the facts say where it stood."""
        _, facts = self.w.chantier("handoff", cr)
        if self.w.cr(cr)["status"] in LIVE:
            self.take(cr, f"resume: {facts[0]}")


def start_driver(w: World, cr_id: str) -> None:
    """A Driver's first step: the worktree its prompt names, on the fresh base, or the one an
    earlier Driver left."""
    c = w.cr(cr_id)
    if Path(c["worktree"]).is_dir():
        return
    w.sh("git", "fetch", "--quiet", "origin", "main")
    Path(c["worktree"]).parent.mkdir(exist_ok=True)
    if w.sh("git", "branch", "--list", c["branch"]):
        w.sh("git", "worktree", "add", "--quiet", c["worktree"], c["branch"])
    else:
        w.sh("git", "worktree", "add", "--quiet", "-b", c["branch"], c["worktree"], "origin/main")


def commit(w: World, cr_id: str, filename: str, content: str, subject: str | None = None) -> None:
    """The Driver's own commit: explicit paths, a message by the project's guideline."""
    wt = Path(w.cr(cr_id)["worktree"])
    (wt / filename).write_text(content)
    msg = w.root / "commit-msg.txt"
    msg.write_text(f"{subject or f'{cr_id}: {filename}'}\n\n{TRAILER}\n")
    w.sh("git", "add", "--", filename, cwd=wt)
    w.sh("git", "commit", "--quiet", "-F", str(msg), cwd=wt)


def push(w: World, cr_id: str) -> None:
    """The Driver rebases on the fresh base and pushes with a lease."""
    c = w.cr(cr_id)
    wt = Path(c["worktree"])
    w.sh("git", "fetch", "--quiet", "origin", cwd=wt)
    w.sh("git", "rebase", "--quiet", "origin/main", cwd=wt)
    w.sh("git", "push", "--quiet", "--force-with-lease", "-u", "origin", c["branch"], cwd=wt)


def ship(w: World, cr_id: str, title: str) -> None:
    """The Driver writes the PR body, pushes, opens or updates the PR itself, then records it."""
    c = w.cr(cr_id)
    body = w.at(c["path"]) / "work" / "pr-body.md"
    body.parent.mkdir(exist_ok=True)
    push(w, cr_id)
    first = cr_id not in OPENED
    body.write_text(BODY.format(title=c["title"], cr=cr_id))
    link = OPENED.setdefault(cr_id, open_pr(w, cr_id, title) if first else c["pr"])
    w.chantier("ship", cr_id, link)


def driver_round(w: World, cr_id: str, filename: str, content: str) -> None:
    """A round counted, a Coder's change, then the Driver's commit, long gate and ship."""
    w.chantier("round", cr_id, "--note", f"edit {filename}")
    commit(w, cr_id, filename, content)
    w.chantier("gate", cr_id, GATE)
    ship(w, cr_id, f"feat: {filename.removesuffix('.py')}")


def prepare_cr(w: World, title: str, priority: str = "P1") -> tuple[Path, Path]:
    _, out = w.chantier("file", title)
    inbox = w.work / out[0].removeprefix("filed ").split(";", 1)[0]
    (inbox / "01-intent.md").write_text(f"# {title}\n\nThe original request is in intake.\n")
    (inbox / "02-answers.md").write_text("# Decisions\n\nNo open questions.\n")
    (inbox / "03-change-spec.md").write_text(f"# {title}\n\nImplement {title}.\n")
    _, out = w.chantier("triage", inbox, "--priority", priority)
    backlog = w.work / out[0].removeprefix("triaged ").rsplit(" (", 1)[0]
    return inbox, backlog


def scenario(w: World) -> None:
    note("## 1. Setup and preflight")
    code, out = w.chantier("preflight", env={"CLAUDE_CODE_ENTRYPOINT": "claude-vscode",
                                             "CHANTIER_HOST": ""}, expect=2)
    check("preflight refuses Claude in VS Code (P1) and says to start nothing",
          code == 2 and out[0].startswith("P1 FAIL") and out[-1].endswith("start nothing"))
    home = w.root / "home"  # a home of its own: the developer's settings are not read
    homes = {"HOME": str(home), "USERPROFILE": str(home)}
    code, out = w.chantier("preflight", env=homes)
    check("preflight passes on Claude Desktop with no setup", code == 0
          and out[-1] == "preflight passed")
    p10 = next((ln for ln in out if ln.startswith("P10")), "")
    check("preflight warns (P10) on the allow rules missing from the settings, names one, and "
          "still passes", p10.startswith("P10 warn")
          and "git push --force-with-lease -u origin chantier/*" in p10, p10)
    sys.path.insert(0, str(SKILL / "scripts" / "cli" / "src"))
    from chantier.commands import RECOMMENDED_ALLOW
    (home / ".claude").mkdir(parents=True)
    user = ["git push --force-with-lease -u origin chantier/*",
            "git push --force-with-lease=chantier/* origin *chantier/*"]
    (home / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": [f"{t}({r})" for r in user
                                              for t in ("Bash", "PowerShell")]}}), encoding="utf-8")
    code, out = w.chantier("preflight", env=homes)
    p10 = next((ln for ln in out if ln.startswith("P10")), "")
    check("preflight (P10) judges equivalence: the user's own force-push forms are not named, the "
          "`-C` form still is", code == 0 and p10.startswith("P10 warn")
          and "add Bash(git push --force-with-lease" not in p10
          and "add Bash(git -C * push --force-with-lease -u origin chantier/*)" in p10, p10)
    (home / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": list(RECOMMENDED_ALLOW)}}), encoding="utf-8")
    code, out = w.chantier("preflight", env=homes)
    check("preflight says P10 ok once the rules are in the home settings", code == 0
          and any(ln.startswith("P10 ok") for ln in out), str(out))
    check("nothing was written in the working tree", w.sh("git", "status", "--porcelain") == "")
    _, out = w.chantier("rules")
    check("`rules` lists the project's instructions and what they link, with line counts",
          out[0].startswith((w.work / "AGENTS.md").as_posix()) and "lines)" in out[0]
          and out[1].startswith((w.work / "CONTRIBUTING.md").as_posix()), str(out))

    note("\n## 2. The Chief of Staff opens the batch and starts the Foreman")
    items = [prepare_cr(w, title) for title in
             ("Fix login timeout", "Add CSV export", "Dark mode", "Audit log")]
    code, _ = w.chantier("open", "Fix login", *FROM_AGENTS_MD, expect=1)
    check("a raw title cannot bypass the prepared CR", code == 1 and items[0][1].is_dir())
    _, spare = prepare_cr(w, "Spare item", "P2")
    _, out = w.chantier("triage", spare, "--priority", "P3")
    moved = spare.parent.parent / "P3" / spare.name
    check("`triage` moves a backlog item to the new priority",
          out[0].endswith("(P3)") and moved.is_dir() and not spare.exists(), str(out))
    code, _ = w.chantier("triage", moved, "--priority", "P3", expect=2)
    check("`triage` to the same priority is refused: already P3",
          "already P3" in w.last_stderr, w.last_stderr)
    code, _ = w.chantier("triage", w.state / "STATUS.md", "--priority", "P1", expect=1)
    check("`triage` of another path says what it expects", "2-backlog/P<n>/<item>" in w.last_stderr,
          w.last_stderr)
    w.chantier("abandon", moved)
    w.chantier("file", "Spare item twice")
    code, _ = w.chantier("file", "Spare item twice", expect=2)
    check("`file` of an existing slug exits 2 and names `--slug`", "--slug" in w.last_stderr,
          w.last_stderr)
    w.chantier("abandon", w.work / ".agents/changes/1-inbox/spare-item-twice")
    _, out = w.start(*(str(backlog) for _, backlog in items),
                     "--slots", 2, "--budget", 50, *FROM_AGENTS_MD)
    check("`open` says what comes next, then where each folder moved",
          out[1].startswith("next:") and "2-backlog/P1/" in out[2] and "-> 4-batch/1-pending/" in out[2],
          str(out))
    check("the batch is numbered, has no name, and `--batch` takes the number",
          w.name == "batch-01" and (w.folder() / "batch.json").is_file()
          and w.chantier("status", "--batch", "1")[0] == 0
          and w.chantier("status", "--batch", "batch-01")[0] == 0, w.name)
    _, first = w.chantier("status")
    board = (w.state / "STATUS.md").read_text(encoding="utf-8")
    batch_report = (w.folder() / "STATUS.md").read_text(encoding="utf-8")
    check("a spend not priced yet is unknown, never $0.00: `status`, the batch's STATUS.md and the board",
          w.batch()["spent_usd"] is None and "spent unknown" in first[0] and "spent $0.00" not in first[0]
          and "spent unknown" in batch_report and "spent $0.00" not in batch_report
          and "unknown" in board and "$0.00" not in board, f"{first[0]}\n{batch_report}\n{board}")
    w.chantier("foreman", "set", "local_foreman1", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    w.chantier("foreman", "transcript", "uuid-foreman", "--epoch", 1)
    d = w.batch()
    check("four CRs, each with a branch and a worktree named, none created: the CLI changes "
          "nothing in git",
          len(d["crs"]) == 4 and all(c["branch"].startswith(f"chantier/{w.name}/cr-10")
                                     and not Path(c["worktree"]).exists() for c in d["crs"]))
    code, _ = w.chantier("gate", "CR-103", GATE, expect=2)
    check("a command that needs the worktree says who creates it",
          code == 2 and "its Driver creates it" in w.last_stderr, w.last_stderr)
    check("opening moves the entire prepared folders into 1-pending",
          all(not backlog.exists() for _, backlog in items)
          and all("4-batch/1-pending/" in c["path"]
                  and (w.state / c["path"] / "intake/request.md").is_file()
                  and (w.state / c["path"] / "03-change-spec.md").is_file() for c in d["crs"]))
    fm.turn()
    check("the Foreman gives two CRs to Drivers (two slots)", fm.started == ["CR-101", "CR-102"])
    check("each Driver created its worktree and branch on the fresh default branch",
          all(Path(w.cr(x)["worktree"]).is_dir() and w.sh("git", "rev-parse", "HEAD", cwd=Path(
              w.cr(x)["worktree"])) == w.sh("git", "rev-parse", "origin/main")
              for x in ("CR-101", "CR-102")) and not Path(w.cr("CR-103")["worktree"]).exists())
    check("`take` prints the facts for the prompt: the CLI, the cards, the base, the rounds",
          any(ln.startswith("cli: uv run --script") for ln in fm.facts)
          and any(ln.startswith("cards: ") and "references/" in ln for ln in fm.facts)
          and any("base origin/main" in ln for ln in fm.facts)
          and any(ln == "rounds: 0 of 3" for ln in fm.facts), str(fm.facts))
    code, _ = w.chantier("take", "CR-103", expect=2)
    check("a third Driver is refused: no free slot", code == 2 and "no free slot" in w.last_stderr)
    check("a taken CR is working", w.cr("CR-101")["status"] == "working")
    _, added = prepare_cr(w, "Waits in the backlog", "P3")
    board = (w.state / "STATUS.md").read_text(encoding="utf-8")
    check("the board shows the open batch and what `triage` just moved",
          f"[{w.name}](4-batch/STATUS.md)" in board and "Fix login timeout" in board
          and "| P3 |" in board and "Waits in the backlog" in board, board)

    note("\n## 3. CR-101: one round, the Driver's own push and PR, hand-back")
    _, out = w.chantier("round", "CR-101", "--note", "round 1")
    check("`round` counts the round and prints the facts", w.cr("CR-101")["round"] == 1
          and out[0] == "round 1 of 3 for CR-101" and any(ln == "rounds: 1 of 3" for ln in out),
          str(out))
    code, _ = w.chantier("handback", "CR-101", "ready", "done", expect=2)
    check("no hand-back ready before a PR is recorded", code == 2 and "PR recorded" in w.last_stderr)
    wt = Path(w.cr("CR-101")["worktree"])
    commit(w, "CR-101", "login.py", "TIMEOUT_S = 30\n")
    code, out = w.chantier("gate", "CR-101", GATE)
    check("the long gate runs the project's command in the worktree and records the head",
          code == 0 and out[0].startswith(f"pass {GATE} at ") and out[1].startswith("log "), str(out))
    ship(w, "CR-101", "feat: login")
    check("`ship` records the Driver's PR with its head, and nothing off",
          w.cr("CR-101")["pr"].startswith(PR_LINK[ARGS.forge]) and w.cr("CR-101")["head"]
          and len(w.last_out) == 1, str(w.last_out))
    (wt / "login.py").write_text("TIMEOUT_S = 31\n")
    _, out = w.chantier("ship", "CR-101", w.cr("CR-101")["pr"])
    check("`ship` reports an uncommitted change the PR does not hold",
          any(ln.startswith("off: uncommitted changes") and "login.py" in ln for ln in out), str(out))
    (wt / "login.py").write_text("TIMEOUT_S = 30\n")
    code, _ = w.chantier("ship", "CR-101", "not a link", expect=1)
    check("the PR link is the forge's", code == 1)
    pr101 = w.cr("CR-101")["pr"]
    _, out = w.ready("CR-101", pr101)
    check("a hand-back writes the state and prints the line to send",
          out[0] == f"[driver CR-101→foreman] hand-back ready {pr101}"
          and w.cr("CR-101")["status"] == "ready", str(out))
    fm.turn()
    check("hand-back frees a slot: CR-103 taken", fm.started[-1] == "CR-103")
    check("the Chief of Staff is told CR-101 is ready with its PR",
          fm.asked[-1] == f"ready CR-101 {pr101}")
    fm.turn()
    check("a second turn with nothing new does nothing", fm.started[-1] == "CR-103"
          and fm.asked[-1] == f"ready CR-101 {pr101}")
    code, _ = w.chantier("handback", "CR-101", "ready", pr101, expect=2)
    check("a CR without a Driver cannot be handed back", code == 2)
    code, _ = w.chantier("round", "CR-101", expect=2)
    check("a CR without a Driver runs no round", code == 2)

    note("\n## 4. CR-102: two rounds")
    driver_round(w, "CR-102", "export.py", "def export():\n    return 'csv'\n")
    w.chantier("note", "CR-102", "CI red: the product; export header missing")
    driver_round(w, "CR-102", "export.py", "def export():\n    return 'id,name\\n'\n")
    w.ready("CR-102", w.cr("CR-102")["pr"])
    fm.turn()
    check("a second ready CR goes to the Chief of Staff",
          fm.asked[-1].startswith(f"ready CR-102 {PR_LINK[ARGS.forge]}"))

    note("\n## 5. Steering: the user drops CR-103, adds an item, changes CR-101")
    _, out = w.chantier("order", "drop", "CR-103")
    check("`chantier order` prints the message with an order id, and what it did",
          out[0] == "[chief-of-staff→foreman] order O-1: drop CR-103"
          and "live" in out[1], str(out))
    # Windows finds a process by its command line only, so the sleeper names its worktree
    wt103 = w.cr("CR-103")["worktree"]
    sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)", wt103],
                               cwd=wt103)
    fm.turn()
    deadline = time.monotonic() + 5
    while sleeper.poll() is None and time.monotonic() < deadline:
        time.sleep(0.05)
    check("dropping a live CR cancels it and stops its processes",
          fm.cancelled == ["CR-103"] and sleeper.poll() is not None
          and w.cr("CR-103")["status"] == "cancelled")
    check("a dropped CR goes to the trash with its work, under the date",
          re.search(r"6-trash/\d{6}-\d{4}-103-", w.cr("CR-103")["path"])
          and (w.state / w.cr("CR-103")["path"] / "02-answers.md").is_file()
          and "⚪ dropped" in (w.state / w.cr("CR-103")["path"] / "STATUS.md").read_text("utf-8"))
    check("the freed slot goes to CR-104", "CR-104" in fm.started)
    _, out = w.chantier("order", "done", "O-1", "--epoch", 1)
    check("an order read twice is done once", out == ["O-1 already done"])
    _, added = prepare_cr(w, "Rate limit the login endpoint")
    _, out = w.chantier("order", "add", "--note", str(added))
    check("an added item becomes CR-105 at once", out[1] == "added CR-105, queued", str(out))
    fm.turn()
    check("CR-105 has a worktree and takes the second free slot",
          fm.started[-1] == "CR-105" and w.cr("CR-105")["status"] == "working"
          and Path(w.cr("CR-105")["worktree"]).is_dir())
    _, out = w.chantier("order", "note", "CR-101", "--note", "change: also log the timeout")
    check("a note on a ready CR is recorded; the CR stays ready for the Foreman to decide",
          w.cr("CR-101")["status"] == "ready" and w.cr("CR-101")["notes"][-1]
          == "change: also log the timeout", str(out))
    _, out = w.chantier("status")
    check("status shows the pending order", any(ln.startswith("orders pending: O-") and "note CR-101"
                                                in ln for ln in out), str(out))
    w.chantier("agents", "set", "CR-101", "-")  # its Driver ended with the hand-back
    code, _ = w.chantier("take", "CR-101", "--note", "change", expect=2)
    check("it waits for a slot", code == 2 and "no free slot" in w.last_stderr)
    fm.turn()
    check("the Foreman keeps the order pending while no slot is free",
          not all(o["done"] for o in w.batch()["orders"]))

    note("\n## 6. A Foreman restart: the old one is refused")
    w.chantier("foreman", "set", "local_foreman2", "--epoch", 2)
    w.chantier("foreman", "transcript", "uuid-foreman", "--epoch", 2)
    code, _ = w.chantier("status", "--refresh", "--epoch", 1, expect=3)
    check("a stale Foreman (epoch 1) is refused with exit 3", code == 3)
    code, _ = w.chantier("foreman", "set", "local_second", "--epoch", 2, expect=3)
    check("a second session cannot claim an epoch already claimed (exit 3)",
          code == 3 and w.batch()["foreman"] == "local_foreman2")
    fm.epoch = 2

    note("\n## 7. CR-104 is lost, then hands back; CR-105 and CR-101 run")
    fm.driver_died("CR-104")
    check("a Driver that ends without a hand-back is replaced from the facts",
          fm.started[-1].startswith("CR-104 resume: CR-104 \"Audit log\" (change) working"),
          fm.started[-1])
    driver_round(w, "CR-104", "audit.py", "AUDIT = []\n")
    w.ready("CR-104", w.cr("CR-104")["pr"])
    driver_round(w, "CR-105", "ratelimit.py", "LIMIT = 10\n")
    w.ready("CR-105", w.cr("CR-105")["pr"])
    fm.turn()
    check("the change on CR-101 reaches a new Driver, with the note, and the order is done",
          fm.started[-1] == "CR-101 note: change: also log the timeout"
          and all(o["done"] for o in w.batch()["orders"]), str(fm.started))
    w.ready("CR-101", pr101)
    fm.turn()
    _, out = w.chantier("status")
    check("status shows every CR", all(f"CR-10{i}" in "\n".join(out) for i in range(1, 6)))
    _, out = w.chantier("log", "CR-104")
    check("`log` tells a CR's story", any(" take " in ln for ln in out)
          and any(" round " in ln for ln in out) and any(" ship " in ln for ln in out)
          and any(" handback " in ln for ln in out), str(out))
    status_files(w)
    trashed = w.cr("CR-103")["path"]
    w.chantier("cancel", "CR-103", "--epoch", 2)
    check("a second cancel leaves the trashed CR where it is", w.cr("CR-103")["path"] == trashed)

    note("\n## 8. The user merges; the Foreman cleans up and pauses the batch")
    code, _ = w.chantier("pause", "--epoch", 2, expect=2)
    check("pause is refused while PRs are not merged", code == 2 and w.batch()["status"] == "running")
    fake_transcripts(w, w.batch())
    orders = len(w.batch()["orders"])
    local = w.work / "local-notes.txt"  # the user's own untracked file
    local.write_text("mine\n")
    planning = sorted(p.relative_to(w.work).as_posix() for p in (w.work / ".agents").rglob("*")
                      if p.is_file() and "4-batch" not in p.parts)
    head0 = w.sh("git", "rev-parse", "HEAD")
    land(w, w.cr("CR-101")["branch"])  # the user's merge reaches origin; nothing is moved yet
    check("the user's merge landed on origin by rebase, through no forge call, and the main "
          "checkout has not moved by itself",
          w.sh("git", "rev-parse", "origin/main") == head0
          and w.sh("git", "rev-parse", "HEAD") == head0
          and w.sh("git", "ls-remote", "origin", "refs/heads/main").split()[0] != head0)
    _, out = w.chantier("order", "merged", "CR-101")
    check("`order merged` moves the CR to 3-done at once and records the time",
          w.cr("CR-101")["status"] == "merged" and "4-batch/3-done/" in w.cr("CR-101")["path"]
          and (w.state / w.cr("CR-101")["path"] / "03-change-spec.md").is_file()
          and re.fullmatch(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ", w.cr("CR-101")["merged_at"]),
          str(out))
    fm.turn()
    remote = w.sh("git", "ls-remote", "origin", "refs/heads/main").split()[0]
    check("fast-forward done: the main checkout is at origin/main, with the file CR-101 added, "
          "the user's untracked file and the untracked planning folder intact, and the note says so",
          w.sh("git", "rev-parse", "HEAD") == remote == w.sh("git", "rev-parse", "origin/main")
          and (w.work / "login.py").read_text() == "TIMEOUT_S = 30\n"
          and local.read_text() == "mine\n"
          and planning == sorted(p.relative_to(w.work).as_posix()
                                 for p in (w.work / ".agents").rglob("*")
                                 if p.is_file() and "4-batch" not in p.parts)
          and w.cr("CR-101")["notes"][-1] == f"main checkout: fast-forwarded to {remote[:7]}",
          str(w.cr("CR-101")["notes"][-3:]))

    # CR-102: a tracked file of the main checkout is changed, the fast-forward is refused
    land(w, w.cr("CR-102")["branch"])
    head1 = w.sh("git", "rev-parse", "HEAD")
    (w.work / "app.py").write_text("def login():\n    return False  # the user's edit\n")
    w.chantier("order", "merged", "CR-102")
    fm.turn()
    check("refused on a tracked change: HEAD has not moved, the change is kept, the note says why",
          w.sh("git", "rev-parse", "HEAD") == head1
          and "the user's edit" in (w.work / "app.py").read_text()
          and not (w.work / "export.py").exists()
          and w.cr("CR-102")["notes"][-1] == "main checkout: not fast-forwarded: tracked changes: app.py",
          str(w.cr("CR-102")["notes"][-2:]))
    w.sh("git", "checkout", "--quiet", "--", "app.py")  # the user undoes the change

    # CR-104: it tries again at the next merge and catches up
    land(w, w.cr("CR-104")["branch"])
    w.chantier("order", "merged", "CR-104")
    fm.turn()
    remote = w.sh("git", "ls-remote", "origin", "refs/heads/main").split()[0]
    check("the next merge tries again: the checkout catches up with origin/main, CR-102's file included",
          w.sh("git", "rev-parse", "HEAD") == remote and (w.work / "export.py").is_file()
          and (w.work / "audit.py").is_file()
          and w.cr("CR-104")["notes"][-1] == f"main checkout: fast-forwarded to {remote[:7]}",
          str(w.cr("CR-104")["notes"][-2:]))

    # CR-105: an untracked file is in the way, the fast-forward is refused and the file kept
    (w.work / "ratelimit.py").write_text("MINE = True\n")
    land(w, w.cr("CR-105")["branch"])
    head2 = w.sh("git", "rev-parse", "HEAD")
    w.chantier("order", "merged", "CR-105")
    fm.turn()
    check("refused with an untracked file in the way: HEAD has not moved, the file is intact, "
          "the note names it",
          w.sh("git", "rev-parse", "HEAD") == head2
          and (w.work / "ratelimit.py").read_text() == "MINE = True\n"
          and w.cr("CR-105")["notes"][-1]
          == "main checkout: not fast-forwarded: untracked file in the way: ratelimit.py",
          str(w.cr("CR-105")["notes"][-2:]))
    (w.work / "ratelimit.py").unlink()
    fm.fast_forward("CR-105")
    check("with the file gone, the next attempt fast-forwards",
          w.sh("git", "rev-parse", "HEAD") == w.sh("git", "ls-remote", "origin",
                                                  "refs/heads/main").split()[0]
          and (w.work / "ratelimit.py").is_file(), str(w.cr("CR-105")["notes"][-2:]))
    # the same, with a file ignored by the project's own exclude list
    (w.work / ".git" / "info" / "exclude").write_text("kept.cache\n")
    (w.work / "kept.cache").write_text("mine too\n")
    land(w, "", extra=("kept.cache", "theirs\n"))
    head3 = w.sh("git", "rev-parse", "HEAD")
    fm.fast_forward("CR-105")
    check("refused with an ignored file in the way (`--no-overwrite-ignore`): HEAD has not moved, "
          "the file is intact, the note names it",
          w.sh("git", "rev-parse", "HEAD") == head3
          and (w.work / "kept.cache").read_text() == "mine too\n"
          and w.cr("CR-105")["notes"][-1]
          == "main checkout: not fast-forwarded: untracked file in the way: kept.cache",
          str(w.cr("CR-105")["notes"][-2:]))
    (w.work / "kept.cache").unlink()
    (w.work / ".git" / "info" / "exclude").write_text("")
    fm.fast_forward("CR-105")
    check("the Foreman's git in the main checkout is only symbolic-ref, status, fetch, "
          "`merge --ff-only --no-overwrite-ignore`, rev-parse, worktree remove and branch -D",
          all(g[0] in {"symbolic-ref", "status", "fetch", "rev-parse", "worktree", "branch"}
              or g[:3] == ("merge", "--ff-only", "--no-overwrite-ignore") for g in fm.git_main)
          and any(g[0] == "merge" for g in fm.git_main), str(sorted({g[0] for g in fm.git_main})))
    local.unlink()
    check("the last merge makes the Foreman pause the batch", fm.paused)
    d = w.batch()
    check("the Foreman removed the merged worktrees and branches; the cancelled one stays",
          d["status"] == "paused" and all(
              Path(c["worktree"]).exists() == (c["status"] == "cancelled") for c in d["crs"])
          and not any(w.sh("git", "branch", "--list", c["branch"]) for c in d["crs"]
                      if c["status"] == "merged"))
    check("merged CR folders wait intact in 3-done until the close",
          all(re.search(r"4-batch/3-done/\d{3}-", c["path"])
              and (w.state / c["path"] / "03-change-spec.md").is_file()
              and (w.state / c["path"] / "STATUS.md").is_file()
              and (w.state / c["path"] / "STATUS.json").is_file()
              for c in d["crs"] if c["status"] == "merged"))
    report = (w.folder() / "STATUS.md").read_text(encoding="utf-8")
    check("the batch's STATUS.md, once paused, lists every CR",
          "paused" in report and all(c["id"].removeprefix("CR-") in report for c in d["crs"]))
    board_index(w, d)
    prs = {c["id"]: c["pr"] for c in d["crs"] if c["pr"]}
    check("four PRs were opened on the fake forge by the Drivers", len(set(prs.values())) == 4)

    note("\n## 9. Cost")
    code, out = w.chantier("cost", "--by", "cr", "--batch", w.name)
    check("Claude cost prices the Foreman and each Driver",
          code == 0 and out[:2] == [f"{w.name}: $1.608 over 94 model calls",
                                    "foreman: $0.391 (30 calls)"]
          and sorted(l.split(";")[0] for l in out[2:-3])
          == [f"CR-10{i}: $0.304 (16 calls" for i in (1, 2, 4, 5)], str(out))
    check("the Chief of Staff's lines (steering, grill and specifications, whole session with its "
          "context size and compactions) come apart from the batch's spend",
          out[-3] == "Chief of Staff, steering the batch (outside the budget): unknown (1 calls "
                     "without a time, not placed)"
          and out[-2] == "Chief of Staff, grill and specifications with the user (outside the budget): "
                         "$0.00 since the batch opened (0 calls, 0 spec-writers)"
          and out[-1] == "Chief of Staff, whole session: $9.02, context 22,010 tokens; not counted: "
                         "0 compactions since the batch opened, which leave no record (about $0.12 each)"
          and abs(w.batch()["spent_usd"] - 1.608) < 0.001 and w.batch()["chief_transcript"]
          == "uuid-chief", str(out))
    w.chantier("status", "--refresh", "--batch", w.name)
    _, priced = w.chantier("status", "--batch", w.name)
    batch_report = (w.folder() / "STATUS.md").read_text(encoding="utf-8")
    board = (w.state / "STATUS.md").read_text(encoding="utf-8")
    check("once the spend is priced, `status`, the batch's STATUS.md and the board show a dollar figure",
          re.search(r"spent \$\d+\.\d\d", priced[0]) and re.search(r"spent \$\d+\.\d\d", batch_report)
          and re.search(r"\$\d+\.\d\d of \$50", board), f"{priced[0]}\n{batch_report}\n{board}")
    code, out = w.chantier("cost", "--batch", w.name)
    spend = [ln for ln in out if re.match(r"(Foreman|Driver|Worker|Agent)\b", ln)]
    each = [re.search(r"\((\d+) calls, (\d+)%\)$", ln) for ln in spend]
    ratio = next((ln for ln in out if ln.startswith("Orchestration")), "")
    check("each line of the batch's spend carries its share, the shares add up to 100 as printed, "
          "the ratio line is the steering share plus the Drivers', and the Chief of Staff's lines "
          "carry no share",
          spend and all(each) and sum(int(m[2]) for m in each) == 100
          and ratio == "Orchestration (steering + Drivers): " + str(sum(
              int(m[2]) for ln, m in zip(spend, each) if ln.startswith(("Foreman", "Driver"))))
          + "% of the batch's spend"
          and not any("%" in ln for ln in out if ln.startswith("Chief of Staff")), str(out))
    code, out = w.chantier("cost", "--summary", "--batch", w.name)
    check("the summary gives the total, the budget and the split by level: the Foreman, the "
          "Drivers (the agents that started others) and the workers",
          code == 0 and out[0] == "Total: $1.61 of a $50 budget"
          and out[1] == "Foreman $0.39 (24%), Drivers $0.91 (57%), workers $0.31 (19%)"
          and out[2].startswith("Most: CR-10") and out[-4].startswith("Chief of Staff, steering the batch (out")
          and out[-1].startswith("Not counted: compaction calls")
          and "Driver cr-driver with its workers: $1.22 (64 calls)" in out, str(out))
    amounts = [int(a.replace(".", "")) for a in re.findall(r"\$(\d+\.\d\d) \(", out[1])]
    shares = [int(s) for s in re.findall(r"\((\d+)%\)", out[1])]
    check("the three amounts and shares add up to the total and to 100 as printed",
          len(amounts) == 3 and sum(amounts) == int(out[0].split("$")[1].split(" ")[0]
                                                    .replace(".", "")) and sum(shares) == 100,
          str(out))
    check("the summary gives the Foreman's wakes and its context, average and peak",
          out[3] == "Foreman: 10 wakes, context 22,010 tokens on average, 22,010 at its peak",
          str(out))
    report = (w.folder() / "STATUS.md").read_text(encoding="utf-8")
    check("the batch's STATUS.md gives each CR's cost and the summary",
          "| $0.30 |" in report and "## Cost" in report and "Total: $1.61" in report, report)
    archived = (w.state / w.cr("CR-101")["path"] / "STATUS.md").read_text(encoding="utf-8")
    check("a paused batch's CR page keeps its cost and its link to the batch, and does not call "
          "the cost final: only `close` does",
          "$0.30 so far" in archived and "(../../STATUS.md)" in archived
          and "- [x] Merged" in archived, archived)
    cost_audit(w)
    foreman_chief_lines(w)

    note("\n## 10. Copilot cost")
    copilot_cost(w, d)
    copilot_uv(w)

    note("\n## 11. Event log")
    events = (w.folder() / "events.jsonl").read_text().splitlines()
    kinds = {json.loads(e)["kind"] for e in events}
    check("events.jsonl holds the whole story",
          {"open", "take", "round", "gate", "ship", "note", "handback",
           "order", "order-done", "cancel", "pause"} <= kinds, str(sorted(kinds)))
    calls = (w.root / "gh-state.json.calls").read_text()
    created, merged = (("create", '"merge"'), ('"POST"', '/merge"'))[ARGS.forge == "gitlab"]
    check("only the agents called the forge: the Drivers created the PRs, nobody merged",
          created in calls and merged not in calls and "edit" not in calls and '"PUT"' not in calls,
          calls[-300:])
    close_batch(w)
    retro_cases(w)
    copilot_missing_transcript(w)
    lifecycle_regressions(w)
    stack_batch(w)
    forge_stack_cli(w)
    batch_modes(w)
    release(w)
    granted_fixes(w)
    release_last(w)
    release_on_stack(w)
    qa_on_head(w)
    old_words(w)
    changes_tree(w)
    old_tree(w)
    dependencies(w)
    release_merge_on_approval(w)
    lost_messages(w)
    failed_opening(w)
    playbook_config(w)
    cancel_during_gate(w)
    stop_own_gate(w)
    rails(w)
    handback_proofs(w)
    gate_proof(w)
    restore_cr(w)
    driver_liveness(w)
    foreman_in_a_worktree(w)
    direct_batch(w)
    seat_handover(w)
    remote_board(w)


class BoardProc:
    """A `chantier board` run in the background: its printed lines are read as they come."""

    def __init__(self, w: World, *args, cwd=None):
        self.p = subprocess.Popen([sys.executable, "-m", "chantier", *map(str, args)],
                                  cwd=cwd or w.work, env=w.env, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, encoding="utf-8")
        self.lines: "queue.Queue[str]" = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        for line in self.p.stdout:
            self.lines.put(line.rstrip("\r\n"))

    def line(self, timeout: float = 20) -> str | None:
        try:
            return self.lines.get(timeout=timeout)
        except queue.Empty:
            return None

    def stop(self) -> None:
        if self.p.poll() is None:
            self.p.terminate()
            try:
                self.p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.p.kill()
        for stream in (self.p.stdout, self.p.stderr):
            if stream:
                stream.close()


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def fetch(port: int, path: str, method: str = "GET", host: str = "127.0.0.1") -> tuple[int, dict, str]:
    """One request to a board, with no proxy: the status, the headers and the body."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(f"http://{host}:{port}{path}", method=method,
                                 data=b"x" if method == "POST" else None)
    try:
        with opener.open(req, timeout=10) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", errors="replace")


def folder_state(root: Path) -> dict:
    """Every file of a folder with its size and modification time: what a read-only run must keep."""
    return {p.relative_to(root).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in sorted(root.rglob("*")) if p.is_file()}


def without_time(value):
    """A board's view with the minutes a working CR has been silent left out: they tick."""
    if isinstance(value, dict):
        return {k: without_time(v) for k, v in value.items() if k != "silent_minutes"}
    if isinstance(value, list):
        return [without_time(v) for v in value]
    return value


def remote_board(w: World) -> None:
    note("\n## 16c. The remote board: a read-only web view of the planning folder")
    w.reset()
    (w.state / "seat.json").unlink(missing_ok=True)
    titles = ("Board working", "Board blocked", "Board queued <b>bold</b> title", "Board last")
    items = [prepare_cr(w, t)[1] for t in titles]
    prepare_cr(w, "Board backlog item", "P2")
    _, ready = prepare_cr(w, "Board ready item")
    w.chantier("triage", ready, "--ready")
    w.chantier("file", "Board inbox item")
    w.start(*items, "--direct", "--slots", 2, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("seat", "take", "s-1", "--env", "remote", "--title", "[remote] proj [Chief of Staff]",
               "--link", "link-s1")
    w.chantier("foreman", "set", "uuid-chief", "--epoch", 1)
    w.chantier("foreman", "transcript", "uuid-chief", "--epoch", 1)
    one, two, three, four = (c["id"] for c in w.batch()["crs"])
    for cr in (one, two):
        w.chantier("take", cr, "--epoch", 1)
        w.chantier("agents", "set", cr, f"agent-{cr}", "--epoch", 1)
        start_driver(w, cr)
    driver_round(w, one, "board1.py", "N = 1\n")
    w.chantier("handback", two, "blocked", "question: which colour?")
    slug = "".join(ch if ch.isalnum() else "-" for ch in str(w.work.resolve()))
    chief = w.root / "claude-projects" / slug / "uuid-chief.jsonl"  # the Chief of Staff's transcript
    chief.parent.mkdir(parents=True, exist_ok=True)
    chief.write_text(json.dumps({"type": "assistant", "timestamp": datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"), "message": {"id": "c1", "model": "claude-sonnet-5-5", "usage": {
            "input_tokens": 10, "output_tokens": 100, "cache_read_input_tokens": 0}}}) + "\n")
    w.chantier("status", "--refresh", "--epoch", 1)
    own = json.loads((w.folder() / "STATUS.json").read_text(encoding="utf-8"))
    index = json.loads((w.state / "STATUS.json").read_text(encoding="utf-8"))
    before = folder_state(w.state)
    porcelain = w.sh("git", "status", "--porcelain", "--", ".agents/changes")
    port = free_port()
    procs: list[BoardProc] = []

    def board(*args, cwd=None) -> BoardProc:
        procs.append(BoardProc(w, *args, cwd=cwd))
        return procs[-1]

    try:
        # 1. the start line, no second line on a loopback address
        first = board("board", "--host", "127.0.0.1", "--port", port, "--seat", "s-1")
        line = first.line()
        check("`board` on a loopback address prints its start line and nothing else",
              line == f"board on http://127.0.0.1:{port}/ over {w.state.resolve().as_posix()}"
              and first.line(1.5) is None, str(line))
        # 2. the page
        code, headers, page = fetch(port, "/")
        labels = [c["label"] for c in own["crs"]]
        check("`GET /` is HTML in UTF-8 with each CR's number and label as STATUS.json says it",
              code == 200 and headers["Content-Type"] == "text/html; charset=utf-8"
              and all(c["cr"] in page and html.escape(c["label"]) in page for c in own["crs"])
              and len(labels) == 4, f"{code} {headers.get('Content-Type')}")
        slugs = [r["item"] for r in index["backlog"]]
        check("it holds the inbox, backlog and 3-ready items and escapes a title's markup",
              all(r["item"] in page for r in index["backlog"]) and slugs
              and {"3-ready", "inbox", "P2"} <= {r["priority"] for r in index["backlog"]}
              and "<b>bold</b>" not in page and "&lt;b&gt;bold&lt;/b&gt;" in page,
              str(slugs))
        check("every response is not cached, not sniffed, and its policy allows no script",
              headers["Cache-Control"] == "no-store" and headers["X-Content-Type-Options"] == "nosniff"
              and "script" not in headers["Content-Security-Policy"].replace("default-src 'none'", "")
              and "default-src 'none'" in headers["Content-Security-Policy"], str(headers))
        # 3. the JSON
        code, headers, body = fetch(port, "/api/status")
        view = json.loads(body)
        check("`GET /api/status` gives the index's view, plus the folder, the seat and `board`",
              code == 200 and headers["Content-Type"] == "application/json; charset=utf-8"
              and all(without_time(view[k]) == without_time(index[k])
                      for k in ("batches", "backlog", "merged", "trashed"))
              and view["planning_folder"] == w.state.resolve().as_posix()
              and view["seat"] == "s-1" and view["board"] is True, body[:300])
        # 4. the files
        spec = (w.at(w.cr(one)["path"]) / "03-change-spec.md")
        rel = spec.relative_to(w.state).as_posix()
        code, _, text = fetch(port, "/file?p=" + urllib.parse.quote(rel))
        check("`/file` gives a CR's specification as text", code == 200 and "Board working" in text, str(code))
        outside = [urllib.parse.quote(p) for p in
                   ("../AGENTS.md", "../../AGENTS.md", str(w.work / "AGENTS.md"), "nothing/here.md")]
        check("`/file` answers 404 for a path outside the planning folder, an absolute one, a missing one",
              all(fetch(port, "/file?p=" + p)[0] == 404 for p in outside)
              and fetch(port, "/elsewhere")[0] == 404, str(outside))
        check("`POST` answers 405", fetch(port, "/", "POST")[0] == 405
              and fetch(port, "/", "HEAD")[0] == 200)
        # 5. nothing written, so far
        check("nothing was written in the planning folder, its files, sizes and times, nor its git status",
              folder_state(w.state) == before
              and w.sh("git", "status", "--porcelain", "--", ".agents/changes") == porcelain,
              str(set(folder_state(w.state).items()) ^ set(before.items())))
        # 6. a second board, a port held
        p = subprocess.run([sys.executable, "-m", "chantier", "board", "--host", "127.0.0.1", "--port",
                            str(port), "--seat", "s-1"], cwd=w.work, env=w.env, capture_output=True,
                           text=True, encoding="utf-8", timeout=30)
        check("a second board with the same address and seat says it is running and exits 0",
              p.returncode == 0
              and p.stdout.strip() == f"board already running at http://127.0.0.1:{port}/", p.stdout + p.stderr)
        with socket.socket() as held:
            held.bind(("127.0.0.1", 0))
            held.listen()
            busy = held.getsockname()[1]
            p = subprocess.run([sys.executable, "-m", "chantier", "board", "--port", str(busy)],
                               cwd=w.work, env=w.env, capture_output=True, text=True,
                               encoding="utf-8", timeout=30)
        check("a port held by another program exits 4 with one `board not started` line",
              p.returncode == 4 and len(p.stderr.strip().splitlines()) == 1
              and p.stderr.startswith("error: board not started: ") and not p.stdout.strip(), p.stderr)
        # 7. the seat moves: the board stops, a new one starts
        w.chantier("seat", "take", "s-2", "--over", "s-1")
        fetch(port, "/")
        try:
            stopped = first.p.wait(timeout=15)
        except subprocess.TimeoutExpired:
            stopped = None
        check("when the seat moves the board stops by itself, exit 0", stopped == 0, str(stopped))
        second = board("board", "--host", "127.0.0.1", "--port", port, "--seat", "s-2")
        check("a board for the new seat starts on the same port",
              second.line() == f"board on http://127.0.0.1:{port}/ over {w.state.resolve().as_posix()}"
              and json.loads(fetch(port, "/api/status")[2])["seat"] == "s-2")
        after = folder_state(w.state)
        after.pop("seat.json"), before.pop("seat.json")
        check("serving to the end wrote nothing in the planning folder", after == before,
              str(set(after.items()) ^ set(before.items())))
        # 8. a wider address says so
        wide = board("board", "--host", "0.0.0.0", "--port", free_port(), "--seat", "s-2")
        head, warning = wide.line(), wide.line()
        check("an address beyond this machine prints the second line",
              (head or "").startswith("board on http://0.0.0.0:")
              and (warning or "").startswith("board: listens beyond this machine (0.0.0.0")
              and "no password" in (warning or ""), f"{head} / {warning}")
        wide.stop()
        # 9. chantier.yaml
        yaml = w.work / "chantier.yaml"
        other = free_port()
        yaml.write_text(f"board:\n  host: 127.0.0.1\n  port: {other}\n", encoding="utf-8")
        configured = board("board", "--seat", "s-2")
        line = configured.line()
        check("`board.port` of chantier.yaml sets the port of a board with no option",
              line is not None and line.startswith(f"board on http://127.0.0.1:{other}/"), str(line))
        configured.stop()
        for bad, wrong in (("port: abc", "port"), ("color: red", "color")):
            yaml.write_text(f"board:\n  host: 127.0.0.1\n  {bad}\n", encoding="utf-8")
            code, out = w.chantier("playbook", expect=None)
            problem = f"chantier.yaml:3: board: " in "\n".join(out) and wrong in "\n".join(out)
            code_board, _ = w.chantier("board", "--port", free_port(), expect=None)
            check(f"an invalid `board` ({bad}) is reported by `playbook` with its line, and the board "
                  "refuses to start with it",
                  code == 2 and problem and code_board == 2 and "chantier.yaml:3: board: " in w.last_stderr,
                  f"{out} / {w.last_stderr}")
        yaml.unlink()
    finally:
        for proc in procs:
            proc.stop()
        (w.work / "chantier.yaml").unlink(missing_ok=True)
        w.env.pop("CHANTIER_BATCH", None)
        w.chantier("seat", "leave", "s-2", expect=None)
        w.reset()


def seat_handover(w: World) -> None:
    """Two Chief of Staff sessions on one repository: the seat, the refused take-over, the
    take-over on purpose, and the new session steering the same direct batch."""
    note("\n## 16b. The seat and the hand-over between two Chief of Staff sessions")
    b_env = {"CLAUDE_CODE_SESSION_ID": "uuid-chief-b"}
    _, item = prepare_cr(w, "Seat work")
    w.reset()
    w.start(item, "--direct", "--slots", 1, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("seat", "take", "sess-a", "--env", "remote", "--title", "[remote] proj [Chief of Staff]",
               "--link", "link-a")
    seat = json.loads((w.state / "seat.json").read_text(encoding="utf-8"))
    check("`seat take` writes one file with the session, transcript, env, title and link, no date",
          set(seat) == {"session", "transcript", "env", "title", "link"}
          and seat["transcript"] == "uuid-chief", str(seat))
    w.chantier("seat", "take", "sess-b", env=b_env, expect=2)
    check("a second session is refused the seat, and told to take it over only on the user's word",
          "sess-a" in w.last_stderr and "--over" in w.last_stderr, w.last_stderr)
    w.chantier("seat", "take", "sess-b", "--over", "sess-x", env=b_env, expect=2)
    check("`--over` must name the session that holds the seat", "sess-a" in w.last_stderr,
          w.last_stderr)
    w.chantier("seat", "take", "sess-b", "--over", "sess-a", "--env", "remote", env=b_env)
    d = w.batch()
    check("`seat take --over` hands the seat and the batch's Chief of Staff transcript over, "
          "keeping the earlier one",
          d["chief_transcript"] == "uuid-chief-b"
          and d["chief_transcripts"] == ["uuid-chief", "uuid-chief-b"], str(d))
    _, out = w.chantier("seat", "get")
    check("`seat get` names the new holder", out[0].startswith("seat sess-b "), str(out))
    w.chantier("seat", "leave", "sess-a", expect=2)
    w.chantier("foreman", "set", "uuid-chief-b", "--epoch", 1, env=b_env)
    w.chantier("foreman", "transcript", "uuid-chief-b", "--epoch", 1, env=b_env)
    check("the new session claims the epoch and the steering stays direct",
          w.batch()["steering"] == "direct", str(w.batch()["steering"]))
    w.chantier("status", "--refresh", "--epoch", 0, expect=3)
    slug = "".join(ch if ch.isalnum() else "-" for ch in str(w.work.resolve()))
    projects = w.root / "claude-projects" / slug
    projects.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    call = json.dumps({"type": "assistant", "timestamp": now, "message": {
        "id": "seat", "model": "claude-sonnet-5-5", "usage": {
            "input_tokens": 10, "output_tokens": 100, "cache_read_input_tokens": 0}}}) + "\n"
    for name in ("uuid-chief", "uuid-chief-b"):  # each Chief of Staff session has its own file
        if not (projects / f"{name}.jsonl").is_file():
            (projects / f"{name}.jsonl").write_text(call, encoding="utf-8")
    code, _ = w.chantier("cost")
    check("`cost` prices two Chief of Staff sessions, blocked by neither's file", code == 0,
          w.last_stderr)
    w.chantier("cancel", w.batch()["crs"][0]["id"], "--epoch", 1, env=b_env)
    code, _ = w.chantier("pause", "--epoch", 1, env=b_env)
    check("`pause` prices two Chief of Staff sessions, blocked by neither's file", code == 0,
          w.last_stderr)
    code, _ = w.chantier("close", "--batch", w.name, "--yes", env=b_env)
    check("`close` prices two Chief of Staff sessions, blocked by neither's file", code == 0,
          w.last_stderr)
    w.chantier("seat", "leave", "sess-b", env=b_env)
    _, out = w.chantier("seat", "get")
    check("`seat leave` frees the seat", out == ["seat none"], str(out))
    w.env.pop("CHANTIER_BATCH", None)
    w.reset()


def foreman_chief_lines(w: World) -> None:
    """Foreman mode: a timed Chief of Staff transcript (a steering call, a grill turn, a spec-writer
    turn) prices into the two lines outside the budget, which add up to everything priced since
    the batch opened and leave `spent_usd` alone."""
    slug = "".join(ch if ch.isalnum() else "-" for ch in str(w.work.resolve()))
    chief = w.root / "claude-projects" / slug / "uuid-chief.jsonl"
    kept = chief.read_text(encoding="utf-8")
    spent = w.batch()["spent_usd"]
    opened = datetime.fromisoformat(w.batch()["created"].replace("Z", "+00:00"))

    def at(minutes: int) -> str:
        return (opened + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    def call(mid: str, stamp: str, *blocks) -> str:
        return json.dumps({"type": "assistant", "timestamp": stamp, "message": {
            "id": mid, "model": "claude-sonnet-5-5", "content": list(blocks), "usage": {
                "input_tokens": 10, "output_tokens": 1_000_000, "cache_read_input_tokens": 20_000,
                "cache_creation": {"ephemeral_1h_input_tokens": 2_000}}}}) + "\n"

    def wake(stamp: str) -> str:
        return json.dumps({"type": "user", "timestamp": stamp, "message": {"content": "go"}}) + "\n"

    answers = {"type": "tool_use", "name": "Edit", "input": {"file_path": "x/02-answers.md"}}
    writer = {"type": "tool_use", "name": "Agent", "input": {"subagent_type": "chantier:spec-writer"}}
    reads = {"type": "tool_use", "name": "Read", "input": {"file_path": "x/03-change-spec.md"}}
    try:
        chief.write_text(wake(at(1)) + call("f-steer", at(2)) + wake(at(3)) + call("f-g1", at(4), answers)
                         + wake(at(5)) + call("f-g2", at(6), writer)
                         + wake(at(7)) + call("f-g3", at(8), reads), encoding="utf-8")
        _, out = w.chantier("cost", "--batch", w.name)
        steer = next((ln for ln in out if ln.startswith("Chief of Staff, steering the batch (outside")), "")
        grill = next((ln for ln in out if ln.startswith("Chief of Staff, grill and")), "")
        whole = next((ln for ln in out if ln.startswith("Chief of Staff, whole session")), "")
        money = lambda ln: float(re.search(r"\$(\d+\.\d+)", ln)[1]) if ln else -1.0
        a, b, total = money(steer), money(grill), money(whole)
        check("Foreman mode: the Chief of Staff's two lines add up to everything priced since the "
              "batch opened, each with its call count, and nothing of it is in the spend",
              "(1 calls)" in steer and "(3 calls, 0 spec-writers)" in grill
              and abs(a + b - total) <= 0.02 and abs(a * 3 - b) <= 0.02 and a > 0
              and abs(w.batch()["spent_usd"] - spent) < 0.001, str(out))
    finally:
        chief.write_text(kept, encoding="utf-8")
        w.chantier("cost", "--batch", w.name)  # the stored spend is the batch's own again


def direct_batch(w: World) -> None:
    """A batch steered by the Chief of Staff itself, from `open` to `close`, priced with one steering
    row and a Chief of Staff line that leaves the steering window out; then a Foreman takes it over."""
    note("\n## 16. Direct mode: the Chief of Staff steers the batch")
    slug = "".join(ch if ch.isalnum() else "-" for ch in str(w.work.resolve()))
    chief = w.root / "claude-projects" / slug / "uuid-chief.jsonl"
    kept = chief.read_text(encoding="utf-8") if chief.is_file() else None
    sub = chief.with_suffix("") / "subagents"
    t0, t1 = "2026-03-01T00:00:00Z", "2026-03-01T01:00:00Z"  # the opening, then the claim

    def at(minutes: int) -> str:
        return (datetime.fromisoformat(t1.replace("Z", "+00:00")) + timedelta(minutes=minutes)
                ).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    def msg(mid: str, stamp: str) -> str:
        return json.dumps({"type": "assistant", "timestamp": stamp, "message": {
            "id": mid, "model": "claude-sonnet-5-5", "usage": {
                "input_tokens": 10, "output_tokens": 1_000_000, "cache_read_input_tokens": 20_000,
                "cache_creation": {"ephemeral_1h_input_tokens": 2_000}}}}) + "\n"

    def edit(**fields) -> None:
        state = w.folder() / "batch.json"
        state.write_text(json.dumps({**w.batch(), **fields}))

    def money(out: list[str], start: str) -> float:
        line = next(ln for ln in out if ln.startswith(start))
        return float(re.search(r"\$(\d+\.\d+)", line)[1])

    code, out = w.chantier("preflight", env={"CLAUDE_CODE_ENTRYPOINT": "cli"}, expect=2)
    check("preflight refuses a terminal session while a Foreman must start", code == 2
          and out[0].startswith("P1 FAIL"), str(out))
    code, out = w.chantier("preflight", "--direct", env={"CLAUDE_CODE_ENTRYPOINT": "cli"})
    check("`preflight --direct` passes P1 on any Claude Code entry point and leaves P2 out",
          code == 0 and out[0].startswith("P1 ok") and "P2" not in "\n".join(out), str(out))
    _, item = prepare_cr(w, "Direct work")
    _, extra = prepare_cr(w, "Direct extra")
    _, extra_after = prepare_cr(w, "Direct extra after the takeover")
    _, later = prepare_cr(w, "Direct after the pause")
    _, later2 = prepare_cr(w, "Direct after the pause, too")
    _, rel_item = prepare_cr(w, "Direct release")
    w.reset()
    code, out = w.chantier("open", item, "--direct", *FROM_AGENTS_MD, env={"CLAUDE_CODE_SESSION_ID": ""},
                           expect=2)
    check("`open --direct` needs the Chief of Staff's own session id", code == 2
          and "session id" in w.last_stderr, w.last_stderr)
    w.start(item, "--direct", "--slots", 1, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    check("`open --direct` records the steering, and says to steer it yourself",
          w.batch()["steering"] == "direct" and w.last_out[1].endswith("then steer it yourself")
          and "steering direct" in w.last_out[0]
          and "Steering: direct" in (w.folder() / "brief.md").read_text(encoding="utf-8"),
          str(w.last_out))
    _, out = w.chantier("status")
    check("`status` and STATUS.md show who steers and the shape",
          " steering direct (the Chief of Staff) shape parallel " in out[0]
          and "steered by the Chief of Staff (direct mode) · independent PRs (parallel)" in
          (w.folder() / "STATUS.md").read_text(encoding="utf-8")
          and json.loads((w.folder() / "STATUS.json").read_text(encoding="utf-8"))["steering"]
          == "direct", str(out))
    kept_batch = w.batch()
    state = w.folder() / "batch.json"
    for fields, words, what in (({"mode": "series"}, " shape series ", "series for a --mode series batch"),
                                ({"mode": "stack"}, " shape stack ", "stack for a --mode stack batch"),
                                ({"steering": None}, " steering unknown ", "steering unknown, not foreman, "
                                 "when batch.json has no steering")):
        state.write_text(json.dumps({k: v for k, v in {**kept_batch, **fields}.items() if v is not None}))
        _, out = w.chantier("status")
        check(f"`status` says {what}", words in out[0], str(out))
    w.chantier("order", "note", w.batch()["crs"][0]["id"], "--note", "a batch.json without a steering")
    check("STATUS.json says null for a steering it does not know",
          json.loads((w.folder() / "STATUS.json").read_text(encoding="utf-8"))["steering"] is None
          and "steering unknown" in (w.folder() / "STATUS.md").read_text(encoding="utf-8"))
    state.write_text(json.dumps(kept_batch))
    w.chantier("foreman", "set", "uuid-chief", "--epoch", 1)
    w.chantier("foreman", "transcript", "uuid-chief", "--epoch", 1)
    edit(created=t0, foreman_claims=[{"transcript": "uuid-chief", "since": t1}])
    code, _ = w.chantier("order", "qa", "--note", "try it", expect=2)
    check("`order qa` is refused on a running direct batch",
          "a running direct batch takes no QA" in w.last_stderr and len(w.batch()["crs"]) == 1,
          w.last_stderr)

    # The heartbeat says something true: the minutes since the last `status --refresh --epoch`.
    def hb_line(out: list[str]) -> str:
        return re.search(r"heartbeat (.*?) spent ", out[0])[1]

    def hb_minutes(text: str) -> int:
        return int(re.match(r"(\d+) min", text)[1])

    def events(kind: str) -> int:
        return sum(1 for ln in (w.folder() / "events.jsonl").read_text(encoding="utf-8").splitlines()
                   if json.loads(ln).get("kind") == kind)

    check("a batch that never woke prints `heartbeat never`", w.batch()["heartbeat"] is None
          and hb_line(w.chantier("status")[1]) == "never")
    _, out = w.chantier("status", "--refresh", "--epoch", 1, expect=None)
    check("a batch's first wake prints `heartbeat 0 min` with no gap, and logs its event",
          hb_line(out) == "0 min" and w.batch()["heartbeat"] and events("heartbeat") == 1, str(out))
    old = (datetime.now(timezone.utc) - timedelta(minutes=45)).strftime("%Y-%m-%dT%H:%M:%SZ")
    edit(heartbeat=old)
    _, out = w.chantier("status")
    check("`status` prints the minutes since the last wake", abs(hb_minutes(hb_line(out)) - 45) <= 1,
          str(out))
    _, out = w.chantier("status", "--refresh", expect=None)
    check("`status --refresh` with no epoch moves no heartbeat and still prints the true age",
          w.batch()["heartbeat"] == old and abs(hb_minutes(hb_line(out)) - 45) <= 1
          and events("heartbeat") == 1, str(out))
    _, out = w.chantier("status", "--refresh", "--epoch", 1, expect=None)
    check("a wake records the heartbeat and prints the gap since the wake before",
          w.batch()["heartbeat"] != old and events("heartbeat") == 2
          and re.fullmatch(r"0 min \((44|45|46) min since the last\)", hb_line(out)) is not None,
          str(out))
    _, out = w.chantier("status")
    check("the status after a wake prints `heartbeat 0 min`", hb_line(out) == "0 min", str(out))
    before = (w.folder() / "batch.json").read_bytes()
    code, _ = w.chantier("status", "--stop-heartbeat", "--epoch", 2, expect=3)
    check("recording the stop with a stale epoch is refused and changes nothing",
          code == 3 and (w.folder() / "batch.json").read_bytes() == before, w.last_stderr)
    code, out = w.chantier("status", "--stop-heartbeat", "--epoch", 1)
    _, out = w.chantier("status")
    check("recording the stop makes `status` print `heartbeat stopped`, logs one event, and shows "
          "the mark in STATUS.json",
          hb_line(out) == "stopped" and events("heartbeat_stopped") == 1
          and json.loads((w.folder() / "STATUS.json").read_text(encoding="utf-8"))
          ["heartbeat_stopped"], str(out))
    _, out = w.chantier("status", "--refresh", expect=None)
    check("a refresh with no epoch leaves the stop in place", hb_line(out) == "stopped", str(out))
    _, out = w.chantier("status", "--refresh", "--epoch", 1, expect=None)
    check("the next wake clears the stop and prints its gap", w.batch()["heartbeat_stopped"] is None
          and re.fullmatch(r"0 min \(\d+ min since the last\)", hb_line(out)) is not None, str(out))
    _, out = w.chantier("order", "add", "--note", str(extra))
    check("`order add` queues a CR on a running direct batch",
          any("queued" in ln for ln in out) and len(w.batch()["crs"]) == 2
          and w.batch()["crs"][1]["status"] == "queued", str(out))
    w.chantier("order", "drop", w.batch()["crs"][1]["id"])
    check("the CR added to the running direct batch can be dropped again",
          w.batch()["crs"][1]["status"] == "cancelled", str(w.batch()["crs"][1]["status"]))
    fm = Foreman(w, epoch=1)
    fm.turn()
    cr = w.batch()["crs"][0]["id"]
    check("the Chief of Staff, as steering session, starts the Driver as a Foreman does",
          fm.started == [cr] and w.cr(cr)["status"] == "working", str(fm.started))
    sub.mkdir(parents=True, exist_ok=True)
    # outside the window: an earlier session, then a call after the opening and before the claim;
    # inside it: two calls of the steering and three of its Driver
    def wake(stamp: str) -> str:
        return json.dumps({"type": "user", "timestamp": stamp, "message": {"content": "go"}}) + "\n"

    def uses(mid: str, stamp: str, *blocks) -> str:  # a call whose record carries tool uses
        return json.dumps({"type": "assistant", "timestamp": stamp, "message": {
            "id": mid, "model": "claude-sonnet-5-5", "content": list(blocks), "usage": {
                "input_tokens": 10, "output_tokens": 1_000_000, "cache_read_input_tokens": 20_000,
                "cache_creation": {"ephemeral_1h_input_tokens": 2_000}}}}) + "\n"

    def boundary(stamp: str) -> str:
        return json.dumps({"type": "system", "subtype": "compact_boundary", "timestamp": stamp}) + "\n"

    answers = {"type": "tool_use", "name": "Edit", "input": {"file_path": "x/02-answers.md"}}
    writer_use = {"type": "tool_use", "name": "Agent", "input": {"subagent_type": "chantier:spec-writer"}}
    # a steering turn that only names a specification (a Driver's prompt) and reads one: it stays
    # on the steering row, not on the grill line
    names_spec = {"type": "tool_use", "name": "Agent", "input": {
        "subagent_type": "chantier:cr-driver", "prompt": "work from x/03-change-spec.md"}}
    reads_spec = {"type": "tool_use", "name": "Read", "input": {"file_path": "x/03-change-spec.md"}}
    # before the opening: a compaction and a grill turn of an earlier batch (in the whole session
    # only); in the window: two steering calls, a turn that only names a specification, a grill turn, a spec-writer turn, two compactions,
    # and a call repeated after the first of them (same message id: priced once)
    chief.write_text(
        msg("c-old", "2000-01-01T00:00:00.000Z") + boundary("2000-01-01T00:00:01.000Z")
        + wake("2000-01-01T00:00:02.000Z") + uses("c-oldg", "2000-01-01T00:00:03.000Z", answers)
        + wake("2026-03-01T00:09:00.000Z") + msg("c-pre", "2026-03-01T00:10:00.000Z") + wake(at(5)) + msg("c-in1", at(10))
        + msg("c-in2", at(20)) + wake(at(21)) + uses("c-g1", at(22), answers)
        + wake(at(23)) + uses("c-g2", at(24), writer_use) + boundary(at(25)) + boundary(at(26))
        + msg("c-g2", at(27))
        + wake(at(28)) + uses("c-nm", at(29), names_spec, reads_spec), encoding="utf-8")
    driver = sub / "agent-agent-1.jsonl"
    driver.write_text("".join(msg(f"d{i}", at(15)) for i in range(3)), encoding="utf-8")
    driver.with_suffix("").with_suffix(".meta.json").write_text(
        json.dumps({"agentType": "cr-driver"}), encoding="utf-8")
    driver_round(w, cr, "direct.py", "DIRECT = True\n")
    w.ready(cr, w.cr(cr)["pr"])
    fm.turn()
    w.chantier("order", "merged", cr)
    fm.turn()
    check("a direct batch runs from open to the pause", fm.paused and w.batch()["status"] == "paused",
          str(w.batch()["status"]))
    _, out = w.chantier("cost")
    cost_out = out
    ROW, STEER, GRILL, WHOLE = ("Chief of Staff, steering the batch: ",
                                "Chief of Staff, steering the batch (outside the budget): ",
                                "Chief of Staff, grill and specifications with the user (outside the budget): ",
                                "Chief of Staff, whole session: ")
    lines = [ln for ln in out if ln.startswith(("Foreman", ROW, "Driver"))]
    printed = [int(a.replace(".", "")) for ln in lines for a in re.findall(r"\$(\d+\.\d{3}) \(", ln)]
    check("`cost` shows one 'Chief of Staff, steering the batch' row without the grill turns, no "
          "'Foreman' row, and the lines add up",
          [ln.split(":")[0] for ln in lines] == ["Chief of Staff, steering the batch", "Driver cr-driver"]
          and "(3 calls," in lines[0] and "(3 calls," in lines[1]
          and out[0].split()[1] == f"${sum(printed) / 1000:.3f}"
          and not any("Chief of Staff (steering)" in ln for ln in out), str(out))
    steering = money(out, ROW)
    one = steering / 3  # a call of the Chief of Staff's transcript
    a, b, whole = money(out, STEER), money(out, GRILL), money(out, WHOLE)
    check("the Chief of Staff's lines add up: the steering row's three calls (one of them names and reads a specification: steering), one steering call "
          "before the claim, the two grill and specification turns (the repeated call priced once), "
          "and the whole session leaves the steering row out",
          abs(a - one) <= 0.02 and abs(b - 2 * one) <= 0.02 and abs(whole - 5 * one) <= 0.03
          and "(1 calls)" in next(ln for ln in out if ln.startswith(STEER))
          and "(2 calls, 0 spec-writers)" in next(ln for ln in out if ln.startswith(GRILL))
          and abs(w.batch()["spent_usd"] - float(out[0].split()[1][1:])) <= 0.01
          and abs(float(out[0].split()[1][1:]) - 2 * steering) <= 0.02,
          f"{out} (steering ${steering})")
    check("the whole-session line counts the compactions of the window, not the one before it",
          "2 compactions since the batch opened" in next(ln for ln in out if ln.startswith(WHOLE)),
          str(out))
    _, out = w.chantier("cost", "--summary")
    check("the summary splits the steering under its own name", out[1].startswith(
          "Chief of Staff, steering the batch $") and "Foreman" not in out[1]
          and any(ln.startswith(GRILL) for ln in out), str(out))
    # no line that starts with "Driver" names the steering session; its figure is the steering row's
    named = ("chief-of-staff", "Chief of Staff", "Foreman")
    _, pause_summary = w.chantier("cost", "--summary")
    status_md = (w.folder() / "STATUS.md").read_text(encoding="utf-8").splitlines()
    every = out + cost_out + w.batch()["summary"] + status_md + pause_summary
    check("a direct batch: no line that starts with `Driver` names the steering session, in `cost`, "
          "`cost --summary`, the pause summary and STATUS.md's Cost; the steering figure is the row's",
          not any(re.match(r"(- )?Driver", ln) and any(n in ln for n in named) for ln in every)
          and abs(float(re.match(r"Chief of Staff, steering the batch \$(\d+\.\d\d)", out[1])[1])
                  - steering) <= 0.006, str(every))
    # a spec-writer of the Chief of Staff, in the window: on the grill line, not the batch's
    grill_before = b
    writer = sub / "agent-agent-spec.jsonl"
    writer.write_text("".join(msg(f"s{i}", at(30)) for i in range(2)), encoding="utf-8")
    writer.with_suffix("").with_suffix(".meta.json").write_text(
        json.dumps({"agentType": "spec-writer"}), encoding="utf-8")
    _, out = w.chantier("cost")
    check("a spec-writer's transcript is left out of the batch's cost and kept on the grill and "
          "specifications line", out[0] == cost_out[0]
          and "spec-writer" not in "\n".join(ln for ln in out if not ln.startswith(GRILL))
          and money(out, GRILL) > grill_before and abs(money(out, GRILL) - 4 * one) <= 0.03
          and "(4 calls, 1 spec-writers)" in next(ln for ln in out if ln.startswith(GRILL)),
          f"{out} (before: {grill_before})")
    writer.unlink()
    writer.with_suffix("").with_suffix(".meta.json").unlink()
    # a subagent no Driver owns is the steering session's own: its own line, not a Driver's
    own = sub / "agent-agent-own.jsonl"
    own.write_text("".join(msg(f"o{i}", at(31)) for i in range(2)), encoding="utf-8")
    own.with_suffix("").with_suffix(".meta.json").write_text(
        json.dumps({"agentType": "Explore"}), encoding="utf-8")
    _, out = w.chantier("cost")
    check("`cost` puts a subagent the steering session ran itself on its own line, not on a Driver",
          any(ln.startswith("Chief of Staff's own subagents") and "(2 calls," in ln for ln in out)
          and not any(ln.startswith("Driver") and "Explore" in ln for ln in out), str(out))
    own.unlink()
    own.with_suffix("").with_suffix(".meta.json").unlink()
    # a paused batch takes any number of new CRs and stays paused; the first `take` runs it again
    paused_at = w.batch()["paused"]
    summary = w.batch()["summary"]
    for n, folder in enumerate((later, later2), start=3):
        w.chantier("order", "add", "--note", str(folder))
        b = w.batch()
        check(f"`order add` {n - 1} on a paused direct batch leaves it paused, with the new CR queued",
              b["status"] == "paused" and b.get("paused") == paused_at and b.get("summary") == summary
              and len(b["crs"]) == n and b["crs"][-1]["status"] == "queued"
              and "stays paused: the first `take` sets it running again" in "\n".join(w.last_out),
              str(w.last_out))
    cr2, cr3 = w.batch()["crs"][2]["id"], w.batch()["crs"][3]["id"]
    check("both new CRs are in the paused batch", {cr2, cr3} <= {c["id"] for c in w.batch()["crs"]})
    code, _ = w.chantier("order", "add", "--note", str(later), expect=None)
    check("a CR folder already in the paused batch is not added twice",
          code != 0 and len(w.batch()["crs"]) == 4, w.last_stderr)
    fm.turn()
    b = w.batch()
    check("the first `take` sets the paused direct batch running again",
          b["status"] == "running" and "paused" not in b and "summary" not in b
          and cr2 in fm.started and w.cr(cr2)["status"] == "working", str(fm.started))
    kinds = [json.loads(e)["kind"] for e in
             (w.folder() / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    check("the first `take` says the batch was paused, and the event log has `reopen` before "
          "that `take`", "was paused: running again" in "\n".join(fm.facts)
          and "reopen" in kinds and kinds[::-1].index("take") < kinds[::-1].index("reopen"),
          str(kinds[-8:]))
    for cr_n, name in ((cr2, "direct2.py"), (cr3, "direct3.py")):
        if cr_n not in fm.started:
            fm.turn()
        check(f"the reopened direct batch starts {cr_n}", cr_n in fm.started
              and w.cr(cr_n)["status"] == "working", str(fm.started))
        driver_round(w, cr_n, name, f"DIRECT = {name!r}\n")
        w.ready(cr_n, w.cr(cr_n)["pr"])
        fm.turn()
        w.chantier("order", "merged", cr_n)
        fm.turn()
    check("the reopened direct batch pauses again", fm.paused and w.batch()["status"] == "paused",
          str(w.batch()["status"]))
    age_sessions(w)
    os.utime(chief, None)  # the Chief of Staff's own session is written by the very call that closes
    os.utime(driver, None)  # a Driver's file is not
    code, _ = w.chantier("close", "--batch", w.name, "--yes", expect=2)
    check("`close` still sees a Driver that writes, on a direct batch", "agent-agent-1" in w.last_stderr
          and "uuid-chief was written" not in w.last_stderr.replace("agent-agent-1", ""), w.last_stderr)
    age_sessions(w)
    os.utime(chief, None)
    code, out = w.chantier("close", "--batch", w.name, "--yes")
    check("`close` is not blocked by the Chief of Staff's own fresh transcript", code == 0
          and not (w.folder() / "batch.json").exists(), str(out))

    # a Foreman takes the batch over: the steering switches, the old epoch is refused
    w.reset()
    shutil.rmtree(sub)
    _, other = prepare_cr(w, "Direct then Foreman")
    w.start(other, "--direct", "--slots", 1, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "uuid-chief", "--epoch", 1)
    w.chantier("foreman", "transcript", "uuid-chief", "--epoch", 1)
    edit(created=t0, foreman_claims=[{"transcript": "uuid-chief", "since": t1}])
    w.chantier("order", "add", "--release", "--note", str(rel_item))
    check("`order add --release` is accepted on a running direct batch",
          len(w.batch()["crs"]) == 2 and w.batch()["crs"][1].get("kind") == "release",
          str(w.last_out))
    w.chantier("foreman", "set", "local_foreman_next", "--epoch", 2)
    w.chantier("foreman", "transcript", "uuid-foreman", "--epoch", 2)
    d = w.batch()
    code, _ = w.chantier("status", "--refresh", "--epoch", 1, expect=3)
    check("a later epoch from another transcript switches the steering to Foreman, and refuses "
          "the old epoch", d["steering"] == "foreman" and code == 3
          and [c["transcript"] for c in d["foreman_claims"]] == ["uuid-chief", "uuid-foreman"]
          and any(json.loads(e)["kind"] == "steering" for e in
                  (w.folder() / "events.jsonl").read_text(encoding="utf-8").splitlines()), str(d))
    _, out = w.chantier("status")
    check("`status` now says Foreman", " steering Foreman shape parallel " in out[0], str(out))
    w.chantier("order", "add", "--note", str(extra_after))
    check("a batch steered by a Foreman takes added work", len(w.batch()["crs"]) == 3)
    _, out = w.chantier("cost")
    labels = [ln.split(":")[0] for ln in out if ln.startswith(("Foreman:", "Chief of Staff, steering the batch:"))]
    check("each steering session is priced under its own name", labels == [
        "Chief of Staff, steering the batch", "Foreman"] or labels == [
        "Foreman", "Chief of Staff, steering the batch"],
          str(out))
    w.env.pop("CHANTIER_BATCH", None)
    w.reset()
    if kept is None:
        chief.unlink()
    else:
        chief.write_text(kept, encoding="utf-8")


def foreman_in_a_worktree(w: World) -> None:
    note("\n## 17. A Foreman started in a worktree stops before it claims its epoch")
    prepared = prepare_cr(w, "Worktree guard")[1]
    w.reset()
    w.start(str(prepared), *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    linked = w.root / "foreman-session"
    w.sh("git", "worktree", "add", "--quiet", "--detach", str(linked), "origin/main")
    fm = Foreman(w, epoch=1)
    check("in a linked worktree the worktree check stops", fm.worktree_check("local_wt", linked) is False)
    d = w.batch()
    check("no epoch claimed, no CR taken, and the Chief of Staff hears it",
          not d.get("foreman") and all(c["status"] == "queued" for c in d["crs"])
          and not fm.started and len(fm.asked) == 1 and fm.asked[0].startswith("blocked "),
          str(fm.asked))
    code, out = w.chantier("asks", expect=None)
    check("the ask is recorded", code == 0 and any("worktree" in ln for ln in out), str(out))
    w.chantier("asks", "--read", "all")
    check("on the main checkout the same worktree check claims the epoch",
          fm.worktree_check("local_main") is True and w.batch()["foreman"] == "local_main")
    w.sh("git", "worktree", "remove", "--force", str(linked))


def status_files(w: World) -> None:
    c = w.cr("CR-104")
    folder = w.state / c["path"]
    text = (folder / "STATUS.md").read_text(encoding="utf-8")
    check("a CR's STATUS.md says where it stands and links back to its batch",
          all(part in text for part in ("**Now:**", "**Next:**", "## Progress", "- [x] Round 1",
                                        "- [x] Long gate", "- [x] Shipped", "- [x] Handed back",
                                        "## Documents", "[specification](03-change-spec.md)",
                                        "## Where", f"[{w.name}](../../STATUS.md)")), text)
    view = json.loads((folder / "STATUS.json").read_text(encoding="utf-8"))
    check("its STATUS.json says the same, with more",
          view["cr"] == "CR-104" and view["state"] == "ready" and view["step"] == "Notify"
          and view["pr"]["url"] == c["pr"] and view["steps"], str(view))
    board = (w.state / "STATUS.md").read_text(encoding="utf-8")
    batch = (w.folder() / "STATUS.md").read_text(encoding="utf-8")
    check("the status cell gives the pastille, the state, the step and the round",
          "🔵 ready Notify 1/3" in board and "🔵 ready Notify 1/3" in batch, board)
    index = json.loads((w.state / "STATUS.json").read_text(encoding="utf-8"))
    rows = [r for b in index["batches"] for r in b["crs"]]
    own = json.loads((w.folder() / "STATUS.json").read_text(encoding="utf-8"))["crs"]
    check("the index gives each batch its heartbeat and pending orders, and each CR row its "
          "blocked reason, silent time and folder, relative to .agents/changes/ in the batch's file too",
          index["schema"] == 3 and rows
          and all({"heartbeat", "orders_pending"} <= set(b) for b in index["batches"])
          and all({"blocked", "silent_minutes", "folder"} <= set(r) for r in rows + own)
          and all((w.state / r["folder"] / "STATUS.json").is_file()
                  for r in rows + own if r["folder"]), str(rows[:1]))
    check("a CR that is not working has no silent time, and none is blocked here",
          all(r["silent_minutes"] is None and r["blocked"] is None
              for r in rows if r["state"] == "ready"), str(rows))
    links = [(w.state, ln) for ln in re.findall(r"\]\(([^)h][^)]*)\)", board)]
    links += [(w.folder(), ln) for ln in re.findall(r"\]\(([^)h][^)]*)\)", batch)]
    check("every link of the board and the batch resolves",
          links and all((start / ln).exists() for start, ln in links), str(links))


def board_index(w: World, d: dict) -> None:
    """The index the CR board reads: the merged and trashed CRs, their totals and the limit."""
    path = w.state / "STATUS.json"
    index = json.loads(path.read_text(encoding="utf-8"))
    merged = {c["id"] for c in d["crs"] if c["status"] == "merged"}
    got = {e["cr"]: e for e in index["merged"]}
    check("the index lists the merged CRs with their state, batch, PR, cost, time and folder",
          merged <= set(got) and index["merged_total"] >= len(merged)
          and all(got[i]["state"] == "merged" and got[i]["batch"] == w.name
                  and got[i]["pr"] and got[i]["cost_usd"] is not None
                  and re.fullmatch(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ", got[i]["when"])
                  and (w.state / got[i]["path"] / "STATUS.json").is_file()
                  for i in merged), str(index["merged"]))
    check("the index lists the trashed CR, with a total",
          any(e["cr"] == "CR-103" and e["state"] == "cancelled" for e in index["trashed"])
          and index["trashed_total"] >= 1, str(index["trashed"]))
    merged_before = index["merged_total"]
    stage = w.state / "5-archives"
    stage.mkdir(exist_ok=True)
    made = []
    for n in range(60):  # older than any real archive, none with a STATUS.json
        folder = stage / f"250101-{n // 60:02d}{n % 60:02d}-padding-{n}"
        folder.mkdir()
        made.append(folder)
        (folder / "01-intent.md").write_text(f"# Padding {n}\n", encoding="utf-8")
    w.chantier("file", "Board index probe")  # rewrites the index
    index = json.loads(path.read_text(encoding="utf-8"))
    whens = [e["when"] for e in index["merged"]]
    bare = [e for e in index["merged"] if e["cr"] is None]
    check("the index keeps the last 50 merged CRs, newest first, and counts them all",
          len(index["merged"]) == 50 and index["merged_total"] == merged_before + 60
          and whens == sorted(whens, reverse=True) and not any("padding" in e["path"] for e in index["merged"][:len(merged)]),
          f"{len(index['merged'])} of {index['merged_total']}")
    check("a folder without a STATUS.json gives its title and null for the rest",
          all(e["title"].startswith("Padding") and e["state"] is None and e["pr"] is None
              and e["cost_usd"] is None and e["batch"] is None for e in bare) and bare,
          str(bare[:1]))
    for folder in made:
        shutil.rmtree(folder)
    # the spec-writer's state, read from the folder: none, specifying, then specified
    probe = next(r for r in index["backlog"] if r["title"].startswith("Board index probe"))
    item = w.state / probe["path"]

    refreshes = [0]

    def spec_of() -> object:
        refreshes[0] += 1
        w.chantier("file", f"Spec state refresh {refreshes[0]}")  # rewrites the index
        again = json.loads(path.read_text(encoding="utf-8"))["backlog"]
        return next(r for r in again if r["path"] == probe["path"]).get("spec")

    check("an inbox item with no specification has no spec state", probe.get("spec") is None
          and spec_of() is None, str(probe))
    (item / "work").mkdir(exist_ok=True)
    (item / "work" / "specifying").write_text("2026-11-07T10:00:00Z agent-1\n", encoding="utf-8")
    check("work/specifying makes the item `specifying`, in STATUS.json and STATUS.md",
          spec_of() == "specifying" and "specifying" in (w.state / "STATUS.md").read_text(
              encoding="utf-8"), "")
    (item / "03-change-spec.md").write_text("# Spec\n", encoding="utf-8")
    check("a specification still being written stays `specifying`", spec_of() == "specifying", "")
    (item / "work" / "specifying").unlink()
    check("the specification without work/specifying makes it `specified`", spec_of() == "specified"
          and "specified" in (w.state / "STATUS.md").read_text(encoding="utf-8"), "")


def age_sessions(w: World, seconds: int = 600) -> None:
    """The session files of the fixture, last written `seconds` ago: `close` reads their times."""
    then = time.time() - seconds
    for base in ("claude-projects", "copilot-home"):
        for f in (w.root / base).rglob("*"):
            if f.is_file():
                os.utime(f, (then, then))


def priced_foreman(w: World) -> None:
    """Give the running batch a Foreman transcript with one priced call, written long ago: `close`
    prices the batch before anything is touched, and refuses a batch it cannot price."""
    slug = "".join(ch if ch.isalnum() else "-" for ch in str(w.work.resolve()))
    f = w.root / "claude-projects" / slug / "uuid-closing.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"type": "assistant", "message": {
        "id": "closing", "model": "claude-sonnet-5-5", "usage": {
            "input_tokens": 10, "output_tokens": 300, "cache_read_input_tokens": 20_000,
            "cache_creation": {"ephemeral_1h_input_tokens": 2_000}}}}) + "\n")
    then = time.time() - 600
    os.utime(f, (then, then))
    state = w.folder() / "batch.json"
    d = json.loads(state.read_text())
    d.pop("foreman_transcripts", None)
    state.write_text(json.dumps({**d, "foreman_transcript": "uuid-closing"}))


MYSTERY_CALL = json.dumps({"type": "assistant", "message": {
    "id": "mys-1", "model": "mystery-model", "usage": {"input_tokens": 1000, "output_tokens": 2000}}}) + "\n"
DATED_CALL = MYSTERY_CALL.replace("mys-1", "mys-2").replace("mystery-model", "mystery-model-20270101")
MYSTERY_PRICES = ("prices:\n  mystery-model:\n    input: 1\n    cache_write_5m: 1\n"
                  "    cache_write_1h: 1\n    cache_read: 1\n    output: 1\n")


def unpriced_model(w: World, main: Path, name: str) -> None:
    """One call of a model with no price: counted and named, never priced, never a block; the
    figures are a floor everywhere. A price in `chantier.yaml` prices it, the dated id too."""
    yaml = w.work / "chantier.yaml"
    before = main.read_text()
    _, out = w.chantier("cost", "--batch", name)
    total, calls = float(re.search(r"\$(\d+\.\d{3}) over", out[0])[1]), int(re.search(r"over (\d+) ", out[0])[1])
    main.write_text(before + MYSTERY_CALL)
    code, out = w.chantier("cost", "--batch", name)
    shared = [ln for ln in out if re.match(r"(Foreman|Driver|Worker|Agent)\b", ln)]
    check("a model with no price: `cost` says `at least` with the priced calls and counts the others "
          "apart", code == 0 and out[0] == f"{name}: at least ${total:.3f} over {calls} priced model "
          "calls; 1 calls of mystery-model not priced", str(out))
    check("each share reads `share not measured` and the ratio `not measured (calls not priced)`, "
          "with the one line that gives the id to add",
          shared and all("share not measured" in ln for ln in shared)
          and "Orchestration (steering + Drivers): not measured (calls not priced)" in out
          and out.count("mystery-model has no price: add it under prices: in chantier.yaml "
                        "(exact id: mystery-model)") == 1, str(out))
    _, out = w.chantier("cost", "--explain", "--batch", name)
    check("`--explain` names the model with `(not priced)` and the shares as of the priced calls",
          any("model claude-sonnet-5-5, mystery-model (not priced)" in ln or
              "mystery-model (not priced)" in ln for ln in out)
          and any("cost of the priced calls:" in ln for ln in out), str(out))
    _, out = w.chantier("cost", "--summary", "--batch", name)
    check("`--summary` gives `at least`, the not-priced calls, and `not measured` shares",
          out[0].startswith("Total: at least $") and out[0].endswith("; 1 calls of mystery-model not priced")
          and "(not measured)" in out[1] and "(%)" not in out[1], str(out))
    code, out = w.chantier("status", "--refresh", "--batch", name)
    check("`status --refresh` records the floor and does not say `spend not updated`",
          code == 0 and not any("spend not updated" in ln for ln in out)
          and any(ln.startswith("spent at least $") and "1 calls of mystery-model not priced" in ln
                  for ln in out) and w.batch()["unpriced"] == {"mystery-model": 1}, str(out))
    _, out = w.chantier("status", "--batch", name)
    report = (w.folder() / "STATUS.md").read_text(encoding="utf-8")
    board = (w.state / "STATUS.md").read_text(encoding="utf-8")
    data = json.loads((w.folder() / "STATUS.json").read_text(encoding="utf-8"))
    check("`status`, the batch's STATUS.md, its STATUS.json and the board say `at least`",
          re.search(r"spent at least \$\d+\.\d\d of \$50", out[0])
          and re.search(r"spent at least \$\d+\.\d\d", report)
          and re.search(r"at least \$\d+\.\d\d of \$50", board)
          and data["unpriced"] == {"mystery-model": 1} and data["priced"] is True,
          f"{out[0]}\n{report}\n{board}")
    # a price of the project's prices it, with no release; the dated id by the same entry
    yaml.write_text(MYSTERY_PRICES, encoding="utf-8")
    code, out = w.chantier("cost", "--batch", name)
    check("a `prices:` entry in chantier.yaml prices the call: no `at least`, the total grows by the "
          "expected amount", code == 0 and out[0].startswith(f"{name}: $")
          and "at least" not in "\n".join(out)
          and abs(float(re.search(r"\$(\d+\.\d{3}) over", out[0])[1]) - total - 0.003) <= 0.0011
          and f"over {calls + 1} model calls" in out[0], str(out))
    main.write_text(before + MYSTERY_CALL + DATED_CALL)
    code, out = w.chantier("cost", "--batch", name)
    check("a dated id (mystery-model-20270101) is priced by the same entry",
          code == 0 and "at least" not in "\n".join(out)
          and abs(float(re.search(r"\$(\d+\.\d{3}) over", out[0])[1]) - total - 0.006) <= 0.0016
          and f"over {calls + 2} model calls" in out[0], str(out))
    _, out = w.chantier("playbook")
    check("`playbook` prints the `prices:` line", "prices: mystery-model (chantier.yaml, above the "
          "built-in table)" in out, str(out))
    yaml.write_text("prices:\n  mystery-model:\n    input: 1\n", encoding="utf-8")
    code, out = w.chantier("cost", "--batch", name, expect=2)
    check("a chantier.yaml that is not valid makes `cost` refuse with its line, never price with the "
          "file ignored", code == 2 and "chantier.yaml:2:" in w.last_stderr
          and "$CHANTIER playbook" in w.last_stderr and not out, w.last_stderr)
    yaml.unlink()
    main.write_text(before + MYSTERY_CALL)


def close_refusals(w: World) -> None:
    """A paused batch shows its cost to date; the first `take` reopens it; `close` refuses while any
    CR, order, stack agent or session file shows that something runs."""
    name, state = w.name, w.folder() / "batch.json"
    slug = "".join(ch if ch.isalnum() else "-" for ch in str(w.work.resolve()))
    main = w.root / "claude-projects" / slug / "uuid-foreman.jsonl"
    sub = main.with_suffix("") / "subagents"
    w.chantier("status", "--refresh", "--batch", name)
    code, out = w.chantier("status", "--batch", name)
    d = w.batch()
    check("`pause` records the cost to date, in the summary and in `status`",
          "paused, cost to date" in out[0] and d["summary"][-1].startswith("To date")
          and not any("Not final" in ln for ln in d["summary"])
          and d["status"] == "paused" and d.get("paused"), str(out))
    before = state.read_text()
    code, _ = w.chantier("pause", "--batch", name, "--epoch", 2, expect=2)
    check("a second `pause` on a paused batch is refused and changes nothing",
          code == 2 and "already paused" in w.last_stderr and "first `take`" in w.last_stderr
          and state.read_text() == before,
          w.last_stderr)
    w.chantier("status", "--refresh", "--batch", name)
    report = (w.folder() / "STATUS.md").read_text(encoding="utf-8")
    header = re.search(r"spent \$(\d+\.\d\d)([^·\n]*)", report)
    total = re.search(r"Total: \$(\d+\.\d\d)", report)
    check("STATUS.md shows one total in its header and its Cost section, marked (to date)",
          header and total and header[1] == total[1] and "(to date)" in header[2]
          and "To date" in report and "Not final" not in report
          and report.startswith(f"# {w.name}: paused") and "## Paused" in report, report)

    # a call made after the pause is spend
    late = json.dumps({"type": "assistant", "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"), "message": {
        "id": "after-pause", "model": "claude-sonnet-5-5", "usage": {
            "input_tokens": 10, "output_tokens": 100_000, "cache_read_input_tokens": 20_000,
            "cache_creation": {"ephemeral_1h_input_tokens": 2_000}}}}) + "\n"
    main.write_text(main.read_text() + late)
    code, out = w.chantier("cost", "--batch", name)
    check("a call made after the pause shows in `cost`",
          out[0] == f"{name}: $2.618 over 95 model calls", str(out))

    # new work leaves the paused batch paused; the first `take` sets it running again
    paused_d = w.batch()
    added = prepare_cr(w, "Work after the pause")[1]
    code, out = w.chantier("order", "add", "--batch", name, "--note", str(added))
    d = w.batch()
    new = d["crs"][-1]["id"]
    check("`order add` on a paused batch leaves it paused, keeps its pause and summary, queues the "
          "CR, with a line that says so",
          d["status"] == "paused" and d.get("paused") == paused_d["paused"]
          and d.get("summary") == paused_d["summary"] and w.cr(new)["status"] == "queued"
          and any("stays paused: the first `take` sets it running again" in ln for ln in out),
          str(out))
    code, _ = w.chantier("order", "add", "--batch", name, "--note", str(added), expect=None)
    check("a CR folder already queued in the paused batch is refused, the batch unchanged",
          code != 0 and len(w.batch()["crs"]) == len(d["crs"]), w.last_stderr)
    for extra in ((), ("--yes",)):
        code, out = w.chantier("close", "--batch", name, *extra, expect=2)
        check(f"`close{' --yes' if extra else ''}` on the paused batch names what holds it, with the "
              "queued CR, not a bare usage error",
              code == 2 and f"cannot close {name}, something still runs" in w.last_stderr
              and f"{new} is queued" in w.last_stderr and "paused: none" not in w.last_stderr
              and (w.folder() / "batch.json").is_file(), w.last_stderr)
    # a refused take leaves the batch paused and unchanged (no free slot)
    held = state.read_text()
    state.write_text(json.dumps({**json.loads(held), "slots": 0}))
    zero = state.read_text()
    code, _ = w.chantier("take", new, "--epoch", 2, expect=None)
    check("a refused `take` on a paused batch leaves it paused and unchanged",
          code != 0 and state.read_text() == zero and w.batch()["status"] == "paused", w.last_stderr)
    state.write_text(held)
    # the steering takes it, without --batch: the CR is found in a paused batch, which runs again
    unpriced_model(w, main, name)  # a call of a model with no price is in the transcript now
    code, out = w.chantier("take", new, "--epoch", 2)
    d = w.batch()
    check("`take` on a queued CR is not refused for a model with no price, and the batch keeps "
          "its calls apart", d["status"] == "running" and d.get("unpriced") == {"mystery-model": 1},
          str(d.get("unpriced")))
    check("`take` finds a paused batch's CR and sets the batch running again, with a line that "
          "says so", d["status"] == "running" and "paused" not in d and "summary" not in d
          and any("was paused: running again" in ln for ln in out) and w.cr(new)["status"] == "working",
          str(out))
    main.write_text(main.read_text().replace(MYSTERY_CALL, ""))  # the later steps price as before
    w.chantier("cancel", new, "--epoch", 2)
    for o in w.batch()["orders"]:
        if not o["done"]:
            w.chantier("order", "done", o["id"], "--epoch", 2)
    age_sessions(w)
    for extra in ((), ("--yes",)):
        code, out = w.chantier("close", "--batch", name, *extra, expect=2)
        check(f"`close{' --yes' if extra else ''}` on a running batch where nothing runs says it is not "
              "paused and `pause` comes first",
              code == 2 and "not paused" in w.last_stderr and "`pause` comes first" in w.last_stderr
              and "paused: none" not in w.last_stderr and (w.folder() / "batch.json").is_file(), w.last_stderr)
    _, out = w.chantier("pause", "--epoch", 2)
    d = w.batch()
    check("`pause` runs again at the end of the reopened batch, and counts the later call",
          d["status"] == "paused" and d["paused"] and "Total: $2.62" in "\n".join(d["summary"]),
          str(d.get("summary")))
    check("`pause` prints the cost summary, past ten lines and not cut, ending with the to-date line",
          any(ln.startswith("Total: $") for ln in out) and out[0].startswith(f"paused {name}")
          and out[-1].startswith("To date") and not any("more lines" in ln for ln in out), str(out))
    # a call made after the LAST pause: `close` counts it, `pause` could not
    w.paused_total = float(re.search(r"Total: \$(\d+\.\d\d)", "\n".join(d["summary"]))[1])
    later = json.loads(late)
    later["message"]["id"] = "after-last-pause"
    later["message"]["usage"]["output_tokens"] = 50_000
    later["timestamp"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    main.write_text(main.read_text() + json.dumps(later) + "\n")

    # close refuses, naming the cause, with and without --yes
    base = state.read_text()
    d = json.loads(base)

    def refused(label: str, text: str, change: dict | None = None, env: dict | None = None) -> None:
        if change is not None:
            state.write_text(json.dumps({**d, **change}))
        for extra in ((), ("--yes",)):
            code, out = w.chantier("close", "--batch", name, *extra, env=env, expect=2)
            check(f"`close{' --yes' if extra else ''}` refuses {label}, naming it and deleting "
                  "nothing", code == 2 and text in w.last_stderr and not out
                  and (w.folder() / "batch.json").is_file(), w.last_stderr)
        state.write_text(base)

    refused("a transcript written within 5 minutes", "transcript uuid-foreman was written")
    age_sessions(w)
    first = sorted(sub.glob("agent-*.jsonl"))[0]
    os.utime(first, None)
    refused("an agent's transcript written within 5 minutes, whatever its type", first.stem)
    age_sessions(w)
    crs = [{**c, "status": "ready"} if i == 0 else c for i, c in enumerate(d["crs"])]
    refused("a CR that is not merged", f"{d['crs'][0]['id']} is ready", {"crs": crs})
    refused("an open order", "order O-99 (qa) is open", {"orders": d["orders"] + [
        {"id": "O-99", "kind": "qa", "cr": "-", "note": "x", "sent": d["created"], "done": None}]})
    refused("a stack agent", "stack agent agent-stack is recorded", {"stack_agent": "agent-stack"})
    # a model with no price does not refuse the close: its calls are counted apart, the cost is a floor
    original, aged = main.read_text(), main.stat()
    call = json.dumps({"type": "assistant", "message": {
        "id": "mystery", "model": "mystery-model", "usage": {"input_tokens": 1, "output_tokens": 1}}}) + "\n"
    main.write_text(original + call)
    os.utime(main, (aged.st_atime, aged.st_mtime))
    code, out = w.chantier("close", "--batch", name)
    text = "\n".join(out)
    check("`close` of a batch with one call of a model with no price exits 0, prints the final cost "
          "as `at least` with the call counted apart and the line that names the id to add, and "
          "deletes nothing",
          code == 0 and re.search(r"Total: at least \$\d+\.\d\d of a \$50 budget; "
                                  r"1 calls of mystery-model not priced", text)
          and "mystery-model has no price: add it under prices: in chantier.yaml "
              "(exact id: mystery-model)" in text
          and "Not final" not in text and (w.folder() / "batch.json").is_file(), text)
    main.write_text(original)
    os.utime(main, (aged.st_atime, aged.st_mtime))
    # nothing at all can be priced (every call is of a model with no price): refused, nothing deleted
    only = main.with_name("uuid-unpriced.jsonl")
    only.write_text(call)
    os.utime(only, (aged.st_atime, aged.st_mtime))
    refused("a batch where nothing can be priced (every call of a model with no price)",
            "its final cost cannot be priced", {"foreman_transcript": "uuid-unpriced",
                                                "foreman_transcripts": ["uuid-unpriced"]})
    only.unlink()
    refused("a batch with no recorded Foreman transcript", "no Foreman transcript recorded",
            {"foreman_transcript": None, "foreman_transcripts": []})

    # Copilot: the session's events file is the only time the CLI reads
    home = w.root / "copilot-home"
    events = home / "session-state" / "uuid-foreman" / "events.jsonl"
    missing = [str(w.root / "missing-session-usage")]
    env = {"COPILOT_HOME": str(home), "CHANTIER_SESSION_USAGE": subprocess.list2cmdline(missing)
           if sys.platform == "win32" else shlex.join(missing)}
    state.write_text(json.dumps({**d, "host": "copilot"}))
    os.utime(events, None)
    refused("a Copilot session file written within 5 minutes", "Copilot session uuid-foreman was "
            "written", env=env)
    state.write_text(json.dumps({**d, "host": "copilot"}))
    refused("a Copilot session whose time is not measured", "not measured",
            env={**env, "COPILOT_HOME": str(w.root / "no-copilot")})
    age_sessions(w)
    refused("on Copilot, a final cost that cannot be priced (no session usage tool)",
            "its final cost cannot be priced", {"host": "copilot"}, env=env)
    state.write_text(base)
    # the Chief of Staff's own session writes all the time and never blocks its own close
    os.utime(main.with_name("uuid-chief.jsonl"), None)


def close_batch(w: World) -> None:
    note("\n## 11b. Closing the batch, on the user's word")
    folder, dropped = w.folder(), w.cr("CR-103")
    name = w.name
    close_refusals(w)
    retro = folder / "retro.md"
    retro_bytes = ("# Retro\n\n## Pause 1\n\n- problem one, long-term fix one\n\n"
                   "## Pause 2\n\n- problem two, long-term fix two\n").encode()
    retro.write_bytes(retro_bytes)
    merged = [c for c in w.batch()["crs"] if c["status"] == "merged" and c.get("path")]
    names = [datetime.strptime(c["merged_at"], "%Y-%m-%dT%H:%M:%SZ").strftime("%y%m%d-%H%M")
             + "-" + Path(c["path"]).name for c in merged]
    last_name = max(names)  # the archive that sorts last: the CR merged last
    code, out = w.chantier("close", "--batch", name)
    check("`close` alone says what would go, names the dropped CR's worktree and branch, and "
          "touches nothing",
          code == 0 and (folder / "batch.json").is_file() and Path(dropped["worktree"]).is_dir()
          and any(folder.name in ln for ln in out) and "--yes" in out[-1]
          and len(list((folder / "3-done").iterdir())) == 4
          and any(dropped["worktree"] in ln and dropped["branch"] in ln for ln in out), str(out))
    retro_lines = [ln for ln in out if ln.startswith("retro:")]
    check("`close` alone prints one `retro:` line naming the archive of the CR merged last, and "
          "the retro stays in 4-batch",
          len(retro_lines) == 1 and f"5-archives/{last_name}/retro.md" in retro_lines[0]
          and retro.read_bytes() == retro_bytes, str(out))
    shown = [float(m[1]) for m in (re.match(r"Total: \$(\d+\.\d\d)", ln) for ln in out) if m]
    check("`close` prints the final cost, with a call made after the last `pause` in it",
          shown and shown[0] > w.paused_total and "Not final" not in "\n".join(out)
          and "To date" not in "\n".join(out), f"{out} (last pause: {w.paused_total})")
    first = w.cr("CR-101")
    stamp = datetime.strptime(first["merged_at"], "%Y-%m-%dT%H:%M:%SZ").strftime("%y%m%d-%H%M")
    collision = w.state / "5-archives" / f"{stamp}-{Path(first['path']).name}"
    collision.mkdir(parents=True)
    (collision / "sentinel.txt").write_text("do not overwrite")
    code, _ = w.chantier("close", "--batch", name, "--yes", expect=3)
    check("an archive collision refuses the close and puts everything back",
          code == 3 and (collision / "sentinel.txt").read_text() == "do not overwrite"
          and (w.state / first["path"] / "03-change-spec.md").is_file()
          and (folder / "batch.json").is_file() and (folder / "events.jsonl").is_file()
          and len(list((folder / "3-done").iterdir())) == 4
          and not (w.state / f".closing-{name}").exists(), w.last_stderr)
    check("the archive collision leaves 4-batch/retro.md in place, byte for byte",
          retro.read_bytes() == retro_bytes)
    shutil.rmtree(collision)
    last_done = w.state / merged[names.index(last_name)]["path"]
    (last_done / "retro.md").write_text("an older retro\n")
    code, _ = w.chantier("close", "--batch", name, "--yes", expect=3)
    check("a retro already in the last CR's folder refuses the close, everything put back and "
          "both files unchanged",
          code == 3 and retro.read_bytes() == retro_bytes
          and (last_done / "retro.md").read_text() == "an older retro\n"
          and (folder / "batch.json").is_file() and len(list((folder / "3-done").iterdir())) == 4
          and not any((a / "retro.md").exists() for a in (w.state / "5-archives").iterdir())
          and not (w.state / f".closing-{name}").exists(), w.last_stderr)
    (last_done / "retro.md").unlink()
    _, out = w.chantier("close", "--batch", name, "--yes")
    check("`close --yes` deletes the batch's own files, keeps the empty state folders, and "
          "repeats what is left to remove",
          sorted(p.name for p in folder.iterdir()) == ["1-pending", "2-actives", "3-done"]
          and not any(list(p.iterdir()) for p in folder.iterdir())
          and Path(dropped["worktree"]).is_dir() and out[0].endswith("4 CRs archived")
          and any(dropped["worktree"] in ln for ln in out), str(out))
    kept = w.state / "5-archives" / last_name / "retro.md"
    others = [a for a in (w.state / "5-archives").glob("*/retro.md") if a != kept]
    retro_lines = [ln for ln in out if ln.startswith("retro:")]
    check("`close --yes` keeps the retro, whole, in the archive of the CR merged last only, and "
          "says where",
          kept.is_file() and kept.read_bytes() == retro_bytes and not others
          and len(retro_lines) == 1 and f"5-archives/{last_name}/retro.md" in retro_lines[0],
          f"{kept} {others} {out}")
    archived = next((w.state / "5-archives").glob("*-101-fix-login-timeout")) / "STATUS.md"
    check("the merged CRs are in 5-archives, named for their merge time, intact",
          re.fullmatch(rf"{stamp}-101-fix-login-timeout", archived.parent.name)
          and len(list((w.state / "5-archives").glob(f"{stamp[:6]}-*-10[1245]-*"))) >= 4
          and (archived.parent / "03-change-spec.md").is_file(), archived.parent.name)
    page = archived.read_text(encoding="utf-8")
    check("at `close` the archived CR page gives its cost as final, priced to then",
          re.search(r"## Cost\s+\$\d+\.\d\d\.\s*$", page) and "so far" not in page
          and "STATUS.md)" not in page.split("## Documents")[0], page)
    # the Chief of Staff removes it on the same word, with git
    w.sh("git", "worktree", "remove", "--force", dropped["worktree"])
    w.sh("git", "branch", "-D", dropped["branch"])
    check("the dropped CR's worktree and branch are gone by the Chief of Staff's hands",
          not Path(dropped["worktree"]).exists()
          and not w.sh("git", "branch", "--list", dropped["branch"]))
    board = (w.state / "STATUS.md").read_text(encoding="utf-8")
    check("the archives and the trash stay, and the board forgets the batch",
          name not in board and "No batch." in board
          and (w.state / dropped["path"] / "STATUS.md").is_file(), board)


def retro_cases(w: World) -> None:
    note("\n## 11c. The batch's retro kept at `close`, with no CR archived, or no retro")
    archives = w.state / "5-archives"
    for label, text in (("a batch of cancelled CRs", "# Retro\n\n## Pause 1\n\n- one, fix one\n"),
                        ("no retro.md", None), ("a whitespace-only retro.md", " \n\t\n")):
        _, item = prepare_cr(w, f"Retro {label}")
        w.reset()
        w.start(str(item), *FROM_AGENTS_MD)
        w.env["CHANTIER_BATCH"] = w.name
        number = int(w.batch()["crs"][0]["id"].removeprefix("CR-"))
        w.chantier("foreman", "set", "local_foreman_retro", "--epoch", 1)
        w.chantier("cancel", w.batch()["crs"][0]["id"], "--epoch", 1)
        w.chantier("pause", "--epoch", 1)
        priced_foreman(w)
        age_sessions(w)
        retro = w.folder() / "retro.md"
        if text is not None:
            retro.write_text(text, encoding="utf-8", newline="")
        before = sorted(p.name for p in archives.iterdir()) if archives.is_dir() else []
        merged_before = json.loads((w.state / "STATUS.json").read_text(encoding="utf-8")).get(
            "merged_total")
        _, out = w.chantier("close", "--batch", w.name)
        lines = [ln for ln in out if ln.startswith("retro:")]
        if text is not None and text.strip():
            check(f"{label}: `close` alone names the batch's retro folder, and touches nothing",
                  len(lines) == 1 and "5-archives/" in lines[0] and w.name in lines[0]
                  and retro.is_file() and len(list(archives.iterdir())) == len(before), str(out))
        else:
            check(f"{label}: `close` prints `retro: no retro`",
                  lines == ["retro: no retro"], str(out))
        _, out = w.chantier("close", "--batch", w.name, "--yes")
        new = [p for p in archives.iterdir() if p.name not in before]
        if text is not None and text.strip():
            check(f"{label}: `close --yes` makes a folder for the batch, holding only retro.md",
                  len(new) == 1 and re.fullmatch(rf"\d{{6}}-\d{{4}}-{w.name}", new[0].name)
                  and [p.name for p in new[0].iterdir()] == ["retro.md"]
                  and (new[0] / "retro.md").read_text(encoding="utf-8") == text
                  and any(ln.startswith("retro: kept in") and new[0].name in ln for ln in out),
                  f"{new} {out}")
            board = json.loads((w.state / "STATUS.json").read_text(encoding="utf-8"))
            check(f"{label}: the board neither counts nor lists the batch's retro folder",
                  board.get("merged_total") == merged_before
                  and not any(new[0].name in str(r.get("path")) for r in board.get("merged", [])),
                  str(board.get("merged_total")))
            w.env.pop("CHANTIER_BATCH", None)
            w.reset()
            _, item2 = prepare_cr(w, f"After {label}")
            w.start(str(item2), *FROM_AGENTS_MD)
            check(f"{label}: the next CR gets the next number",
                  w.batch()["crs"][0]["id"] == f"CR-{number + 1}",
                  f"{w.batch()['crs'][0]['id']} after CR-{number}")
        else:
            check(f"{label}: nothing is created in 5-archives, and the empty file is gone",
                  not new and not retro.exists() and "retro: no retro" in out, f"{new} {out}")
        w.env.pop("CHANTIER_BATCH", None)
    w.reset()


def failed_opening(w: World) -> None:
    note("\n## 17. Openings that fail")
    w.reset()
    _, item = prepare_cr(w, "Latin one specification")
    spec = item / "03-change-spec.md"
    good = spec.read_bytes()
    spec.write_bytes("# Spécification\n".encode("latin-1"))
    code, _ = w.chantier("open", str(item), *FROM_AGENTS_MD, expect=None)
    check("a specification that is not UTF-8 is named, not a traceback",
          code == 2 and "not UTF-8" in w.last_stderr and "Traceback" not in w.last_stderr,
          w.last_stderr)
    spec.write_bytes(good)
    code, _ = w.chantier("open", str(item), str(w.root / 'nowhere'), *FROM_AGENTS_MD,
                         expect=None)
    check("a second item that is not a prepared CR fails the opening, and the first one is "
          "restored where it was",
          code != 0 and (item / "03-change-spec.md").is_file()
          and not list((w.state / "4-batch").glob("batch.json")), w.last_stderr)


def playbook_config(w: World) -> None:
    """chantier.yaml: absent, valid, kept by a running batch, refused with its line, and a host
    that cannot set a model at a start."""
    from chantier.playbook import SETS_MODEL_AT_START
    note("\n## 17b. The playbook: an optional chantier.yaml")
    yaml = w.work / "chantier.yaml"
    earlier = w.env.pop("CHANTIER_BATCH", None)
    yaml.unlink(missing_ok=True)

    def batch_of(*titles: str) -> list[str]:
        w.reset()
        w.start(*(str(prepare_cr(w, t)[1]) for t in titles), *FROM_AGENTS_MD)
        w.env["CHANTIER_BATCH"] = w.name
        w.chantier("foreman", "set", "local_foreman_playbook", "--epoch", 1)
        return [c["id"] for c in w.batch()["crs"]]

    def team(out: list[str]) -> list[str]:
        return [ln for ln in out if ln.startswith("team:")]

    # S1: no chantier.yaml, chantier runs as before
    code, out = w.chantier("playbook")
    check("S1: `playbook` with no chantier.yaml prints the plugin's agents and `(its file's)`",
          code == 0 and out[0].startswith("playbook: no chantier.yaml")
          and "coder: agent=chantier:coder model=(its file's)" in out, str(out))
    check("S1: `playbook` prints the spec-writer's first prompt line with the project's root resolved",
          any(ln.startswith("spec-writer prompt, first line: chantier spec-writer for the Chief of Staff, "
                            "in the project ") and "proj" in ln and ln.endswith(".") for ln in out), str(out))
    want_escalate = "escalate: opus (claude-opus-5-5, Claude Opus 5.5)"
    check("S1: `playbook` ends with the escalation model, and the stack and release drivers "
          "show `model=(its file's)`",
          out[-1] == want_escalate
          and "stack-driver: agent=chantier:stack-driver model=(its file's)" in out
          and "release-driver: agent=chantier:release-driver model=(its file's)" in out, str(out))
    code, cout = w.chantier("playbook", "--host", "copilot")
    check("S1: `playbook` on Copilot ends with `escalate: (none on this host)`",
          code == 0 and cout[-1] == "escalate: (none on this host)", str(cout))
    check("S1: the agents' files of the stack and release drivers name Sonnet 5.5",
          all("model: claude-sonnet-5-5" in (HERE.parent / "agents" / f"{r}.md").read_text(encoding="utf-8")
              for r in ("stack-driver", "release-driver")))
    _, out = w.chantier("preflight")
    check("S1: preflight P12 is ok with no chantier.yaml",
          any(ln.startswith("P12 ok") and "no chantier.yaml" in ln for ln in out), str(out))
    crs = batch_of("Playbook none one", "Playbook none two")
    _, took = w.chantier("take", crs[0], "--epoch", 1)
    _, shown = w.chantier("handoff", crs[1])
    code, out = w.chantier("playbook", "--batch", w.name, "--host", "copilot")
    check("S1: with no chantier.yaml `open` records nothing, `take` and `handoff` print no team "
          "line, and `playbook --batch` prints the plugin's agents, whatever `--host`",
          "playbook" not in w.batch() and not team(took) and not team(shown)
          and code == 0 and out[0].startswith("playbook: no chantier.yaml")
          and "coder: agent=chantier:coder model=(its file's)" in out, str(out))

    # S2: a valid file (with a BOM, as a Windows editor writes it)
    sets_model = SETS_MODEL_AT_START["claude"]
    yaml.write_text("# the team\nroles:\n  coder:\n" + ("    model: opus\n" if sets_model else "")
                    + "    skills: [jira]\n  cr-driver:\n    agent: my-driver  # my own\n",
                    encoding="utf-8-sig")
    coder = ("coder: agent=chantier:coder model=opus (claude-opus-5-5, Claude Opus 5.5) skills=jira"
             if sets_model else "coder: agent=chantier:coder model=(its file's) skills=jira")
    code, out = w.chantier("playbook")
    now_lines = out
    check("S2: `playbook` prints the resolved model with its start value, its exact identifier and "
          "its display name, the skills, and the user's own Driver",
          code == 0 and out[0] == "playbook: chantier.yaml, valid, host claude"
          and coder in out and "cr-driver: agent=my-driver model=(its file's)" in out, str(out))
    crs = batch_of("Playbook set one", "Playbook set two")
    _, took = w.chantier("take", crs[0], "--epoch", 1)
    recorded = w.batch().get("playbook", {})
    want = ("team: coder model=opus (claude-opus-5-5, Claude Opus 5.5) skills=jira" if sets_model
            else "team: coder skills=jira")
    check("S2: `open` records the resolved playbook, `take` prints one team line per role",
          recorded.get("roles", {}).get("cr-driver") == {"agent": "my-driver"}
          and team(took) == [want, "team: cr-driver agent=my-driver"], str(took))
    code, out = w.chantier("playbook", "--batch", w.name)
    check("S2: `playbook` and `playbook --batch` end with the escalation model, with a chantier.yaml",
          now_lines[-1] == want_escalate and out[-1] == want_escalate, str(out))
    check("S2: `playbook --batch` prints the playbook the batch recorded",
          code == 0 and out[1:] == [l for l in now_lines[1:] if not l.startswith("spec-writer prompt")]
          and "opened it" in out[0], str(out))

    # S3: a running batch keeps the playbook it opened with
    yaml.write_text("roles:\n  coder:\n    agent: other-coder\n", encoding="utf-8")
    _, took = w.chantier("take", crs[1], "--epoch", 1)
    code, out = w.chantier("playbook", "--batch", w.name)
    check("S3: after chantier.yaml changed, `take` of another CR and `playbook --batch` still "
          "print the opening's",
          "other-coder" not in "".join(took + out) and "agent=my-driver" in "".join(team(took))
          and out[1:] == [l for l in now_lines[1:] if not l.startswith("spec-writer prompt")], str(out))

    # S4: refusals, each exit 2 with its line, `open` moving nothing
    w.reset()
    _, item = prepare_cr(w, "Playbook refused")
    head = "roles:\n  coder:\n"
    PRICES = "prices:\n  mystery-model:\n"
    four = "".join(f"    {k}: 1\n" for k in ("input", "cache_write_5m", "cache_write_1h", "cache_read"))
    five = four + "    output: 1\n"
    refusals = [
        ("an unknown role", "roles:\n  codr:\n    agent: x\n", 2, "is not one of the plugin's agents"),
        ("an unknown key", head + "    colour: red\n", 3, 'unknown key "colour"'),
        ("an empty role", head, 2, "is empty"),
        ("a tab", head + "\tagent: x\n", 3, "a tab"),
        ("an anchor", head + "    agent: &a x\n", 3, "anchors"),
        ("a duplicate key", head + "    agent: x\n    agent: y\n", 4, "duplicate key"),
        ("a flow mapping", head + "    agent: {a: b}\n", 3, "flow mappings"),
        ("a second document", "roles:\n  coder:\n    agent: x\n---\n", 4, "several documents"),
        ("an unknown model", head + "    model: opus 5.6\n", 3, "is unknown on Claude Code; known:"),
        ("a model with no letter", head + "    model: 5.5\n", 3, "name the model, not only its version"),
        ("a price missing", PRICES + four, 2, "missing output"),
        ("a price that is not a number", PRICES + four + "    output: cheap\n", 7, '"output" is a number'),
        ("a negative price", PRICES + four + "    output: -1\n", 7, '"output" is a number, not negative'),
        ("an unknown key under a price entry", PRICES + five + "    colour: red\n", 8, 'unknown key "colour"'),
        ("a long_context without above", PRICES + five + "    long_context:\n"
         + "".join(f"      {k}: 1\n" for k in ("input", "cache_write_5m", "cache_write_1h",
                                                   "cache_read", "output")), 8, "missing above"),
    ]
    for label, text, line, why in refusals:
        yaml.write_text(text, encoding="utf-8")
        code, _ = w.chantier("open", str(item), *FROM_AGENTS_MD, expect=None)
        check(f"S4: {label} is refused by `open` at its line, and nothing moved",
              code == 2 and f"chantier.yaml:{line}:" in w.last_stderr and why in w.last_stderr
              and (item / "03-change-spec.md").is_file()
              and not list((w.state / "4-batch").glob("batch.json")), w.last_stderr)
    yaml.write_text(refusals[0][1], encoding="utf-8")
    code, out = w.chantier("playbook", expect=None)
    _, pre = w.chantier("preflight", expect=2)
    check("S4: `playbook` exits 2 with the problem and its line, and preflight P12 fails",
          code == 2 and any(ln.startswith("chantier.yaml:2:") for ln in out)
          and any(ln.startswith("P12 FAIL chantier.yaml:2:") for ln in pre) and pre[-1].endswith("start nothing"),
          str(out + pre))
    yaml.write_text(head + "    model: gpt\n", encoding="utf-8")
    code, out = w.chantier("playbook", "--host", "copilot", expect=None)
    check("S4: a name that fits several models is refused as ambiguous, listing them",
          code == 2 and "ambiguous" in "".join(out) and "Luna" in "".join(out) and "Sol" in "".join(out),
          str(out))

    # S5: a host that cannot set a model at a start refuses clearly
    yaml.write_text(head + "    model: opus\n", encoding="utf-8")
    code, out = w.chantier("playbook", "--host", "copilot", expect=None)
    check("S5: a `model` on a host that cannot set one at a start is refused, naming the reference",
          code == 2 and any("cannot set a model when it starts an agent" in ln
                            and 'hosts/copilot.md, "Models"' in ln for ln in out), str(out))

    # S6: no chantier.yaml again
    yaml.unlink()
    batch_of("Playbook none again")
    check("S6: with no chantier.yaml again, `open` of the next batch records nothing",
          "playbook" not in w.batch())
    w.env.pop("CHANTIER_BATCH", None)
    if earlier:
        w.env["CHANTIER_BATCH"] = earlier


def lock_names(w: World, what: str) -> bool:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            with open(w.state / ".long-gate.lock", encoding="utf-8") as f:  # byte 0 is locked
                f.seek(1)
                if what in f.read():
                    return True
        except OSError:
            pass
        time.sleep(0.05)
    return False


def cancel_during_gate(w: World) -> None:
    note("\n## 18. A cancel during a gate")
    _, item = prepare_cr(w, "Stopped mid gate")
    slow = w.root / "slow_gate.py"
    slow.write_text("import time\ntime.sleep(60)\n")
    gate = f"uv run --no-project python {slow.as_posix()}"
    w.reset()
    w.start(str(item), "--default-branch", "main")
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman6", "--epoch", 1)
    Foreman(w, epoch=1).turn()
    cr = w.batch()["crs"][0]["id"]
    running = subprocess.Popen([sys.executable, "-m", "chantier", "gate", cr, gate], cwd=w.work,
                               env=w.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8")
    lock_names(w, f"{cr} pid")
    lock_names(w, " pg")
    w.chantier("cancel", cr, "--epoch", 1)
    out, err = running.communicate(timeout=30)
    check("a cancel stops the suite and moves the CR while its gate runs; the gate ends cleanly",
          "6-trash/" in w.cr(cr)["path"] and out.startswith("FAIL") and "Traceback" not in err
          and "pg" in w.last_out[0], f"{out} {err} {w.last_out}")


def stop_own_gate(w: World) -> None:
    note("\n## 18b. A Driver stops its own long gate; `cancel` needs the epoch")
    sys.path.insert(0, str(SKILL / "scripts" / "cli" / "src"))
    from chantier import procs
    from chantier.commands import gate_passed
    items = [prepare_cr(w, t)[1] for t in ("Stop own gate", "Stop other gate")]
    slow = w.root / "slow_stop.py"
    pidfile = w.root / "slow_stop.pid"
    slow.write_text(f"import os, time\nopen({pidfile.as_posix()!r}, 'w').write(str(os.getpid()))\n"
                    "time.sleep(60)\n")
    slow_gate = f'"{sys.executable}" "{slow}"'
    w.reset()
    w.start(*map(str, items), "--slots", 2, "--default-branch", "main")
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman18b", "--epoch", 1)
    Foreman(w, epoch=1).turn()
    one, two = (c["id"] for c in w.batch()["crs"])
    wt = Path(w.cr(one)["worktree"])

    def events(cr):
        return [json.loads(ln) for ln in (w.folder() / "events.jsonl").read_text("utf-8").splitlines()
                if json.loads(ln)["kind"] == "gate" and json.loads(ln)["cr"] == cr]

    def logs(cr):
        return sorted((w.at(w.cr(cr)["path"]) / "work" / "gates").glob("*.log"))

    def background(cr):
        p = subprocess.Popen([sys.executable, "-m", "chantier", "gate", cr, slow_gate], cwd=w.work,
                             env=w.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             encoding="utf-8")
        lock_names(w, f"{cr} pid")
        lock_names(w, " pg")
        return p

    head = w.sh("git", "rev-parse", "HEAD", cwd=wt)
    notes_before = len(w.cr(one).get("notes", []))
    running = background(one)
    code, _ = w.chantier("gate", one, "--stop", expect=None)
    stop_out = w.last_out
    out, err = running.communicate(timeout=30)
    time.sleep(0.5)
    gone = not procs.alive(int(pidfile.read_text()))
    check("`gate <cr> --stop` exits 0 and names the group; the stopped gate says STOPPED, exits 4, "
          "with no traceback; the slow suite is gone",
          code == 0 and any("(pg" in ln for ln in stop_out) and out.startswith("STOPPED")
          and running.returncode == 4 and "Traceback" not in err and gone,
          f"{stop_out} {out} {err} {running.returncode}")
    last = events(one)[-1]
    check("the stop changes nothing else: the CR still works in its folder with its worktree and "
          "no new note; its last gate event is `stopped` at the run's head; the log ends `result: "
          "stopped`",
          w.cr(one)["status"] == "working" and "4-batch/2-actives/" in w.cr(one)["path"].replace(
              "\\", "/") and wt.is_dir() and len(w.cr(one).get("notes", [])) == notes_before
          and last["result"] == "stopped" and last["head"] == head
          and logs(one)[-1].read_text("utf-8").splitlines()[-1].startswith("result: stopped"),
          f"{w.cr(one)} {last}")
    marker = w.root / "second_ran"
    second = f'"{sys.executable}" -c "open({marker.as_posix()!r}, \'w\').close()"'
    n_before = len(events(one))
    p = subprocess.Popen([sys.executable, "-m", "chantier", "gate", one, slow_gate, second],
                         cwd=w.work, env=w.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, encoding="utf-8")
    lock_names(w, " pg")
    w.chantier("gate", one, "--stop")
    out, err = p.communicate(timeout=30)
    new = events(one)[n_before:]
    check("a stop while the first of two commands runs: the second never starts, the gate exits 4 "
          "and records `stopped` with no `fail` event",
          p.returncode == 4 and out.startswith("STOPPED") and not marker.exists()
          and [e["result"] for e in new] == ["stopped"] and "Traceback" not in err,
          f"{out} {err} {p.returncode} {new}")
    w.chantier("gate", one, GATE)
    check("the lock is free: a second gate runs at once, with no waiting line, and passes",
          "waiting for the long gate" not in logs(one)[-1].read_text("utf-8")
          and gate_passed(events(one), head))
    running = background(one)
    w.chantier("gate", one, "--stop")
    running.communicate(timeout=30)
    _, out = w.chantier("ship", one, "https://example.invalid/pr/0")
    check("a stopped run voids an earlier pass at the same head: `ship` says no long gate passed",
          not gate_passed(events(one), head) and any("no long gate passed" in ln for ln in out),
          str(out))
    code, out = w.chantier("gate", one, "--stop")
    check("`gate <cr> --stop` with no gate running exits 0 and says there is nothing to stop",
          code == 0 and any("nothing to stop" in ln for ln in out), str(out))
    other = background(two)
    code, _ = w.chantier("gate", one, "--stop", expect=2)
    check("with another CR's gate holding the lock, `--stop` exits 2, names it and stops nothing",
          code == 2 and two in w.last_stderr + "".join(w.last_out) and other.poll() is None,
          f"{w.last_out} {w.last_stderr}")
    w.chantier("gate", two, "--stop")
    other.communicate(timeout=30)
    code, _ = w.chantier("gate", one, "--stop", GATE, expect=1)
    code2, _ = w.chantier("gate", one, expect=1)
    check("`--stop` with a command, and `gate` with neither command nor `--stop`, exit 1",
          code == 1 and code2 == 1)
    before = (w.cr(one)["status"], w.cr(one)["path"])
    code, _ = w.chantier("cancel", one, expect=2)
    check("`cancel` with no `--epoch` exits 2, names `gate <cr> --stop`, and changes nothing",
          code == 2 and f"gate {one} --stop" in w.last_stderr
          and (w.cr(one)["status"], w.cr(one)["path"]) == before, w.last_stderr)


def rails(w: World) -> None:
    note("\n## 19. The rails: rounds, slots 0, the budget, the long gate")
    _, a = prepare_cr(w, "Rail one")
    _, b = prepare_cr(w, "Rail two")
    slow = w.root / "slow_long.py"
    slow.write_text("import time\ntime.sleep(2)\n")
    long_gate = f'"{sys.executable}" "{slow}"'
    w.reset()
    w.start(str(a), str(b), "--slots", 1, "--budget", 1, "--default-branch", "main")
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman7", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    fm.turn()
    one, two = (c["id"] for c in w.batch()["crs"])
    check("one slot: one Driver", fm.started == [one])
    w.chantier("round", one)
    logged = lambda cr: [e for e in (json.loads(ln) for ln in (w.folder() / "events.jsonl")  # noqa: E731
                                     .read_text("utf-8").splitlines())
                         if e["kind"] == "round" and e["cr"] == cr]
    code, _ = w.chantier("round", one, expect=2)
    check("a second `round` with nothing since is refused (exit 2): the count unchanged, no "
          "`round` event, the message names what to do",
          code == 2 and "nothing happened since" in w.last_stderr and "handoff" in w.last_stderr
          and w.cr(one)["round"] == 1 and len(logged(one)) == 1, w.last_stderr)
    for i in range(2):
        w.chantier("note", one, f"round {i + 1} done")
        w.chantier("round", one)
    check("after a `note` the next `round` passes", w.cr(one)["round"] == 3 and len(logged(one)) == 3)
    code, _ = w.chantier("round", one, expect=5)
    check("the fourth round is refused: the round limit is a rail (exit 5)",
          code == 5 and "round limit" in w.last_stderr and w.cr(one)["round"] == 3, w.last_stderr)
    _, out = w.chantier("status")
    check("status shows the rounds against the limit",
          any(ln.startswith(f"{one} working r3/3") for ln in out), str(out))
    w.chantier("order", "rounds", one, "--note", "4")
    fm.turn()  # the Driver is live: the Foreman tells it, the order is done
    w.chantier("note", one, "the limit was raised")
    code, _ = w.chantier("round", one)
    check("more rounds granted by the user open the next one", code == 0
          and w.cr(one)["round"] == 4 and w.cr(one)["rounds"] == 4)
    w.chantier("order", "slots", "--note", "0")
    commit(w, one, "rail.py", "RAIL = 1\n")
    _, out = w.chantier("ship", one, "https://example.invalid/pr/0")
    check("`ship` reports a head not pushed and no long gate passed at it",
          any("is not pushed" in ln for ln in out) and any("no long gate passed" in ln for ln in out),
          str(out))
    ship(w, one, "feat: rail")
    _, out = w.ready(one, w.cr(one)["pr"])
    check("the hand-back stands: CI is the Driver's judgement, not the CLI's",
          w.cr(one)["status"] == "ready", str(out))
    code, _ = w.chantier("take", two, expect=2)
    check("slots 0 holds: no Driver starts", code == 2 and "no free slot" in w.last_stderr)
    code, _ = w.chantier("order", "slots", "--note", "none", expect=1)
    check("the `order slots` usage line says \"0 holds\"", "0 holds" in w.last_stderr,
          w.last_stderr)
    code, _ = w.chantier("land", "--epoch", 1, expect=None)
    check("`land` is no longer a command: usage error, nothing changed",
          code in (1, 2) and "invalid choice" in w.last_stderr and w.batch()["status"] == "running",
          w.last_stderr)
    w.chantier("order", "slots", "--note", "1")
    state = w.folder() / "batch.json"
    data = w.batch()
    state.write_text(json.dumps({**data, "spent_usd": 2}))
    code, _ = w.chantier("take", two, expect=5)
    check("past the budget, no Driver starts (exit 5)", code == 5 and "budget" in w.last_stderr)
    fm.turn()
    check("the Foreman asks the Chief of Staff for budget",
          fm.asked[-1].startswith("budget ") and w.cr(two)["status"] == "queued", str(fm.asked))
    w.chantier("order", "budget", "--note", "10")
    fm.turn()
    check("a wider budget lets the next Driver start", fm.started[-1] == two)
    _, out = w.chantier("handoff", one)
    check("`handoff` gives a fresh agent the CR on one screen",
          out[0].startswith(f'{one} "Rail one" (change) ready') and any("rounds: 4 of 4" in ln
                                                                        for ln in out)
          and any(ln.startswith("PR: ") for ln in out), str(out))
    code, _ = w.chantier("take", one, expect=2)
    check("a ready CR goes back to a Driver only with a note saying why",
          code == 2 and "only with `--note`" in w.last_stderr, w.last_stderr)
    w.chantier("order", "slots", "--note", "2")
    w.chantier("agents", "set", one, "-")
    code, _ = w.chantier("take", one, "--note", "rebase: main moved; the PR no longer merges")
    check("with the note, the Foreman's round on a ready CR starts",
          code == 0 and w.cr(one)["status"] == "working"
          and w.cr(one)["notes"][-1].startswith("back to a Driver: rebase:"))

    def held_gate(cr):
        return subprocess.Popen([sys.executable, "-m", "chantier", "gate", cr, long_gate],
                                cwd=w.work, env=w.env, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, encoding="utf-8")

    held = held_gate(one)
    lock_names(w, f"{one} pid")
    started = time.monotonic()
    code, out = w.chantier("gate", two, long_gate)
    waited = time.monotonic() - started
    held.communicate(timeout=30)
    log = max((w.state / w.cr(two)["path"] / "work" / "gates").glob("*.log"))
    check("a second long gate waits for the first (one long gate at a time)",
          code == 0 and waited >= 1 and "waiting for the long gate of" in log.read_text("utf-8"),
          f"{waited:.1f}s {out}")
    held = held_gate(one)
    lock_names(w, " pg")
    held.kill()  # the command dies; its suite runs on in its own process group
    held.communicate(timeout=30)
    started = time.monotonic()
    code, out = w.chantier("gate", two, long_gate)
    waited = time.monotonic() - started
    log = max((w.state / w.cr(two)["path"] / "work" / "gates").glob("*.log"))
    check("a long gate whose command died still holds the next one while its suite runs",
          code == 0 and waited >= 1 and "its command still runs" in log.read_text("utf-8"),
          f"{waited:.1f}s {out}")


def driver_liveness(w: World) -> None:
    note("\n## 12c. A Driver that dies: activity lines, the restart path, the `context:` hand-back")
    items = [prepare_cr(w, t)[1] for t in ("Live one", "Live two", "Live three")]
    w.reset()
    w.start(*(str(p) for p in items), "--slots", 3, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "uuid-live", "--epoch", 1)
    w.chantier("foreman", "transcript", "uuid-live", "--epoch", 1)
    one, two, three = (c["id"] for c in w.batch()["crs"])
    for cr in (one, two, three):
        w.chantier("take", cr, "--epoch", 1)
        w.chantier("agents", "set", cr, f"agent-{cr}", "--epoch", 1)
        start_driver(w, cr)
    slug = "".join(ch if ch.isalnum() else "-" for ch in str(w.work.resolve()))
    chief = w.root / "claude-projects" / slug / "uuid-live.jsonl"
    chief.parent.mkdir(parents=True, exist_ok=True)
    chief.write_text(json.dumps({"type": "assistant", "timestamp": datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"), "message": {"id": "l1", "model": "claude-sonnet-5-5", "usage": {
            "input_tokens": 10, "output_tokens": 100, "cache_read_input_tokens": 0}}}) + "\n")
    sub = chief.with_suffix("") / "subagents"  # a Driver of the first CR and its worker
    sub.mkdir(parents=True, exist_ok=True)
    (sub / f"agent-agent-{one}.jsonl").write_text("{}\n")
    (sub / "agent-w1.jsonl").write_text("{}\n")
    (sub / "agent-w1.meta.json").write_text(json.dumps({"parentAgentId": f"agent-{one}"}))
    (w.state / ".long-gate.lock").write_bytes(b"\0" + f"{three} pid 1 pg1".encode())
    code, out = w.chantier("status", "--refresh", "--epoch", 1, expect=None)
    lines = {ln.split()[1]: ln for ln in out if ln.startswith("activity ")}
    check("`status --refresh` gives one activity age per working CR, and no longest silent Driver",
          code == 0 and set(lines) == {one, two, three}
          and re.fullmatch(rf"activity {one} \d+ min", lines[one])
          and lines[two] == f"activity {two} not measured"
          and lines[three] == f"activity {three} gate running"
          and not any("longest silent" in ln for ln in out), str(out))
    w.chantier("agents", "set", one, "-", "--epoch", 1)
    _, out = w.chantier("note", one, "no Driver recorded")
    check("`note` prints `context: not measured (no agent recorded)` with no agent recorded",
          out == ["ok", "context: not measured (no agent recorded)"], str(out))
    w.chantier("agents", "set", one, f"agent-{one}", "--epoch", 1)
    _, out = w.chantier("note", one, "agent without a record")
    check("`note` says so when the recorded agent's transcript is missing",
          out[1].startswith("context: not measured (no transcript found"), str(out))

    def usage_line(mid, inp, write, read):
        return json.dumps({"type": "assistant", "message": {"id": mid, "model": "claude-sonnet-5-5",
                           "usage": {"input_tokens": inp, "output_tokens": 5,
                                     "cache_creation": {"ephemeral_5m_input_tokens": write,
                                                        "ephemeral_1h_input_tokens": 30},
                                     "cache_read_input_tokens": read}}})
    (sub / f"agent-agent-{one}.jsonl").write_text(
        usage_line("d1", 100, 0, 8870) + "\n"
        + json.dumps({"type": "system", "subtype": "compact_boundary"}) + "\n"
        + usage_line("d2", 10, 200, 4000) + "\n" + json.dumps({"type": "user"}) + "\n",
        encoding="utf-8")
    _, out = w.chantier("note", one, "context measured")
    check("`note` prints the last call's prompt size: input, cache writes and cache reads of "
          "the recorded agent's transcript",
          out == ["ok", f"context: 4240 tokens (agent agent-{one})"], str(out))
    _, out = w.chantier("cost", "--by", "cr", expect=None)
    line = next((ln for ln in out if ln.startswith(f"{one}:")), "")
    check("`cost --by cr` shows the Driver's peak context and compactions on the CR's line",
          "Driver peak context 9,000 tokens, 1 compaction)" in line, str(out))
    (w.state / ".long-gate.lock").unlink()
    chief.unlink()
    shutil.rmtree(sub)
    code, out = w.chantier("status", "--refresh", "--epoch", 1, expect=None)
    check("with no readable session record the line says not measured, and the exit code is the "
          "spend's own", code == 4 and f"activity {one} not measured" in out
          and any(ln.startswith("spend not updated") for ln in out), str(out))
    code, _ = w.chantier("take", one, expect=2)
    check("`take` of a working CR without a note is refused (exit 2)", code == 2, w.last_stderr)
    code, _ = w.chantier("take", one, "--note", "resume: x", expect=2)
    check("`take` of a CR with an agent recorded is refused, naming `agents set <cr> -`",
          code == 2 and f"agents set {one} -" in w.last_stderr, w.last_stderr)
    rounds = w.cr(one)["round"]
    w.chantier("agents", "set", one, "-")
    _, out = w.chantier("status")
    check("status flags a working CR with no Driver recorded",
          any(ln.startswith(f"{one} working") and "no Driver recorded" in ln for ln in out), str(out))
    code, out = w.chantier("take", one, "--note", "resume: x")
    _, facts = w.chantier("handoff", one)
    kinds = [json.loads(ln) for ln in (w.folder() / "events.jsonl").read_text("utf-8").splitlines()]
    check("after `agents set <cr> -` the restart is accepted: same slots held, no round counted, "
          "the note in the facts, the take logged as a restart",
          code == 0 and "(3 of 3 slots held)" in out[0] and w.cr(one)["round"] == rounds
          and w.cr(one)["notes"][-1] == "back to a Driver: resume: x"
          and any("resume: x" in ln for ln in facts)
          and [e for e in kinds if e["kind"] == "take" and e["cr"] == one][-1].get("restart") is True,
          str(out))
    w.chantier("agents", "set", one, f"agent-{one}-2")
    data = w.batch()
    (w.folder() / "batch.json").write_text(json.dumps({**data, "budget_usd": 1, "spent_usd": 2}))
    w.chantier("agents", "set", one, "-")
    code, _ = w.chantier("take", one, "--note", "resume: x", expect=5)
    check("a restart past the budget is refused (exit 5)", code == 5, w.last_stderr)
    (w.folder() / "batch.json").write_text(json.dumps(data))
    code, out = w.chantier("handback", two, "blocked", "context: stopped at the tests, run them next")
    check("`handback blocked context:` leaves the CR blocked and prints the restart line, not the "
          "ask line", code == 0 and w.cr(two)["status"] == "blocked"
          and w.cr(two)["blocked_reason"].startswith("context:")
          and any("restarts a fresh Driver" in ln for ln in out)
          and not any("asks the Chief of Staff" in ln for ln in out), str(out))
    rounds = w.cr(two)["round"]
    w.chantier("agents", "set", two, "-")
    code, _ = w.chantier("take", two, "--note", "resume: context")
    check("a fresh Driver takes it back with the note, the round unchanged",
          code == 0 and w.cr(two)["status"] == "working" and w.cr(two)["round"] == rounds,
          w.last_stderr)
    cards = HERE.parent / "skills" / "chantier" / "references"
    foreman = (cards / "foreman.md").read_text(encoding="utf-8")
    driver = (cards / "driver.md").read_text(encoding="utf-8")
    check("foreman.md names the suspect rule, the two proofs of death, the new-epoch rule, the "
          "`context:` case and what counts toward `ended twice`; driver.md lists `context:`",
          all(s in foreman for s in ("**Suspect:**", "**Proof of death**", "new Foreman epoch",
                                     "blocked context: …", "driver ended twice", "do not."))
          and "`context: <where it stopped" in driver)


def handback_proofs(w: World) -> None:
    note("\n## 12b. Handback ready needs two proofs at the PR's head: a long gate and a verdict")
    _, item = prepare_cr(w, "Proof one")
    w.reset()
    w.start(str(item), "--slots", 1, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman8", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    fm.turn()
    cr = w.batch()["crs"][0]["id"]
    num = cr.removeprefix("CR-")
    folder = w.at(w.cr(cr)["path"])

    def log_events(kind):
        return [json.loads(ln) for ln in (w.folder() / "events.jsonl").read_text("utf-8").splitlines()
                if json.loads(ln)["kind"] == kind and json.loads(ln)["cr"] == cr]

    commit(w, cr, "proof.py", "PROOF = 1\n")
    ship(w, cr, "feat: proof")
    link = w.cr(cr)["pr"]
    code, _ = w.chantier("handback", cr, "ready", link, expect=2)
    check("`handback ready` with no long gate passed is refused, naming the long gate",
          code == 2 and "no long gate passed" in w.last_stderr, w.last_stderr)
    gate_two = f"\"{sys.executable}\" -c \"print(1)\""
    code, out = w.chantier("gate", num, GATE, gate_two)
    runs = {e.get("run") for e in log_events("gate")}
    check("a two-command gate passes: one pass line each, one run id, and `gate` takes a bare number",
          code == 0 and out[0].startswith(f"pass {GATE} at ") and out[1].startswith("pass ")
          and out[2].startswith("log ") and len(runs) == 1 and None not in runs, str(out))
    code, _ = w.chantier("handback", cr, "ready", link, expect=2)
    check("`handback ready` with the gate but no verdict is refused, naming the verdict",
          code == 2 and "no verdict VERIFIED" in w.last_stderr
          and "no long gate passed" not in w.last_stderr, w.last_stderr)
    w.chantier("verdict", num, "VERIFIED")
    w.chantier("verdict", cr, "NOT VERIFIED")
    code, _ = w.chantier("handback", cr, "ready", link, expect=2)
    check("a VERIFIED then a NOT VERIFIED at the same head refuses: the last verdict decides",
          code == 2 and "NOT VERIFIED" in w.last_stderr, w.last_stderr)
    code, _ = w.chantier("verdict", cr, "maybe", expect=1)
    check("a verdict is VERIFIED or NOT VERIFIED, nothing else", code == 1, w.last_stderr)
    w.chantier("verdict", cr, "VERIFIED")
    check("a later VERIFIED at the head lets the last verdict through",
          [e["result"] for e in log_events("verdict")][-1] == "VERIFIED"
          and len(log_events("verdict")) == 3)
    # a new commit, shipped: the gate and the verdict above are of the old head
    commit(w, cr, "proof2.py", "PROOF = 2\n")
    ship(w, cr, "feat: proof")
    code, _ = w.chantier("handback", cr, "ready", link, expect=2)
    check("a verdict and a gate made before a new commit do not count at the new head",
          code == 2 and "no long gate passed" in w.last_stderr
          and "no verdict VERIFIED" in w.last_stderr, w.last_stderr)
    code, _ = w.chantier("handback", cr, "ready", link, "--no-gate", "", expect=1)
    check("`--no-gate` with an empty reason is a usage error", code == 1, w.last_stderr)
    rule = "AGENTS.md declares no long gate for this change"
    code, _ = w.chantier("handback", cr, "ready", link, "--no-gate", rule, expect=2)
    check("`--no-gate` with no verdict at the head is refused", code == 2
          and "no verdict VERIFIED" in w.last_stderr and "no long gate" not in w.last_stderr,
          w.last_stderr)
    # the gate that fails on its second command stops there and logs no pass for it
    bad = f"\"{sys.executable}\" -c \"import sys; sys.exit(3)\""
    never = f"\"{sys.executable}\" -c \"print(2)\""
    code, out = w.chantier("gate", cr, GATE, bad, never, expect=4)
    gates = log_events("gate")
    check("a gate whose second command fails stops there and logs no pass for it (exit 4)",
          code == 4 and out[1].startswith("FAIL ") and not any("print(2)" in ln for ln in out[:2])
          and [e["result"] for e in gates[-2:]] == ["pass", "fail"]
          and not any(e["command"] == never for e in gates), str(out))
    code, _ = w.chantier("handback", cr, "ready", link, expect=2)
    check("a gate that failed leaves no gate passed at the head", code == 2
          and "no long gate passed" in w.last_stderr, w.last_stderr)
    w.chantier("verdict", cr, "VERIFIED")
    _, out = w.chantier("handback", f"cr-{num}", "ready", link, "--no-gate", rule)
    check("`--no-gate <rule>` with a verdict is accepted: the reason is on the printed line, in "
          "the event and in STATUS.md",
          w.cr(cr)["status"] == "ready" and rule in out[0]
          and log_events("handback")[-1].get("no_gate") == rule
          and any("Long gate" in ln and rule in ln for ln in (folder / "STATUS.md").read_text(
              "utf-8").splitlines()), str(out))
    w.chantier("order", "slots", "--note", "2")
    fm.take(cr, "recheck the gates")
    facts = fm.facts
    check("`take` prints the two-gate checklist, marks following the events",
          any(ln.startswith("gates before handback ready") for ln in facts)
          and any(ln.startswith("  [ ] long gate") for ln in facts)
          and any(ln.startswith("  [x] verdict") for ln in facts), str(facts))
    w.chantier("gate", cr, GATE)
    _, out = w.chantier("handoff", cr)
    check("`handoff` prints the checklist too, with the gate now marked",
          any(ln.startswith("  [x] long gate") for ln in out)
          and any(ln.startswith("  [x] verdict") for ln in out), str(out))
    _, out = w.chantier("handback", num, "ready", link)
    check("after a passed gate and `verdict VERIFIED` at the head, `handback ready` is accepted",
          w.cr(cr)["status"] == "ready" and out[0].startswith(f"[driver {cr}"), str(out))
    code, out = w.chantier("ship", num, link)
    check("`ship`, `gate`, `handback` and `verdict` all resolve a bare number, or `cr-<n>`, to "
          f"{cr}", code == 0 and out[0].startswith("recorded "), str(out))

    # a ready CR goes back to its Driver by `take --note`, and hands back again
    handbacks = len(log_events("handback"))
    code, _ = w.chantier("handback", cr, "ready", link, expect=2)
    check("`handback ready` on a ready CR is refused with the `take` that reopens it",
          code == 2 and "is ready" in w.last_stderr and f"take {cr} --note" in w.last_stderr
          and "then hand back again" in w.last_stderr and w.cr(cr)["status"] == "ready"
          and len(log_events("handback")) == handbacks, w.last_stderr)
    _, out = w.chantier("order", "note", cr, "--note", "rebase: main moved")
    check("`order note` on a ready CR names the `take`",
          any(f"take {cr} --note" in ln for ln in out), str(out))
    before = w.cr(cr)["round"]
    w.chantier("agents", "set", cr, "-")  # `take` wants the recorded agent cleared first
    w.chantier("take", cr, "--epoch", 1, "--note", "rebase: main moved")
    _, out = w.chantier("log", cr)
    check("`take --note` reopens a ready CR to working: no round, the note and "
          "the `take` event say why",
          w.cr(cr)["status"] == "working" and w.cr(cr)["round"] == before
          and w.cr(cr)["notes"][-1].startswith("back to a Driver: rebase:")
          and any(" take " in ln and "note=rebase: main moved" in ln for ln in out), str(out))
    commit(w, cr, "rebased.py", "REBASED = 1\n")
    for extra in ([], ["--no-gate", rule]):
        code, _ = w.chantier("handback", cr, "ready", link, *extra, expect=2)
        check("after a commit with no `ship`, `handback ready` names the head `ship` recorded, "
              "alone" + (", with `--no-gate`" if extra else ""),
              code == 2 and "is not the head ship recorded" in w.last_stderr
              and f"ship {cr}" in w.last_stderr and "no long gate passed" not in w.last_stderr
              and "no verdict VERIFIED" not in w.last_stderr, w.last_stderr)
    ship(w, cr, "feat: rebased")
    code, _ = w.chantier("handback", cr, "ready", link, expect=2)
    check("after `ship`, the gate and the verdict are wanted at the new head",
          code == 2 and "no long gate passed" in w.last_stderr
          and "no verdict VERIFIED" in w.last_stderr, w.last_stderr)
    w.chantier("gate", cr, GATE)
    w.chantier("verdict", cr, "VERIFIED")
    w.chantier("handback", cr, "ready", link)
    check("with `ship`, the gate and a verdict at the new head, the CR hands back ready again, "
          "in the same round", w.cr(cr)["status"] == "ready" and w.cr(cr)["round"] == before)
    w.chantier("agents", "set", cr, "-")
    w.chantier("take", cr, "--epoch", 1, "--note", "answer: go")
    w.chantier("handback", cr, "blocked", "question: x")
    code, _ = w.chantier("handback", cr, "blocked", "question: y", expect=2)
    check("a second hand-back on a blocked CR is refused with the `take` that reopens it",
          code == 2 and "is blocked" in w.last_stderr and f"take {cr} --note" in w.last_stderr,
          w.last_stderr)


def gate_proof(w: World) -> None:
    note("\n## 12c. The gate binds to a commit; the budget bounds the rounds")
    sys.path.insert(0, str(SKILL / "scripts" / "cli" / "src"))
    from chantier.commands import gate_passed
    items = [prepare_cr(w, t)[1] for t in ("Gate head", "Gate abbrev", "Gate short", "Gate budget",
                                           "Gate rounds", "Gate free")]
    w.reset()
    w.start(*map(str, items), "--slots", 6, "--budget", 1, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman9", "--epoch", 1)
    Foreman(w, epoch=1).turn()
    a, b, c, d, e, f = (x["id"] for x in w.batch()["crs"])

    def wt(cr):
        return Path(w.cr(cr)["worktree"])

    def head(cr):
        return w.sh("git", "rev-parse", "HEAD", cwd=wt(cr))

    def events(kind, cr):
        return [json.loads(ln) for ln in (w.folder() / "events.jsonl").read_text("utf-8").splitlines()
                if json.loads(ln)["kind"] == kind and json.loads(ln)["cr"] == cr]

    def last_log(cr):
        return max((w.at(w.cr(cr)["path"]) / "work" / "gates").glob("*.log")).read_text(
            "utf-8").splitlines()

    commit(w, a, "g1.py", "G = 1\n")
    w.chantier("gate", a, GATE)
    lines, sha = last_log(a), head(a)
    check("the gate log's first line holds the CR and the 40-character HEAD, and the event the "
          "same SHA; its last line gives the result",
          lines[0].startswith(f"gate {a} branch ") and lines[0].split()[-1] == sha
          and len(sha) == 40 and events("gate", a)[-1]["head"] == sha
          and lines[-1].startswith("result: pass"), str(lines))
    # a dirty tree: nothing runs
    before = len(events("gate", a))
    (wt(a) / "g1.py").write_text("G = 100\n")
    code, _ = w.chantier("gate", a, GATE, expect=2)
    tracked = code == 2 and "commit first" in w.last_stderr
    (wt(a) / "g1.py").write_text("G = 1\n")
    (wt(a) / "loose.txt").write_text("untracked\n")
    code, _ = w.chantier("gate", a, GATE, expect=2)
    (wt(a) / "loose.txt").unlink()
    check("`gate` on a worktree with a modified or an untracked file exits 2 and runs nothing",
          tracked and code == 2 and len(events("gate", a)) == before, w.last_stderr)
    # a gate command that commits: no pass at either head
    code, out = w.chantier("gate", a, "git commit --allow-empty --quiet -m moved", expect=4)
    new = head(a)
    evs = events("gate", a)
    check("a gate command that commits leaves no pass at either head, says the head moved, and "
          "exits 4",
          code == 4 and new != sha and not gate_passed(evs, sha) and not gate_passed(evs, new)
          and any("head moved" in ln for ln in out) and "head moved" in last_log(a)[-1],
          str(out))
    # handback ready: the head, the tree, the push, the gate
    commit(w, a, "g2.py", "G = 2\n")
    w.chantier("gate", a, GATE)
    w.chantier("verdict", a, "VERIFIED")
    ship(w, a, "feat: g2")
    link, shipped = w.cr(a)["pr"], head(a)
    check("`ship` records the full SHA of the head in the CR and its event",
          w.cr(a)["head"] == shipped and events("ship", a)[-1]["head"] == shipped
          and len(shipped) == 40)
    commit(w, a, "g3.py", "G = 3\n")
    refusals = []
    for extra in ([], ["--no-gate", "AGENTS.md declares no long gate"]):
        code, _ = w.chantier("handback", a, "ready", link, *extra, expect=2)
        refusals.append(code == 2 and "is not the head ship recorded" in w.last_stderr)
    w.sh("git", "reset", "--hard", "--quiet", shipped, cwd=wt(a))
    (wt(a) / "junk.txt").write_text("loose\n")
    for extra in ([], ["--no-gate", "AGENTS.md declares no long gate"]):
        code, _ = w.chantier("handback", a, "ready", link, *extra, expect=2)
        refusals.append(code == 2 and "uncommitted" in w.last_stderr
                        and "is not the head ship recorded" not in w.last_stderr)
    (wt(a) / "junk.txt").unlink()
    w.sh("git", "update-ref", "-d", f"refs/remotes/origin/{w.cr(a)['branch']}", cwd=wt(a))
    for extra in ([], ["--no-gate", "AGENTS.md declares no long gate"]):
        code, _ = w.chantier("handback", a, "ready", link, *extra, expect=2)
        refusals.append(code == 2 and "not pushed" in w.last_stderr)
    w.sh("git", "fetch", "--quiet", "origin", cwd=wt(a))
    check("`handback ready` exits 2 naming the cause: a commit after `ship`, a dirty tree, a head "
          "not pushed; `--no-gate` waives none of these", all(refusals) and len(refusals) == 6,
          str(refusals))
    commit(w, a, "g4.py", "G = 4\n")
    ship(w, a, "feat: g4")
    w.chantier("verdict", a, "VERIFIED")
    code, _ = w.chantier("handback", a, "ready", link, expect=2)
    check("a gate passed only at an earlier head is refused, with that cause alone",
          code == 2 and "no long gate passed" in w.last_stderr
          and "is not the head ship recorded" not in w.last_stderr
          and "not pushed" not in w.last_stderr
          and "uncommitted" not in w.last_stderr, w.last_stderr)
    w.chantier("gate", a, GATE)
    w.chantier("handback", a, "ready", link)
    check("with the commit shipped, clean, pushed, gated and verified, `handback ready` passes",
          w.cr(a)["status"] == "ready")

    # core.abbrev 12: the heads are the full SHA, so `ship` and `handback` agree
    w.sh("git", "config", "core.abbrev", "12")
    try:
        commit(w, b, "g5.py", "G = 5\n")
        w.chantier("gate", b, GATE)
        ship(w, b, "feat: g5")
        w.chantier("verdict", b, "VERIFIED")
        w.chantier("handback", b, "ready", w.cr(b)["pr"])
    finally:
        w.sh("git", "config", "--unset", "core.abbrev")
    check("with core.abbrev 12, `gate`, `ship`, `verdict` then `handback ready` succeed",
          w.cr(b)["status"] == "ready" and len(w.cr(b)["head"]) == 40)

    # a record whose heads were short, before the change
    commit(w, c, "g6.py", "G = 6\n")
    w.chantier("gate", c, GATE)
    ship(w, c, "feat: g6")
    w.chantier("verdict", c, "VERIFIED")
    long_head = w.cr(c)["head"]
    for name in ("events.jsonl", "batch.json"):
        path = w.folder() / name
        path.write_text(path.read_text("utf-8").replace(long_head, long_head[:7]), encoding="utf-8")
    w.chantier("handback", c, "ready", w.cr(c)["pr"])
    check("a record holding short heads from before the change still reaches `handback ready`",
          w.cr(c)["status"] == "ready" and w.cr(c)["head"] == long_head[:7])

    # the budget bounds the rounds
    state = w.folder() / "batch.json"
    for i in range(3):
        w.chantier("note", d, f"round {i}")
        w.chantier("round", d)
    state.write_text(json.dumps({**w.batch(), "spent_usd": 2}), encoding="utf-8")
    code, _ = w.chantier("round", e, expect=5)
    refused = code == 5 and "budget" in w.last_stderr and "round limit" not in w.last_stderr
    code, _ = w.chantier("round", d, expect=5)
    both = code == 5 and "budget" in w.last_stderr and "round limit" not in w.last_stderr
    check("with the budget spent, `round` exits 5 with a budget message, the round count "
          "unchanged and nothing logged; with the limit reached too, the budget message wins",
          refused and both and w.cr(e)["round"] == 0 and not events("round", e)
          and w.cr(d)["round"] == 3, w.last_stderr)
    commit(w, d, "g7.py", "G = 7\n")
    w.chantier("gate", d, GATE)
    ship(w, d, "feat: g7")
    w.chantier("note", d, "still open past the budget")
    w.chantier("verdict", d, "VERIFIED")
    w.chantier("handback", d, "ready", w.cr(d)["pr"])
    check("`gate`, `ship`, `note`, `verdict` and `handback` are never refused for the budget",
          w.cr(d)["status"] == "ready")
    state.write_text(json.dumps({**w.batch(), "spent_usd": 0}), encoding="utf-8")
    for i in range(3):
        w.chantier("note", e, f"round {i}")
        w.chantier("round", e)
    code, _ = w.chantier("round", e, expect=5)
    check("within the budget, the round-limit refusal keeps its own message",
          code == 5 and "round limit" in w.last_stderr and "budget" not in w.last_stderr,
          w.last_stderr)
    state.write_text(json.dumps({**w.batch(), "budget_usd": None, "spent_usd": 2}),
                     encoding="utf-8")
    start_driver(w, f)  # the Driver's first step: the worktree exists when the round is counted
    w.chantier("round", f)
    check("with no budget, `round` is unchanged whatever the spend", w.cr(f)["round"] == 1)
    ring = events("round", f)[-1]
    code, _ = w.chantier("round", f, expect=2)
    check("the `round` event keeps the worktree's head and a fingerprint; a stray round on a "
          "worktree that did not change is refused",
          code == 2 and ring.get("wt_head") == head(f) and ring.get("wt_state")
          and w.cr(f)["round"] == 1 and len(events("round", f)) == 1, w.last_stderr)
    commit(w, f, "g8.py", "G = 8\n")
    w.chantier("round", f)
    check("a `round` passes with no note when the worktree's head changed since the last one",
          w.cr(f)["round"] == 2)
    (wt(f) / "dirty.py").write_text("D = 1\n")
    w.chantier("round", f)
    check("a `round` passes with no note when an untracked file appeared since the last one",
          w.cr(f)["round"] == 3)


def restore_cr(w: World) -> None:
    note("\n## 12d. `restore`: a trashed CR back to the inbox")
    inbox_of = lambda out: w.work / out[0].removeprefix("filed ").split(";", 1)[0]  # noqa: E731
    trash = w.state / "6-trash"

    def trashed(out):
        return w.work / out[0].removeprefix("abandoned ")

    plain = inbox_of(w.chantier("file", "Restore plain")[1])
    (plain / "01-intent.md").write_text("# Restore plain\n")
    (plain / "work").mkdir()
    (plain / "work" / "notes.md").write_text("kept\n")
    old = trashed(w.chantier("abandon", plain)[1])
    code, out = w.chantier("restore", old)
    check("`restore 6-trash/<stamp>-<slug>` puts `1-inbox/<slug>` back, whole, and updates STATUS.md",
          code == 0 and (w.state / "1-inbox" / "restore-plain" / "work" / "notes.md").is_file()
          and (w.state / "1-inbox" / "restore-plain" / "intake" / "request.md").is_file()
          and not old.exists() and "restore-plain" in (w.state / "STATUS.md").read_text("utf-8"),
          str(out))
    numbered = inbox_of(w.chantier("file", "2026 plan")[1])
    gone = trashed(w.chantier("abandon", numbered)[1])
    w.chantier("restore", gone)
    check("a leading number of a plain slug is not stripped",
          (w.state / "1-inbox" / "2026-plan").is_dir() and not (w.state / "1-inbox" / "plan").exists())
    # a name clash, an item that is not directly under 6-trash
    gone = trashed(w.chantier("abandon", w.state / "1-inbox" / "restore-plain")[1])
    inbox_of(w.chantier("file", "Restore plain")[1])
    code, _ = w.chantier("restore", gone, expect=2)
    stayed = gone.is_dir()
    w.chantier("restore", gone, "--slug", "restore-again")
    check("a name clash exits 2 with nothing moved, and `--slug` resolves it",
          code == 2 and stayed and (w.state / "1-inbox" / "restore-again").is_dir())
    old_archive = w.state / "5-archives" / "260101-0000-9-old"
    old_archive.mkdir(parents=True)
    code, _ = w.chantier("restore", old_archive, expect=2)
    check("an item of `5-archives` is refused, and stays", code == 2 and old_archive.is_dir())
    # a cancelled CR of an open batch
    one, two = (prepare_cr(w, t)[1] for t in ("Restore one", "Restore two"))
    w.reset()
    w.start(str(one), str(two), *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman10", "--epoch", 1)
    x, y = (k["id"] for k in w.batch()["crs"])
    w.chantier("cancel", x, "--epoch", 1)
    w.chantier("cancel", y, "--epoch", 1)
    path = w.at(w.cr(y)["path"])
    code, out = w.chantier("restore", path)
    back = w.state / "1-inbox" / "restore-two"
    check("a former batch CR loses its number and keeps `formerly CR-<n> of <batch>`; the output "
          "says in one line that its branch, worktree and PR stay",
          code == 0 and back.is_dir() and not path.exists() and len(out) == 2
          and f"formerly {y} of {w.name}" in (back / "01-intent.md").read_text("utf-8")
          and w.cr(y)["status"] == "cancelled" and w.cr(y)["branch"] in out[1], str(out))
    w.chantier("pause", "--epoch", 1)
    priced_foreman(w)
    code, out = w.chantier("close")
    check("after restoring a cancelled CR of a paused batch, `close` (without `--yes`) still runs",
          code == 0 and out[-1].startswith("ask the user"), str(out))
    number = int(y.removeprefix("CR-"))
    w.reset()
    _, fresh = prepare_cr(w, "Restore number")
    w.start(str(fresh), *FROM_AGENTS_MD)
    new = int(w.batch()["crs"][0]["id"].removeprefix("CR-"))
    check("a CR number taken off a restored folder is never given again", new > number,
          f"{y} then CR-{new}")


def stack_batch(w: World) -> None:
    note("\n## 13. A stack on request, one open batch, a stack merged in part")
    w.reset()
    bottom, middle, top = (prepare_cr(w, t)[1] for t in ("Stack bottom", "Stack middle", "Stack top"))
    _, joined = prepare_cr(w, "Stack joiner")
    w.start(str(bottom), str(middle), str(top), "--mode", "stack", *FROM_AGENTS_MD)
    d = w.batch()
    check("`open --mode stack` makes a stack of four slots; the batch is `batch-<n>`",
          d["mode"] == "stack" and d["slots"] == 4 and re.fullmatch(r"batch-\d\d", d["id"])
          and d["id"] == w.name and w.folder().name == "4-batch"
          and d["crs"][0]["branch"].startswith(f"chantier/{w.name}/")
          and Path(d["crs"][0]["worktree"]).name == f"{w.name}-{d['crs'][0]['id']}", str(d))
    code, _ = w.chantier("open", str(joined), *FROM_AGENTS_MD, expect=2)
    check("a second `open` is refused while a batch is open, and says which",
          code == 2 and w.name in w.last_stderr and "order add" in w.last_stderr
          and joined.is_dir() and len(list((w.state / "4-batch").glob("batch.json"))) == 1,
          w.last_stderr)
    w.chantier("foreman", "set", "local_foreman8", "--epoch", 1)
    w.env["CHANTIER_BATCH"] = w.name.removeprefix("batch-").lstrip("0")  # the number alone
    fm = Foreman(w, epoch=1)
    fm.turn()
    one, two, three = (c["id"] for c in w.batch()["crs"])
    base = {c: w.chantier("handoff", c)[1] for c in (one, two, three)}
    _, stacked = w.chantier("take", "stack", "--epoch", 1)
    w.chantier("agents", "set", "stack", "-", "--epoch", 1)
    check("a stack: independent CRs are all taken at once and start on the default branch; "
          "their place in the stack is the one under it",
          fm.started == [one, two, three]
          and all(any("base origin/main" in ln for ln in base[c]) for c in (one, two, three))
          and "base origin/main" in stacked[1]
          and f"base {w.cr(one)['branch']}" in stacked[2]
          and f"base {w.cr(two)['branch']}" in stacked[3], str(base) + str(stacked))
    for i, cr in enumerate((one, two, three)):
        driver_round(w, cr, f"stack{i}.py", f"N = {i}\n")
        w.ready(cr, w.cr(cr)["pr"])

    def ship_bases(cr: str) -> list[str]:
        events = [json.loads(e) for e in (w.folder() / "events.jsonl").read_text().splitlines()]
        return [e["base"] for e in events if e["kind"] == "ship" and e["cr"] == cr]
    check("before `stack`, `ship` records the default branch for every independent CR",
          all(ship_bases(c)[-1] == "main" for c in (one, two, three)), str(ship_bases(two)))
    w.chantier("stack", one, two, three)
    w.chantier("ship", three, w.cr(three)["pr"])
    w.chantier("ship", one, w.cr(one)["pr"])
    check("after `stack`, `ship` records the CR under it, the first on the default branch",
          ship_bases(three)[-1] == w.cr(two)["branch"] and ship_bases(one)[-1] == "main",
          str(ship_bases(three)))
    _, out = w.chantier("order", "add", "--note", str(joined))
    d = w.batch()
    four = d["crs"][-1]["id"]
    check("`order add` joins the open batch, on top of the stack; no batch is opened",
          len(d["crs"]) == 4 and w.cr(four)["status"] == "queued"
          and w.cr(four)["path"].startswith("4-batch/1-pending/")
          and len(list((w.state / "4-batch").glob("batch.json"))) == 1
          and any("base origin/main" in ln for ln in w.chantier("handoff", four)[1]),
          str(out))
    w.chantier("order", "after", four, "--note", two)
    chained = any(f"base {w.cr(two)['branch']}" in ln for ln in w.chantier("handoff", four)[1])
    w.chantier("order", "after", four, "--note", "-")
    check("a chain through `order after` starts on the ready CR's branch; `--note -` puts the "
          "queued CR back on the default branch",
          chained and w.cr(four)["status"] == "queued" and "after" not in w.cr(four)
          and any("base origin/main" in ln for ln in w.chantier("handoff", four)[1]))
    fm.turn()
    driver_round(w, four, "stack3.py", "N = 3\n")
    w.ready(four, w.cr(four)["pr"])

    _, out = w.chantier("order", "merged", one)
    d = w.batch()
    check("the bottom merges alone: it moves to 3-done at once and the batch stays open",
          w.cr(one)["status"] == "merged" and "/3-done/" in w.cr(one)["path"]
          and (w.state / w.cr(two)["path"]).is_dir() and d["status"] == "running"
          and all(w.cr(c)["status"] == "ready" for c in (two, three, four)), str(out))
    _, out = w.chantier("take", "stack", "--epoch", 1)
    check("what remains forms another stack: the first now stands on the default branch",
          out[0].endswith(f"{two} → {three} → {four}")
          and f"{two} ready" in out[1] and "base origin/main" in out[1]
          and f"base {w.cr(two)['branch']}" in out[2], str(out))
    w.chantier("agents", "set", "stack", "agent-stack", "--epoch", 1)
    code, _ = w.chantier("take", "stack", "--epoch", 1, expect=2)
    check("one stack driver at a time, and the batch does not pause under it",
          code == 2 and w.chantier("pause", "--epoch", 1, expect=2)[0] == 2
          and w.batch()["status"] == "running")
    w.chantier("ship", two, w.cr(two)["pr"])
    ships = [json.loads(e) for e in (w.folder() / "events.jsonl").read_text().splitlines()]
    last = [e for e in ships if e["kind"] == "ship" and e["cr"] == two][-1]
    check("the restacked PR is recorded on the default branch", last["base"] == "main", str(last))
    w.chantier("agents", "set", "stack", "-", "--epoch", 1)
    for cr in (two, three, four):
        w.chantier("order", "merged", cr)
    fm.turn()
    if fm.paused:
        priced_foreman(w)
    check("the stack merged piece by piece: the batch pauses, then closes",
          fm.paused and w.batch()["status"] == "paused"
          and w.chantier("close", "--batch", w.name.removeprefix("batch-"), "--yes")[0] == 0
          and not (w.folder() / "batch.json").exists())
    w.env.pop("CHANTIER_BATCH", None)


def forge_stack_cli(w: World) -> None:
    note("\n## 13a. `forge-stack`: the native stack made and read back on the forge")
    w.reset()
    a_item, b_item, r_item = (prepare_cr(w, t)[1] for t in ("Forge piece a", "Forge piece b", "Forge release"))
    w.start(str(a_item), str(b_item), str(r_item), "--mode", "stack", "--release", 3, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    a, b, r = (c["id"] for c in w.batch()["crs"])
    w.chantier("stack", a, b, r)
    path_key = next(k for k in w.env if k.upper() == "PATH")
    on_path = {path_key: f"{w.fake.parent}{os.pathsep}{w.env[path_key]}"}
    links = {a: PR_LINK[ARGS.forge] + "201", b: PR_LINK[ARGS.forge] + "202", r: PR_LINK[ARGS.forge] + "203"}

    def record(**prs: str) -> None:
        d = w.batch()
        for c in d["crs"]:
            if c["id"] in prs:
                c["pr"] = prs[c["id"]]
        (w.folder() / "batch.json").write_text(json.dumps(d, indent=2))

    def stack_calls() -> list[list[str]]:
        log = w.root / "gh-state.json.calls"
        rows = [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
        return [x for x in rows if x[:1] == ["api"] and "POST" in x and any(a.endswith("/stacks") for a in x)]

    record(**{a: links[a], b: links[b]})
    code, _ = w.chantier("forge-stack", "create", env=on_path, expect=2)
    check("`forge-stack create` is refused (exit 2) when a stacked CR has no PR recorded, naming it"
          if ARGS.forge == "github" else "`forge-stack create` is refused (exit 2) on GitLab links",
          code == 2 and (r in w.last_stderr and "no PR recorded" in w.last_stderr
                         if ARGS.forge == "github" else "GitHub only" in w.last_stderr), w.last_stderr)
    record(**{r: links[r]})
    if ARGS.forge == "gitlab":
        code, _ = w.chantier("forge-stack", "create", env=on_path, expect=2)
        check("on a GitLab remote `forge-stack create` is refused: GitHub only",
              code == 2 and "GitHub only" in w.last_stderr and not stack_calls(), w.last_stderr)
        code, _ = w.chantier("forge-stack", "show", env=on_path, expect=2)
        check("on a GitLab remote `forge-stack show` is refused: GitHub only",
              code == 2 and "GitHub only" in w.last_stderr, w.last_stderr)
    else:
        code, out = w.chantier("forge-stack", "create", env=on_path)
        posts = stack_calls()
        check("`forge-stack create` calls the stacks endpoint once, the PRs bottom to top and the "
              "release PR last, and prints the stack's link",
              code == 0 and len(posts) == 1 and [x for x in posts[0] if x.startswith("pull_requests[]")]
              == [f"pull_requests[]={n}" for n in (201, 202, 203)] and "--hostname" not in posts[0]
              and "repos/acme/demo/stacks" in posts[0] and out and out[0].startswith("stack #100 ")
              and links[r] in out[0], f"{out} {posts}")
        code, out = w.chantier("forge-stack", "show", env=on_path)
        check("`forge-stack show` exits 0 on a stack that matches the record; it writes nothing",
              code == 0 and "ready" in out[0] and len(stack_calls()) == 1, str(out))
        w.chantier("forge-stack", "create", env=on_path, expect=4)
        check("a second `create` over PRs already stacked comes back with the forge's exact text (exit 4)",
              "already in a stack" in w.last_stderr, w.last_stderr)

        def stack_on_forge(order: list[int], drafts: list[int] = (), is_open: bool = True) -> None:
            w.gh(stacks=[{"number": 100, "open": is_open, "pull_requests": order}], drafts=list(drafts))
        cases = [("a draft", dict(order=[201, 202, 203], drafts=[202]), "check 4", "#202"),
                 ("a wrong order", dict(order=[202, 201, 203]), "check 3", "#202"),
                 ("the release not on top", dict(order=[201, 203, 202]), "check 5", "#203"),
                 ("a closed stack", dict(order=[201, 202, 203], is_open=False), "check 1", "not open"),
                 ("a missing PR", dict(order=[201, 203]), "check 2", "#202"),
                 ("a foreign PR", dict(order=[201, 202, 203, 999]), "check 2", "#999")]
        for what, kw, line, word in cases:
            stack_on_forge(**kw)
            code, out = w.chantier("forge-stack", "show", env=on_path, expect=2)
            check(f"`forge-stack show` on {what}: a `{line}` line naming the cause, exit 2",
                  code == 2 and any(x.startswith(line) and word in x for x in out), str(out))
        stack_on_forge([201, 202, 203], drafts=[202, 203])
        code, out = w.chantier("forge-stack", "show", env=on_path, expect=2)
        check("`forge-stack show` prints one line per failed check", len(out) == 1 and "#202 #203" in out[0], str(out))
        w.gh(stacks=[{"number": 99, "open": False, "pull_requests": [201, 202]},
                     {"number": 100, "open": True, "pull_requests": [201, 202, 203]}], drafts=[])
        code, out = w.chantier("forge-stack", "show", env=on_path)
        check("`forge-stack show` without --stack prefers the open stack over a closed one that "
              "overlaps the batch's PRs", code == 0 and "stack #100 ready" in out[0], str(out))
        record(**{b: PR_LINK["gitlab"] + "202"})
        for action in ("create", "show"):
            code, _ = w.chantier("forge-stack", action, env=on_path, expect=2)
            check(f"on a GitLab link `forge-stack {action}` is refused: GitHub only",
                  code == 2 and "GitHub only" in w.last_stderr, w.last_stderr)
        record(**{b: links[b]})

    w.chantier("foreman", "set", "local_foreman_fs", "--epoch", 1)
    _, joined = prepare_cr(w, "Forge inserted")
    w.chantier("order", "add", "--note", str(joined))
    new = w.batch()["crs"][-1]["id"]
    w.chantier("stack", a, new, b, r)
    _, listed = w.chantier("take", "stack", "--epoch", 1)
    w.chantier("agents", "set", "stack", "-", "--epoch", 1)
    check("insertion: a CR added to the stack batch and ordered below the release CR sits there in "
          "`take stack`, the release CR still last",
          listed and listed[0].endswith(f"{a} → {new} → {b} → {r}") and listed[-1].startswith(f"{r} "),
          str(listed))
    if ARGS.forge == "github":
        code, out = w.chantier("forge-stack", "show", env=on_path, expect=2)
        check("after the insertion, `forge-stack show` names the new CR, which has no PR yet",
              code == 2 and any(x.startswith("check 2") and new in x for x in out), str(out))
    w.reset()
    _, par = prepare_cr(w, "Forge parallel")
    w.start(str(par), *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    code, _ = w.chantier("forge-stack", "create", env=on_path, expect=2)
    check("`forge-stack create` is refused (exit 2) on a parallel batch",
          code == 2 and "not a stack" in w.last_stderr, w.last_stderr)
    w.reset()
    w.env.pop("CHANTIER_BATCH", None)


def batch_modes(w: World) -> None:
    note("\n## 13b. The three modes: parallel by default, series, the switch to a stack")
    w.reset()
    p1, p2 = prepare_cr(w, "Mode one")[1], prepare_cr(w, "Mode two")[1]
    code, _ = w.start(str(p1), "--parallel", *FROM_AGENTS_MD, expect=2)
    check("`open --parallel` is refused as an unknown argument", code == 2 and p1.is_dir(),
          w.last_stderr)
    w.start(str(p1), str(p2), *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    one, two = (c["id"] for c in w.batch()["crs"])
    check("a batch with no mode named is parallel", w.batch()["mode"] == "parallel",
          str(w.batch()["mode"]))
    code, _ = w.chantier("take", "stack", expect=2)
    code2, _ = w.chantier("stack", one, two, expect=2)
    check("parallel: `take stack` and `stack` are refused, `order mode` too",
          code == 2 and code2 == 2 and w.chantier("order", "mode", "--note", "stack", expect=2)[0] == 2
          and w.batch()["mode"] == "parallel", w.last_stderr)
    for cr, name in ((one, "mode_one.py"), (two, "mode_two.py")):
        w.chantier("take", cr)
        start_driver(w, cr)
        driver_round(w, cr, name, "N = 1\n")
        w.ready(cr, w.cr(cr)["pr"])
    w.chantier("order", "merged", one)
    code, out = w.chantier("take", two, "--note", f"rebase: {one} merged")
    check("parallel: after a merge, a ready CR goes back to a Driver for its rebase, on the "
          "default branch", code == 0 and any("base origin/main" in ln for ln in out), str(out))

    w.reset()
    sa, sb, sc = (prepare_cr(w, t)[1] for t in ("Series first", "Series second", "Series third"))
    w.start(str(sa), str(sb), str(sc), "--mode", "series", *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    a, b, c = (x["id"] for x in w.batch()["crs"])
    _, out = w.chantier("status")
    check("series: `status` shows the next CR waiting for the previous one",
          w.batch()["mode"] == "series"
          and any(ln.startswith(b) and f"waits for {a} queued" in ln for ln in out)
          and any(ln.startswith(c) and f"waits for {b} queued" in ln for ln in out), str(out))
    code, _ = w.chantier("take", b, expect=2)
    check("series: `take` refuses the next CR until the previous one is ready",
          code == 2 and f"waits for {a} queued" in w.last_stderr, w.last_stderr)
    w.chantier("take", a)
    start_driver(w, a)
    driver_round(w, a, "series_a.py", "A = 1\n")
    code, _ = w.chantier("take", b, expect=2)
    check("series: a working predecessor is not enough", code == 2 and f"{a} working" in w.last_stderr,
          w.last_stderr)
    w.ready(a, w.cr(a)["pr"])
    _, out = w.chantier("take", b)
    start_driver(w, b)
    check("series: once the previous one is ready, the next starts on its branch, and the third "
          "still waits", any(f"base {w.cr(a)['branch']}" in ln for ln in out)
          and w.chantier("take", c, expect=2)[0] == 2 and f"waits for {b} working" in w.last_stderr,
          str(out))
    driver_round(w, b, "series_b.py", "B = 1\n")
    w.ready(b, w.cr(b)["pr"])
    w.chantier("order", "merged", a)
    _, out = w.chantier("take", b, "--note", f"rebase: {a} merged")
    check("series: once the previous one is merged, the next one is rebased on the default branch",
          any("base origin/main" in ln for ln in out), str(out))
    w.ready(b, w.cr(b)["pr"])
    _, out = w.chantier("take", c)
    check("series: the third starts on the second's branch once that one is ready",
          any(f"base {w.cr(b)['branch']}" in ln for ln in out), str(out))
    w.chantier("handback", c, "blocked", "question: which one?")
    sd = prepare_cr(w, "Series on top")[1]
    w.chantier("order", "add", "--note", str(sd))
    d = w.batch()["crs"][-1]["id"]
    _, out = w.chantier("status")
    check("series: `order add` puts the new CR on top, waiting for the last one",
          w.cr(d)["order"] == max(x["order"] for x in w.batch()["crs"])
          and any(ln.startswith(d) and f"waits for {c} blocked" in ln for ln in out), str(out))

    w.reset()
    x1, x2 = prepare_cr(w, "Series late")[1], prepare_cr(w, "Series early")[1]
    depends_on(x1, x2.name)
    code, _ = w.start(str(x1), str(x2), "--mode", "series", *FROM_AGENTS_MD, expect=2)
    check("series: a CR placed before its dependency is refused at `open`",
          code == 2 and "cannot come before it in the series" in w.last_stderr and x1.is_dir()
          and x2.is_dir(), w.last_stderr)

    w.reset()
    y = [prepare_cr(w, t)[1] for t in ("Switch one", "Switch two", "Switch three")]
    w.start(*(str(p) for p in y), "--mode", "series", *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    a, b, c = (x["id"] for x in w.batch()["crs"])
    code, _ = w.chantier("order", "mode", "--note", "parallel", expect=2)
    check("`order mode --note parallel` is refused on a series", code == 2
          and w.batch()["mode"] == "series", w.last_stderr)
    code, _ = w.chantier("take", c, expect=2)
    _, out = w.chantier("order", "mode", "--note", "stack")
    check("`order mode --note stack` turns a series into a stack at once, and logs it",
          code == 2 and w.batch()["mode"] == "stack" and w.batch()["orders"][-1]["kind"] == "mode"
          and w.batch()["orders"][-1]["applied"]
          and any('"kind": "mode"' in ln for ln in (w.folder() / "events.jsonl").read_text().splitlines()),
          str(out))
    code, out = w.chantier("take", c)
    check("after the switch, a queued CR is taken at once, on the default branch",
          code == 0 and any("base origin/main" in ln for ln in out), str(out))
    code, out = w.chantier("take", "stack")
    check("after the switch, `take stack` works", code == 0 and out[0].startswith("the stack of batch"),
          str(out))
    code, _ = w.chantier("order", "mode", "--note", "stack", expect=2)
    check("`order mode` is refused on a stack", code == 2, w.last_stderr)
    w.env.pop("CHANTIER_BATCH", None)


def release(w: World) -> None:
    note("\n## 14. A release: the project's procedure, approvals, a fix, a grant")
    _, change = prepare_cr(w, "Last change")
    _, version = prepare_cr(w, "Release v1.1.0")
    bad = (("--release", 3), ("--release", 2, "--grant-fixes"),
           ("--autonomous-releases", 1, "--budget", 5))
    for args in bad:
        code, _ = w.chantier("open", str(change), str(version), *FROM_AGENTS_MD, *args,
                             expect=1)
        check(f"open refuses {args}", code == 1 and change.is_dir())
    w.reset()
    w.start(str(change), str(version), "--release", 2, "--slots", 2, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman3", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    work, rel = (c["id"] for c in w.batch()["crs"])
    fm.turn()
    check("the release waits for the batch's other CRs", fm.started == [work])
    code, _ = w.chantier("take", rel, expect=2)
    check("the release CR is refused until the others are merged",
          code == 2 and "merged or cancelled" in w.last_stderr, w.last_stderr)
    driver_round(w, work, "last.py", "LAST = True\n")
    w.ready(work, w.cr(work)["pr"])
    fm.turn()
    check("an ordinary ready CR goes to the user, never to a merge",
          fm.asked[-1].startswith(f"ready {work} "), str(fm.asked))
    w.chantier("order", "merged", work)
    fm.turn()
    check("once the other CR is merged, the release is taken at once (no confirmation), with "
          "the grant in its facts",
          fm.started[-1] == rel and "confirmation" not in " ".join(w.chantier("status")[1])
          and any(ln.startswith("grant: every irreversible action waits") for ln in fm.facts),
          str(fm.facts))

    tag = "push tag v1.1.0"
    _, out = w.chantier("release", "start", rel)
    check("an attempt is counted", out[0].startswith("attempt 1"), str(out))
    notes = w.state / w.cr(rel)["path"] / "work" / "notes-v1.1.0.md"
    notes.write_text("# v1.1.0\n")
    w.chantier("note", rel, "--draft", notes)
    _, out = w.chantier("status")
    check("status shows the draft on the release's line",
          any(ln.startswith(rel) and notes.as_posix() in ln for ln in out), str(out))
    code, out = w.chantier("release", "go", rel, "--note", tag, expect=2)
    check("an irreversible action without approval is refused",
          code == 2 and out[0].startswith("no approval"), str(out))
    w.chantier("handback", rel, "blocked", f"approval: {tag}")
    fm.turn()
    check("the Chief of Staff gets the approval to ask", fm.asked[-1].startswith(f"blocked {rel} approval:"))
    code, _ = w.chantier("order", "approve", work, "--note", tag, expect=1)
    check("only the release CR takes an approval", code == 1)
    w.chantier("order", "approve", rel, "--note", tag)
    check("an approval is recorded; the release stays blocked until the Foreman acts",
          w.cr(rel)["status"] == "blocked" and w.cr(rel)["approvals"] == [tag])
    fm.turn()
    check("the Foreman gives the approval to a new Release driver", fm.started[-1].startswith(f"{rel} approve:")
          and any("approvals unused: " + tag in ln for ln in fm.facts), str(fm.facts))
    code, out = w.chantier("release", "go", rel, "--note", tag)
    check("the approval opens that action", code == 0 and out[0].startswith(f"go: {tag}"))
    code, _ = w.chantier("release", "go", rel, "--note", "publish v1.1.0", expect=2)
    check("an approval is spent once", code == 2)

    w.chantier("handback", rel, "blocked", "fix: the heavy suite fails; work/fix-1.md")
    fm.turn()
    _, fix = prepare_cr(w, "Fix the heavy suite")
    code, _ = w.chantier("order", "grant", rel, "--note", "releases=1 fixes=on", expect=1)
    check("a grant without a budget is refused", code == 1 and "budget" in w.last_stderr)
    w.chantier("order", "grant", rel, "--note", "releases=1 fixes=on budget=5")
    started = len(fm.started)
    fm.turn()
    check("a grant leaves a release that waits for its fix alone",
          len(fm.started) == started and w.cr(rel)["status"] == "blocked")
    _, out = w.chantier("order", "add", "--note", str(fix), "--fix-for", rel)
    fm.turn()
    fix_id = w.batch()["crs"][-1]["id"]
    check("a fix becomes a CR of the batch; the release waits for it",
          fm.started[-1] == fix_id and w.cr(rel)["status"] == "blocked"
          and w.cr(fix_id)["fix_for"] == rel, str(fm.started))
    code, out = w.chantier("release", "go", rel, "--note", "publish v1.1.0", expect=2)
    check("no irreversible action while a fix of the release is not merged",
          code == 2 and out[0].startswith(f"no: fix {fix_id} is not merged"), str(out))
    code, _ = w.chantier("release", "go", fix_id, "--note", "merge the fix", expect=2)
    check("a fix that is not ready does not merge", code == 2 and "ready" in w.last_stderr)
    driver_round(w, fix_id, "heavy.py", "FIXED = True\n")
    w.gh(merge_refused=True)
    w.ready(fix_id, w.cr(fix_id)["pr"])
    w.chantier("order", "grant", rel, "--note", "fixes=off")
    code, out = w.chantier("release", "go", fix_id, "--note", "merge the fix", expect=2)
    check("without the grant, the user merges the fix",
          code == 2 and "the user merges it" in out[0], str(out))
    w.chantier("order", "grant", rel, "--note", "fixes=on")
    fm.turn()
    check("a merge the forge refuses goes to the Chief of Staff, the fix stays ready",
          fm.asked[-1].startswith(f"refused {fix_id}") and w.cr(fix_id)["status"] == "ready",
          fm.asked[-1])
    w.gh(merge_refused=False)
    fm.told.discard((fix_id, "ready", w.cr(fix_id)["pr"]))  # the user's word: try again
    fm.turn()
    check("under the grant the Foreman merges the fix with the forge's CLI and records it; "
          "the release goes on",
          w.cr(fix_id)["status"] == "merged" and "/3-done/" in w.cr(fix_id)["path"]
          and any(a.startswith(f"merged {fix_id} ") for a in fm.asked)
          and fm.started[-1].startswith(f"{rel} fix merged:"), str(fm.asked))

    _, out = w.chantier("release", "start", rel)
    check("each new attempt is counted", out[0].startswith("attempt 2"), str(out))
    state = w.folder() / "batch.json"
    data = w.batch()
    state.write_text(json.dumps({**data, "spent_usd": 6}))
    code, out = w.chantier("release", "go", rel, "--note", "publish v1.1.0", expect=5)
    check("past the budget, a grant opens nothing", code == 5 and "budget" in out[0], str(out))
    w.chantier("handback", rel, "blocked", "budget: publish v1.1.0")
    fm.turn()
    _, out = w.chantier("order", "budget", "--note", "20")
    check("a wider budget is recorded; the CR blocked on it waits for the Foreman",
          out[-1] == "budget $20" and w.cr(rel)["status"] == "blocked", str(out))
    fm.turn()
    check("the Foreman sends the blocked release on, with the budget's note",
          fm.started[-1].startswith(f"{rel} budget:") and w.cr(rel)["status"] == "working"
          and all(o["done"] for o in w.batch()["orders"]), str(fm.started))
    code, out = w.chantier("release", "go", rel, "--note", "publish v1.1.0")
    check("the grant opens the action without asking", code == 0 and "without asking" in out[0])
    w.chantier("note", rel, "release commit")
    commit(w, rel, "VERSION", "1.1.0\n", "release: v1.1.0")
    w.chantier("gate", rel, GATE)
    ship(w, rel, "release: v1.1.0")
    # the grant is lifted for a moment: the user's approval never covers the release PR's merge
    w.chantier("order", "grant", rel, "--note", "releases=0 fixes=on budget=20")
    w.chantier("handback", rel, "ready", w.cr(rel)["pr"])
    check("the release PR is prepared: `ready`, no verdict asked, and not red",
          w.cr(rel)["status"] == "ready" and "waits for its merge" in w.last_out[-1]
          and not any("🔴" in lb for lb in drawn(w, rel)[0]), str(w.last_out))
    events = [json.loads(e) for e in (w.folder() / "events.jsonl").read_text().splitlines()]
    check("the release PR, in a parallel batch, sits on the default branch",
          [e["base"] for e in events if e["kind"] == "ship" and e["cr"] == rel][-1] == "main")
    w.chantier("order", "approve", rel, "--note", f"merge the release PR {w.cr(rel)['pr']}")
    code, out = w.chantier("release", "go", rel, "--note", f"merge the release PR {w.cr(rel)['pr']}",
                           expect=2)
    check("an approval never covers the release PR's merge: `release go` answers `merge`",
          code == 2 and out[0].startswith("no: the release PR") and "user's to merge" in out[0],
          str(out))
    for o in w.batch()["orders"]:
        if not o["done"]:
            w.chantier("order", "done", o["id"], "--epoch", 1)
    w.chantier("order", "grant", rel, "--note", "releases=1 fixes=on budget=20")
    w.chantier("order", "done", w.batch()["orders"][-1]["id"], "--epoch", 1)
    w.gh(merge_refused=True)
    fm.turn()
    check("under the grant the Foreman merges the release PR; refused by the forge, it asks",
          fm.asked[-1].startswith(f"refused {rel}") and w.cr(rel)["status"] == "ready",
          fm.asked[-1])
    w.gh(merge_refused=False)
    fm.told.discard((rel, "refused", fm.asked[-1].removeprefix(f"refused {rel} ")))
    drivers = len(fm.started)
    fm.turn()
    check("merged with the forge's CLI, `order merged --epoch` sends the release on with a new "
          "Driver, not to the archives",
          len(fm.started) == drivers + 1 and fm.started[-1].startswith(f"{rel} merged:")
          and "5-archives/" not in w.cr(rel)["path"]
          and all(o["done"] for o in w.batch()["orders"]), str(fm.started))
    check("the merged PR is not the next attempt's", w.cr(rel).get("pr") is None)
    merged_pr = w.cr(rel)["merged_pr"]
    for step in ("push tag v1.1.0", "publish v1.1.0"):
        code, out = w.chantier("release", "go", rel, "--note", step)
        check(f"the merge is the go for `{step}`, with no approval",
              code == 0 and out[0].startswith("go:") and merged_pr in out[0]
              and "approved" not in out[0], str(out))
    w.chantier("release", "published", rel, "--note", "v1.1.0 https://forge.example/v1.1.0")
    _, out = w.chantier("handback", rel, "ready", "https://forge.example/v1.1.0")
    check("a released CR moves to 3-done, and the batch can pause",
          "/3-done/" in w.cr(rel)["path"] and "chantier pause" in out[1], str(out))
    fm.turn()
    check("the release done, the batch pauses", fm.paused, str(fm.asked))
    calls = (w.root / "gh-state.json.calls").read_text()
    merged = ('"merge"', '/merge"')[ARGS.forge == "gitlab"]
    check("the forge saw the Foreman's merges", calls.count(merged) >= 2)


def granted_fixes(w: World) -> None:
    note("\n## 14b. The Foreman starts a release's fixes under the grant, up to three")
    _, version = prepare_cr(w, "Release v1.3.0")
    w.reset()
    w.start(str(version), "--release", 1, "--slots", 1, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman5", "--epoch", 1)
    rel = w.batch()["crs"][0]["id"]
    work = w.state / w.cr(rel)["path"] / "work"
    work.mkdir()
    files = [work / f"fix-{n}.md" for n in range(1, 5)]
    for n, path in enumerate(files, 1):
        path.write_text(f"# Fix step {n}\n\nExpected: it passes. Actual: it fails.\n")
    add = ("order", "add", "--note", files[0], "--fix-for", rel)
    code, _ = w.chantier(*add, "--epoch", 1, expect=2)
    check("without a grant, the Foreman starts no fix", code == 2 and "no grant" in w.last_stderr,
          w.last_stderr)
    w.chantier("order", "budget", "--note", 50)
    w.chantier("order", "grant", rel, "--note", "fixes=on")
    codes = [w.chantier("order", "add", "--note", path, "--fix-for", rel, "--epoch", 1,
                        expect=None)[0] for path in files]
    check("under the grant, three fixes start and a fourth is refused", codes == [0, 0, 0, 5],
          str(codes))
    fix = w.batch()["crs"][1]
    spec = w.state / fix["path"] / "03-change-spec.md"
    check("a fix file becomes a fix CR of the batch, its specification kept",
          fix["kind"] == "fix" and fix["title"] == "Fix step 1" and fix["status"] == "queued"
          and spec.read_text() == files[0].read_text(), str(fix))
    w.chantier("order", "add", "--note", files[3], "--fix-for", rel)
    check("past three, a fix is the user's go", len(w.batch()["crs"]) == 5)
    for c in w.batch()["crs"]:
        if c["status"] != "cancelled":  # a second drop is refused
            w.chantier("order", "drop", c["id"])
    _, out = w.chantier("status")
    check("`status` tells an order the CLI applied from one nothing has touched",
          any(ln.startswith("orders the CLI applied") and "order done" in ln and "O-" in ln
              for ln in out), str(out))
    dropped = next(c for c in w.batch()["crs"] if c["status"] == "cancelled")
    count = len(w.batch()["orders"])
    code, _ = w.chantier("order", "drop", dropped["id"], expect=2)
    check("a second drop of a cancelled CR is refused and records no order",
          code == 2 and "already dropped" in w.last_stderr and len(w.batch()["orders"]) == count,
          w.last_stderr)
    code, _ = w.chantier("order", "drop", dropped["id"].removeprefix("CR-"), expect=2)
    check("`101` is taken for `CR-101` in `order`", code == 2 and "already dropped" in w.last_stderr,
          w.last_stderr)
    code, _ = w.chantier("order", "note", dropped["id"], "--note", "late", expect=2)
    check("a note on a cancelled CR is refused", code == 2 and "cancelled" in w.last_stderr,
          w.last_stderr)
    code, _ = w.chantier("order", "rounds", "--note", "0", expect=1)
    check("`order rounds` with no CR shows its full usage", "--note <n>" in w.last_stderr,
          w.last_stderr)
    code, _ = w.chantier("order", "budget", "--note", "-5", expect=1)
    check("`order budget` says why a value is refused", "'-5'" in w.last_stderr
          and "dollars" in w.last_stderr, w.last_stderr)
    for o in w.batch()["orders"]:
        if not o["done"]:
            w.chantier("order", "done", o["id"], "--epoch", 1)
    w.chantier("pause", "--epoch", 1)
    priced_foreman(w)
    w.chantier("close", "--batch", w.name, "--yes")


def release_last(w: World) -> None:
    note("\n## 14c. A release added to a running batch waits for every other CR, then for the user")
    _, first = prepare_cr(w, "First change")
    _, second = prepare_cr(w, "Second change")
    _, third = prepare_cr(w, "Third change")
    _, version = prepare_cr(w, "Release v1.5.0")
    _, other = prepare_cr(w, "Release v1.6.0")
    _, fix_one = prepare_cr(w, "Fix one")
    _, fix_two = prepare_cr(w, "Fix two")
    w.reset()
    w.start(str(first), "--slots", 1, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman6", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    work = w.batch()["crs"][0]["id"]
    w.chantier("order", "add", "--release", "--fix-for", work, "--note", str(version), expect=1)
    check("--release goes with no --fix-for", w.last_stderr.count("--release") >= 1, w.last_stderr)
    w.chantier("order", "add", "--release", "--note", str(version))
    rel = w.batch()["crs"][-1]["id"]
    check("order add --release adds the batch's release CR, with the default grant, after the CR",
          w.cr(rel)["kind"] == "release" and w.cr(rel)["after"] == [work]
          and w.batch()["release"] == {"autonomous": 0, "fixes": False, "published": 0, "cr": rel},
          str(w.cr(rel)))
    w.chantier("order", "add", "--note", str(second))
    late = w.batch()["crs"][-1]["id"]
    check("a CR added later is waited for too", w.cr(rel)["after"] == [work, late])
    _, out = w.chantier("status")
    check("status shows the release waiting for each CR",
          any(ln.startswith(rel) and f"waits for {work} queued, {late} queued" in ln for ln in out),
          str(out))
    icon_is(w, rel, "🟠", "a queued release behind other CRs")
    w.chantier("order", "add", "--release", "--note", str(other), expect=2)
    check("a second release is refused, the next batch named", "next batch" in w.last_stderr,
          w.last_stderr)
    w.chantier("order", "after", rel, "--note", work, expect=2)
    check("order after is refused on the release", "release CR" in w.last_stderr, w.last_stderr)
    w.chantier("order", "after", late, "--note", rel, expect=2)
    check("a CR that waits for the release is a cycle, the release named",
          "cycle" in w.last_stderr and rel in w.last_stderr, w.last_stderr)
    w.chantier("order", "confirm", work, "--note", "v1.5.0", expect=1)
    check("only a release is confirmed", rel in w.last_stderr, w.last_stderr)
    w.chantier("order", "confirm", rel, "--note", "v1.5.0", expect=2)
    check("the user's word is refused while CRs are open: they are named",
          "not merged yet" in w.last_stderr and work in w.last_stderr and late in w.last_stderr,
          w.last_stderr)

    check("the first CR starts", fm.take(work) == 0)
    driver_round(w, work, "first.py", "FIRST = True\n")
    w.ready(work, w.cr(work)["pr"])
    code, _ = w.chantier("take", rel, expect=2)
    check("a ready CR keeps the release waiting",
          code == 2 and f"{work} ready" in w.last_stderr, w.last_stderr)
    w.chantier("order", "merged", work)
    w.chantier("order", "drop", late)
    check("a merged CR and a dropped one are met",
          w.cr(work)["status"] == "merged" and w.cr(late)["status"] == "cancelled")
    _, out = w.chantier("status")
    check("status shows no confirmation for the release: the others ended, it waits for nothing",
          not any("confirmation" in ln for ln in out)
          and not any(ln.startswith(rel) and "waits for" in ln for ln in out), str(out))
    icon_is(w, rel, "⚪", "a queued release with the others ended: no confirmation to wait for")
    w.chantier("order", "confirm", rel, "--note", "v1.5.0, the notes settled")
    check("the user's word to run the procedure is kept on the CR and in its notes, never as "
          "`confirmed`",
          w.cr(rel)["procedure"] == "v1.5.0, the notes settled" and "confirmed" not in w.cr(rel)
          and any(n.startswith("procedure:") for n in w.cr(rel)["notes"]))
    w.chantier("order", "add", "--note", str(third))
    added = w.batch()["crs"][-1]["id"]
    check("a CR added then voids the word, which the log and a note explain",
          "procedure" not in w.cr(rel) and w.cr(rel)["after"][-1] == added
          and any("voided" in n for n in w.cr(rel)["notes"])
          and any(e["kind"] == "confirm-void" for e in map(json.loads, (w.folder() / "events.jsonl").read_text().splitlines())))
    w.chantier("order", "drop", added)
    w.chantier("order", "confirm", rel, "--note", "v1.5.0, with the third change dropped")
    check("the release starts with no confirmation asked", fm.take(rel) == 0)

    w.chantier("order", "add", "--note", str(second), expect=2)
    check("order add is refused once the release has started, with its two ways out",
          "--fix-for" in w.last_stderr and "next batch" in w.last_stderr
          and "ships the work under it" in w.last_stderr, w.last_stderr)
    w.chantier("order", "confirm", rel, "--note", "again")
    check("the user's word is accepted once the release has started, the others being merged",
          w.cr(rel)["procedure"] == "again", str(w.cr(rel)))
    w.chantier("order", "add", "--note", str(fix_one), "--fix-for", rel)
    check("a fix of the release is still added",
          w.batch()["crs"][-1]["kind"] == "fix" and "procedure" in w.cr(rel))
    w.chantier("release", "start", rel)
    w.chantier("order", "merged", rel)
    check("a merged release PR puts the release back to queued, attempts kept",
          w.cr(rel)["status"] == "queued" and w.cr(rel)["attempts"] == 1)
    w.chantier("order", "add", "--note", str(second), expect=2)
    check("order add is refused again, whatever the state, since attempts says so",
          "has started" in w.last_stderr, w.last_stderr)
    w.chantier("order", "add", "--note", str(fix_two), "--fix-for", rel)
    check("order add --fix-for still works", w.batch()["crs"][-1]["fix_for"] == rel)
    fixes = [x["id"] for x in w.batch()["crs"] if x.get("fix_for") == rel]
    own = icon_is(w, rel, "🟠", "a queued release with an open fix (`take` refuses it)")
    check("the open fixes are in the release's `waits`",
          all(any(wt.startswith(f"{i} ") for wt in own["waits"]) for i in fixes)
          and f"waits for {fixes[0]}" in own["label"], str(own))
    for i in fixes:
        w.chantier("order", "drop", i)
    icon_is(w, rel, "⚪", "a queued release once its fixes have ended")

    w.reset()
    _, alone = prepare_cr(w, "Release v1.7.0")
    w.start(str(alone), "--release", 1, "--slots", 1, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman7", "--epoch", 1)
    only = w.batch()["crs"][0]["id"]
    w.chantier("order", "confirm", only, "--note", "v1.7.0")
    check("the user's word is accepted for a release alone, before a release PR is recorded",
          w.cr(only)["procedure"] == "v1.7.0", str(w.cr(only)))
    solo = Foreman(w, epoch=1)
    check("a release alone starts when taken, with no confirmation asked, on the default branch",
          solo.take(only) == 0 and any("base origin/main" in ln for ln in solo.facts),
          str(solo.facts))
    w.chantier("release", "start", only)
    commit(w, only, "VERSION", "1.7.0\n", "release: v1.7.0")
    w.chantier("gate", only, GATE)
    ship(w, only, "release: v1.7.0")
    code, out = w.chantier("release", "go", only, "--note", "tag v1.7.0", expect=2)
    check("once its PR is recorded, `release go` answers `merge` until `order merged`",
          code == 2 and out[0].startswith("no: the release PR") and "user's to merge" in out[0],
          str(out))
    w.chantier("order", "confirm", only, "--note", "again", expect=2)
    check("the user's word is refused while the release PR is not merged",
          "is not merged" in w.last_stderr, w.last_stderr)
    w.chantier("handback", only, "ready", w.cr(only)["pr"])
    w.chantier("order", "merged", only)
    code, out = w.chantier("release", "go", only, "--note", "tag v1.7.0")
    check("after `order merged`, `release go` answers `go`, naming the merged PR",
          code == 0 and out[0].startswith("go:") and "was merged" in out[0], str(out))
    w.reset()


def on_branch(w: World, cr_id: str, base: str) -> None:
    """A Driver's first step for a CR that starts on another CR's branch: the worktree its
    prompt names, on the pushed branch of the CR under it."""
    c = w.cr(cr_id)
    Path(c["worktree"]).parent.mkdir(exist_ok=True)
    w.sh("git", "fetch", "--quiet", "origin")
    w.sh("git", "worktree", "add", "--quiet", "-b", c["branch"], c["worktree"], f"origin/{base}")


def restack(w: World, cr_id: str, under: str) -> None:
    """The stack driver restacks a PR: rebase onto the CR under it, push with a lease, `ship`."""
    c = w.cr(cr_id)
    wt = Path(c["worktree"])
    w.sh("git", "fetch", "--quiet", "origin", cwd=wt)
    w.sh("git", "rebase", "--quiet", f"origin/{w.cr(under)['branch']}", cwd=wt)
    w.sh("git", "push", "--quiet", "--force-with-lease", "-u", "origin", c["branch"], cwd=wt)
    w.chantier("ship", cr_id, c["pr"])


def settle(w: World) -> None:
    """The Foreman marks each order the CLI applied as done."""
    for o in w.batch()["orders"]:
        if not o["done"]:
            w.chantier("order", "done", o["id"], "--epoch", 1)


def release_on_stack(w: World) -> None:
    note("\n## 14d. A release on top of a stack: prepared on the top CR's branch, merged last")
    w.reset()
    items = [prepare_cr(w, t)[1] for t in ("Stack piece a", "Stack piece b", "Release v1.8.0")]
    w.start(*map(str, items), "--mode", "stack", "--release", 3, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman9", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    a, b, r = (c["id"] for c in w.batch()["crs"])
    fm.turn()
    code, out = w.chantier("take", r, expect=2)
    refusal = w.last_stderr
    _, status = w.chantier("status")
    check("1. a stack's release is refused while the CRs under it are queued or working, "
          "each named; status shows no confirmation",
          fm.started == [a, b] and code == 2 and a in refusal and b in refusal
          and "ready or merged" in refusal and not any("confirmation" in ln for ln in status),
          refusal)
    for i, cr in enumerate((a, b)):
        driver_round(w, cr, f"piece{i}.py", f"N = {i}\n")
        w.ready(cr, w.cr(cr)["pr"])
    head = w.cr(a)["head"]
    code, _ = w.chantier("take", r, expect=2)
    check("2. both CRs ready but not stacked: the release is refused, naming the head of the "
          "CR the top branch does not hold, and `take stack`",
          code == 2 and head[:7] in w.last_stderr and "take stack" in w.last_stderr
          and a in w.last_stderr, w.last_stderr)
    code, _ = w.chantier("stack", r, a, b, expect=None)
    check("4. `stack` refuses an order that puts a CR above the release",
          code != 0 and "cannot sit below" in w.last_stderr and r in w.last_stderr, w.last_stderr)
    w.chantier("stack", a, b, r)
    restack(w, b, a)
    _, listed = w.chantier("take", "stack", "--epoch", 1)
    w.chantier("agents", "set", "stack", "-", "--epoch", 1)
    top = w.cr(b)["branch"]
    check("3. once stacked, `take stack` lists the release last, with the top CR's branch "
          "as its base",
          listed[0].endswith(f"{a} → {b} → {r}") and listed[-1].startswith(f"{r} queued")
          and f"base {top}" in listed[-1], str(listed))
    on_branch(w, r, top)
    code = fm.take(r)
    check("3. the release is taken, and its facts print `base` = the top CR's branch",
          code == 0 and any(f"base {top}" in ln for ln in fm.facts), str(fm.facts))

    tag = "tag v1.8.0"
    w.chantier("order", "approve", r, "--note", tag)
    w.chantier("order", "grant", r, "--note", "releases=1 budget=5")
    code, out = w.chantier("release", "go", r, "--note", tag, expect=2)
    check("5. `release go` is refused while CRs are open, with an approval and a grant: the "
          "`merge` text names them",
          code == 2 and out[0].startswith("no: ") and a in out[0] and b in out[0]
          and "not merged" in out[0], str(out))
    w.chantier("order", "grant", r, "--note", "releases=0 fixes=off budget=5")
    settle(w)

    w.chantier("release", "start", r)
    commit(w, r, "VERSION", "1.8.0\n", "release: v1.8.0")
    w.chantier("gate", r, GATE)
    wt = Path(w.cr(r)["worktree"])
    w.sh("git", "push", "--quiet", "--force-with-lease", "-u", "origin", w.cr(r)["branch"], cwd=wt)
    (w.at(w.cr(r)["path"]) / "work").mkdir(exist_ok=True)
    (w.at(w.cr(r)["path"]) / "work" / "pr-body.md").write_text(BODY.format(title=w.cr(r)["title"], cr=r))
    pr = open_pr(w, r, "release: v1.8.0", base=top)
    OPENED[r] = pr
    _, out = w.chantier("ship", r, pr)
    code, out = w.chantier("handback", r, "ready", f"{pr} draft on {top}: waits for the merge")
    events = [json.loads(e) for e in (w.folder() / "events.jsonl").read_text().splitlines()]
    check("6. the release PR is shipped on the top CR's branch and handed back `ready`, with "
          "no verdict; its STATUS icon is not red",
          code == 0 and [e["base"] for e in events if e["kind"] == "ship" and e["cr"] == r][-1] == top
          and w.cr(r)["status"] == "ready" and "waits for its merge" in out[-1]
          and not any(e["kind"] == "verdict" and e["cr"] == r for e in events)
          and not any("🔴" in lb for lb in drawn(w, r)[0]), str(out))
    extra = prepare_cr(w, "Late piece")[1]
    fixed = prepare_cr(w, "Urgent fix")[1]
    w.chantier("order", "add", "--note", str(extra), expect=2)
    check("7. `order add` is refused once the release has started",
          "has started" in w.last_stderr and "--fix-for" in w.last_stderr, w.last_stderr)
    w.chantier("order", "add", "--note", str(fixed), "--fix-for", r)
    fix = w.batch()["crs"][-1]["id"]
    check("7. `order add --fix-for` is accepted", w.cr(fix)["kind"] == "fix" and w.cr(fix)["fix_for"] == r)
    w.chantier("order", "drop", fix)
    w.chantier("order", "merged", r, expect=2)
    check("8. `order merged` on the release is refused while a CR is open: it merges last",
          a in w.last_stderr and "merges last" in w.last_stderr, w.last_stderr)
    w.chantier("order", "confirm", r, "--note", "go", expect=2)
    check("8. the user's word is refused while the CRs are open",
          a in w.last_stderr and "not merged yet" in w.last_stderr, w.last_stderr)

    # a change of content: CR a gets a new round after the release PR is prepared
    settle(w)
    check("11. CR a goes back for a round", fm.take(a, "round: a change of content") == 0)
    w.chantier("agents", "set", r, "-", "--epoch", 1)
    code, _ = w.chantier("take", r, "--note", "redo: a changed", expect=2)
    check("11. the release is refused while CR a is not ready", code == 2 and a in w.last_stderr,
          w.last_stderr)
    driver_round(w, a, "piece0.py", "N = 10\n")
    w.ready(a, w.cr(a)["pr"])
    code, _ = w.chantier("take", r, "--note", "redo: a changed", expect=2)
    check("11. ready again but not restacked, it is refused still",
          code == 2 and "take stack" in w.last_stderr, w.last_stderr)
    restack(w, b, a)
    check("11. once restacked, the release is taken back with the `redo` note",
          fm.take(r, "redo: a changed") == 0 and w.cr(r)["status"] == "working")
    w.chantier("release", "start", r)
    check("11. `release start` keeps the PR recorded and counts an attempt",
          w.cr(r)["pr"] == pr and w.cr(r)["attempts"] == 2 and w.cr(r).get("head") is None,
          str(w.cr(r)))
    w.sh("git", "fetch", "--quiet", "origin", cwd=wt)
    w.sh("git", "rebase", "--quiet", f"origin/{top}", cwd=wt)
    w.chantier("gate", r, GATE)
    w.sh("git", "push", "--quiet", "--force-with-lease", "-u", "origin", w.cr(r)["branch"], cwd=wt)
    w.chantier("ship", r, pr)
    w.chantier("handback", r, "ready", f"{pr} draft on {top}: waits for the merge")
    settle(w)

    w.chantier("order", "merged", a)
    w.chantier("order", "merged", b)
    w.chantier("order", "approve", r, "--note", tag)
    code, out = w.chantier("release", "go", r, "--note", tag, expect=2)
    check("9. the stack merged, the release PR still is the user's to merge: `release go` "
          "is refused with an approval", code == 2 and "user's to merge" in out[0], str(out))
    w.chantier("order", "grant", r, "--note", "releases=1 budget=5")
    code, out = w.chantier("release", "go", r, "--note", tag)
    check("9. under a grant (`releases=1 budget=5`) it answers `go`",
          code == 0 and out[0].startswith("go:"), str(out))
    w.chantier("order", "grant", r, "--note", "releases=0 fixes=off budget=5")
    settle(w)

    w.chantier("order", "merged", r)
    fm.turn()
    steps = [w.chantier("release", "go", r, "--note", s)[1][0] for s in ("push the tag", "publish")]
    check("10. `order merged` puts the release back to `queued`, taken by a new Driver; "
          "`release go` answers `go` naming the merged PR for two steps, with no grant",
          fm.started[-1].startswith(f"{r} merged:") and w.cr(r)["status"] == "working"
          and all(s.startswith("go:") and pr in s for s in steps), str(steps))
    w.chantier("release", "published", r, "--note", "v1.8.0 https://forge.example/v1.8.0")
    w.chantier("handback", r, "ready", "https://forge.example/v1.8.0")
    fm.turn()
    check("10. the release `3-done`, the batch pauses",
          "/3-done/" in w.cr(r)["path"] and fm.paused, str(w.cr(r)))
    priced_foreman(w)
    w.chantier("close", "--batch", w.name, "--yes")

    # 12. a procedure with no release PR
    w.reset()
    items = [prepare_cr(w, t)[1] for t in ("Piece c", "Release v1.9.0")]
    w.start(*map(str, items), "--mode", "stack", "--release", 2, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman10", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    c, r = (x["id"] for x in w.batch()["crs"])
    fm.turn()
    driver_round(w, c, "piece_c.py", "N = 0\n")
    w.ready(c, w.cr(c)["pr"])
    on_branch(w, r, w.cr(c)["branch"])
    check("12. the release starts on the only CR's branch once it is ready", fm.take(r) == 0
          and any(f"base {w.cr(c)['branch']}" in ln for ln in fm.facts), str(fm.facts))
    w.chantier("handback", r, "blocked", "waits: the other CRs' merge, then the user's word "
               "to run the release procedure")
    w.chantier("order", "confirm", r, "--note", "yes, run it", expect=2)
    check("12. the user's word is refused before the other CRs' merge", c in w.last_stderr,
          w.last_stderr)
    w.chantier("order", "merged", c)
    w.chantier("order", "confirm", r, "--note", "yes, run it")
    code, out = w.chantier("release", "go", r, "--note", "tag v1.9.0")
    check("12. accepted after: `release go` answers `go` naming the word, and no `confirmed` "
          "field is written", code == 0 and "the user's word" in out[0] and "yes, run it" in out[0]
          and "confirmed" not in w.cr(r) and w.cr(r)["procedure"] == "yes, run it", str(out))

    # 15. a batch opened by the older CLI
    w.reset()
    _, old = prepare_cr(w, "Release v1.0.1")
    w.start(str(old), "--release", 1, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman11", "--epoch", 1)
    only = w.batch()["crs"][0]["id"]
    state = w.folder() / "batch.json"
    data = w.batch()
    data["crs"][0]["confirmed"] = "v1.0.1"
    data["crs"][0]["notes"] = ["merged: https://forge.example/pull/1"]
    state.write_text(json.dumps(data))
    code, out = w.chantier("release", "go", only, "--note", "tag v1.0.1", expect=2)
    check("15. a record with the older CLI's `confirmed` and `merged:` note gives no go: `ask`",
          code == 2 and out[0].startswith("no approval"), str(out))
    w.reset()

    # 13. a series
    items = [prepare_cr(w, t)[1] for t in ("Series one", "Series two", "Release v2.0.0")]
    w.start(*map(str, items), "--mode", "series", "--release", 3, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman12", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    one, two, r = (x["id"] for x in w.batch()["crs"])
    fm.turn()
    driver_round(w, one, "series1.py", "S = 1\n")
    w.ready(one, w.cr(one)["pr"])
    on_branch(w, two, w.cr(one)["branch"])
    fm.turn()
    code, _ = w.chantier("take", r, expect=2)
    refused = code == 2 and two in w.last_stderr
    driver_round(w, two, "series2.py", "S = 2\n")
    w.ready(two, w.cr(two)["pr"])
    on_branch(w, r, w.cr(two)["branch"])
    check("13. in a series, the release waits for the CRs, then starts on the second CR's branch",
          refused and fm.take(r) == 0
          and any(f"base {w.cr(two)['branch']}" in ln for ln in fm.facts), str(fm.facts))
    w.reset()
    w.env.pop("CHANTIER_BATCH", None)


def qa_on_head(w: World) -> None:
    note("\n## 14c. QA on the project's head, on the user's word, during the batch")
    _, item = prepare_cr(w, "Waits for its merge")
    w.reset()
    w.start(str(item), *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman6", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    cr = w.batch()["crs"][0]["id"]
    code, _ = w.chantier("order", "qa", expect=1)
    check("a QA says what to test", code == 1 and "what to test" in w.last_stderr, w.last_stderr)
    inbox = w.work / ".agents/changes/1-inbox"
    before = (sorted(p.name for p in inbox.glob("qa-*")), len(w.batch()["orders"]))
    state = w.folder() / "batch.json"
    state.write_text(json.dumps({**w.batch(), "budget_usd": 1, "spent_usd": 2}))
    code, _ = w.chantier("order", "qa", "--note", "try the export on a phone", expect=5)
    check("a spent budget refuses `order qa` (exit 5): no folder, no order",
          code == 5 and "budget" in w.last_stderr
          and (sorted(p.name for p in inbox.glob("qa-*")), len(w.batch()["orders"])) == before,
          w.last_stderr)
    w.chantier("order", "budget", "--note", "10")
    _, out = w.chantier("order", "qa", "--note", "try the export on a phone")
    check("a raised budget lets `order qa` through", len(w.batch()["orders"]) == before[1] + 2
          and len(list(inbox.glob("qa-*"))) == len(before[0]) + 1, str(out))
    shown = out[1].removeprefix("QA folder: ").split(";")[0]
    folder = w.work / shown
    check("`order qa` makes its work folder in the inbox, with the request, and names it",
          out[0] == f"[chief-of-staff→foreman] order O-2: qa {shown} try the export on a phone"
          and "/1-inbox/qa-" in folder.as_posix()
          and "phone" in (folder / "intake/request.md").read_text(encoding="utf-8"), str(out))
    code, _ = w.chantier("open", folder, *FROM_AGENTS_MD, expect=2)
    check("a QA folder is not opened: it is an item to triage and split",
          "QA report" in w.last_stderr and "triage" in w.last_stderr, w.last_stderr)
    fm.turn()
    check("the Foreman starts a QA driver on the folder, and the CR goes on without it",
          fm.qa == [shown] and fm.started == [cr] and w.cr(cr)["status"] == "working",
          str(fm.qa))
    code, _ = w.chantier("agents", "set", "O-2", "agent-qa", "--epoch", 1)
    check("`agents set O-<k>` maps a QA order to its agent", code == 0, w.last_stderr)
    code, _ = w.chantier("agents", "set", "O-1", "agent-x", "--epoch", 1, expect=1)
    check("`agents set` refuses an order that is not a QA", code == 1, w.last_stderr)
    _, out = w.chantier("status")
    check("`status` shows the QA order and its folder until it is done",
          any(ln.startswith(f"orders pending: O-2 qa {shown}") for ln in out), str(out))
    w.chantier("cancel", cr, "--epoch", 1)
    code, _ = w.chantier("pause", "--epoch", 1, expect=2)
    check("a batch does not pause under a running QA", code == 2 and "O-2" in w.last_stderr,
          w.last_stderr)
    (folder / "04-result.md").write_text("# QA\n\n- The export button is hidden on mobile\n")
    w.chantier("order", "done", "O-2", "--epoch", 1)
    w.chantier("pause", "--epoch", 1)
    priced_foreman(w)
    w.chantier("close", "--batch", w.name, "--yes")
    check("its findings stay in the inbox, an ordinary item",
          (folder / "04-result.md").is_file())
    w.chantier("abandon", folder)


def old_words(w: World) -> None:
    note("\n## 14d. A batch written with the old words: `open` and `landed`")
    _, item = prepare_cr(w, "Old words")
    w.reset()
    w.start(str(item), *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman_old", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    cr = w.batch()["crs"][0]["id"]
    state = w.folder() / "batch.json"

    def written(status: str, **more) -> None:
        d = w.batch()
        d["status"] = status
        d.update(more)
        state.write_text(json.dumps(d))

    # a batch recorded `open`: running for `status`, taken by `take`, stored as running
    written("open")
    _, out = w.chantier("status")
    check("a batch written with status open is reported running by `status`",
          out[0].split()[1] == "running", str(out))
    check("`take` takes a CR of a batch recorded open, and stores it as running",
          fm.take(cr) == 0 and w.batch()["status"] == "running"
          and '"open"' not in state.read_text(), w.last_stderr)
    w.chantier("cancel", cr, "--epoch", 1)
    priced_foreman(w)
    written("open")
    w.chantier("pause", "--epoch", 1)
    d = w.batch()
    check("`pause` pauses a batch recorded open as a running batch, and stores no open",
          d["status"] == "paused" and d.get("paused") and '"open"' not in state.read_text(),
          str(d.get("status")))

    # a batch recorded `landed` with a `landed` time: paused for `status` and for `close`
    d = w.batch()
    paused = d.pop("paused")
    state.write_text(json.dumps({**d, "status": "landed", "landed": paused}))
    _, out = w.chantier("status")
    check("a batch written with status landed is reported paused by `status`",
          out[0].split()[1] == "paused" and "paused, cost to date" in out[0], str(out))
    age_sessions(w)
    code, out = w.chantier("close", "--batch", w.name, expect=None)
    check("`close` treats a batch recorded landed as paused: it names what would go, deletes nothing",
          code == 0 and "not paused" not in w.last_stderr and (w.folder() / "batch.json").is_file(), w.last_stderr)
    w.chantier("status", "--refresh")
    text = state.read_text()
    d = w.batch()
    check("the next write through the CLI stores the new words: no `landed` key, no landed status",
          d["status"] == "paused" and d.get("paused") and "landed" not in d
          and '"landed"' not in text and '"open"' not in text, text[:300])
    w.chantier("close", "--batch", w.name, "--yes")


def changes_tree(w: World) -> None:
    note("\n## 14e. The changes tree: 3-ready, and the folder follows the status")
    w.reset()
    first = lambda out, word: w.work / out[0].removeprefix(word).split(";", 1)[0].rsplit(" (", 1)[0]  # noqa: E731
    _, spec = prepare_cr(w, "Tree with spec")
    _, out = w.chantier("file", "Tree without spec")
    bare = first(out, "filed ")
    _, out = w.chantier("triage", spec, "--ready")
    ready_spec = first(out, "triaged ")
    _, out = w.chantier("triage", bare, "--ready")
    ready_bare = first(out, "triaged ")
    check("`triage --ready` takes an item with a specification and one without, into 3-ready",
          ready_spec.parent == ready_bare.parent == w.state / "3-ready"
          and (ready_spec / "03-change-spec.md").is_file()
          and not (ready_bare / "03-change-spec.md").exists()
          and not spec.exists() and not bare.exists(), str(out))
    code, _ = w.chantier("triage", ready_spec, expect=None)
    check("`triage` wants a priority or --ready, one of them", code != 0 and ready_spec.is_dir())
    code, _ = w.chantier("triage", ready_spec, "--ready", expect=2)
    check("an item already in 3-ready is refused, not moved", code == 2 and ready_spec.is_dir(),
          w.last_stderr)
    _, out = w.chantier("triage", ready_spec, "--priority", "P2")
    back = first(out, "triaged ")
    check("`triage --priority P2` brings a 3-ready item back to the backlog",
          back.parent == w.state / "2-backlog" / "P2" and not ready_spec.exists(), str(out))
    w.chantier("triage", back, "--ready")
    _, bare_backlog = prepare_cr(w, "Tree backlog bare")
    (bare_backlog / "03-change-spec.md").unlink()
    code, _ = w.chantier("open", bare_backlog, *FROM_AGENTS_MD, expect=2)
    check("`open` still refuses a backlog item with no specification",
          code == 2 and bare_backlog.is_dir() and not (w.state / "4-batch/batch.json").exists(),
          w.last_stderr)
    w.chantier("abandon", bare_backlog)
    _, out = w.start(ready_spec, ready_bare, "--slots", 2, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    d = w.batch()
    one, two = d["crs"]
    check("`open` takes both 3-ready items into 1-pending; the one with no specification records "
          "the request as its specification",
          all("4-batch/1-pending/" in c["path"] for c in d["crs"])
          and one["specification"] == "03-change-spec.md"
          and two["specification"] == "intake/request.md" and two["title"].startswith("Tree without")
          and not ready_spec.exists() and not ready_bare.exists(), str(d["crs"]))
    w.chantier("foreman", "set", "local_foreman_tree", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    fm.take(two["id"])
    check("`take` moves the folder to 2-actives and shows the request as the specification",
          "4-batch/2-actives/" in w.cr(two["id"])["path"]
          and (w.state / w.cr(two["id"])["path"] / "intake/request.md").is_file()
          and any("intake/request.md" in ln for ln in fm.facts), str(fm.facts))
    fm.take(one["id"])
    driver_round(w, one["id"], "tree.py", "N = 1\n")
    w.ready(one["id"], w.cr(one["id"])["pr"])
    w.chantier("handback", two["id"], "blocked", "question: which one")
    check("the folder stays in 2-actives after `handback`, ready or blocked",
          all("4-batch/2-actives/" in w.cr(c["id"])["path"] for c in (one, two))
          and w.cr(one["id"])["status"] == "ready" and w.cr(two["id"])["status"] == "blocked")
    w.chantier("order", "merged", one["id"])
    done = w.state / w.cr(one["id"])["path"]
    check("`order merged` moves the folder to 3-done and records the merge time",
          done.parent == w.state / "4-batch" / "3-done" and done.is_dir()
          and w.cr(one["id"]).get("merged_at"), w.cr(one["id"])["path"])
    w.chantier("order", "drop", two["id"])
    dropped = w.state / w.cr(two["id"])["path"]
    check("`order drop` moves the folder to 6-trash at once",
          dropped.parent == w.state / "6-trash" and dropped.is_dir(), w.cr(two["id"])["path"])
    fm.turn()
    priced_foreman(w)
    age_sessions(w)
    stray = w.state / "4-batch" / "2-actives" / "stray"
    stray.mkdir()
    code, _ = w.chantier("close", "--batch", w.name, "--yes", expect=2)
    check("`close --yes` is refused while 2-actives holds a CR, and deletes nothing",
          code == 2 and "2-actives/stray" in w.last_stderr
          and (w.state / "4-batch/batch.json").is_file() and done.is_dir(), w.last_stderr)
    stray.rmdir()
    w.chantier("close", "--batch", w.name, "--yes")
    archived = [p for p in (w.state / "5-archives").iterdir() if p.name.endswith(f"-{done.name}")]
    page = (archived[0] / "STATUS.md").read_text(encoding="utf-8") if archived else ""
    check("`close` archives the 3-done CR as <merge time>-<number>-<slug>, its page saying the "
          "cost is final; the state folders stay, empty",
          len(archived) == 1 and re.fullmatch(r"\d{6}-\d{4}-" + re.escape(done.name), archived[0].name)
          and "so far" not in page and not done.exists()
          and sorted(p.name for p in (w.state / "4-batch").iterdir()) ==
          ["1-pending", "2-actives", "3-done"], str(archived))
    w.env.pop("CHANTIER_BATCH", None)


def old_tree(w: World) -> None:
    note("\n## 14f. A tree written in the older layout is converted in place, once")
    keep = w.root / "changes-keep"
    shutil.move(str(w.state), str(keep))
    try:
        w.chantier("init")
        (w.state / ".batch-number").write_text("80\n")  # no branch of the other batches is reused
        items = [prepare_cr(w, title)[1] for title in ("Old queued", "Old ready", "Old working")]
        w.start(*items, "--slots", 2, *FROM_AGENTS_MD)
        w.env["CHANTIER_BATCH"] = w.name
        w.chantier("foreman", "set", "local_foreman_old_tree", "--epoch", 1)
        fm = Foreman(w, epoch=1)
        queued, ready, working = (c["id"] for c in w.batch()["crs"])
        fm.take(ready)
        driver_round(w, ready, "old_tree.py", "N = 1\n")
        w.ready(ready, w.cr(ready)["pr"])
        fm.take(working)
        # write the older layout by hand: every CR in the batch folder, 4-archives, 5-trash
        d = w.batch()
        old = w.state / "3-requests" / w.name
        old.mkdir(parents=True)
        new = w.state / "4-batch"
        for p in list(new.iterdir()):
            if p.name not in ("1-pending", "2-actives", "3-done"):
                shutil.move(str(p), str(old / p.name))
        for stage in ("1-pending", "2-actives", "3-done"):
            for p in list((new / stage).iterdir()):
                shutil.move(str(p), str(old / p.name))
        shutil.rmtree(new)
        for name in ("5-archives", "6-trash"):
            shutil.rmtree(w.state / name)
        for stage, who in (("4-archives", "190-old-merged"), ("5-trash", "191-old-dropped")):
            (w.state / stage / f"260101-0000-{who}").mkdir(parents=True)
            (w.state / stage / f"260101-0000-{who}" / "01-intent.md").write_text(f"# {who}\n")
        for name in ("STATUS.md", "STATUS.json"):
            (w.state / name).unlink()
            (w.state / "3-requests" / name).write_text("older index\n")
        for c in d["crs"]:
            c["path"] = f".agents/changes/3-requests/{w.name}/{Path(c['path']).name}"
        for n, (status, stage) in enumerate((("merged", "4-archives"), ("cancelled", "5-trash")), 190):
            d["crs"].append({**d["crs"][0], "id": f"CR-{n}", "status": status, "order": 90 + n,
                             "path": f".agents/changes/{stage}/260101-0000-{n}-old-"
                                     f"{'merged' if n == 190 else 'dropped'}"})
        (old / "batch.json").write_text(json.dumps(d), encoding="utf-8")
        before = (old / "batch.json").read_bytes()
        # a tree with both 4-archives and a non-empty 5-archives is refused, nothing moved
        (w.state / "5-archives" / "x").mkdir(parents=True)
        (w.state / "5-archives" / "x" / "f.txt").write_text("kept")
        code, _ = w.chantier("status", expect=2)
        check("an older tree whose target holds files exits 2, naming both folders, nothing moved",
              code == 2 and "4-archives" in w.last_stderr and "5-archives" in w.last_stderr
              and (old / "batch.json").read_bytes() == before
              and (w.state / "4-archives/260101-0000-190-old-merged").is_dir()
              and (w.state / "5-archives/x/f.txt").is_file(), w.last_stderr)
        shutil.rmtree(w.state / "5-archives")
        code, out = w.chantier("status")
        converted = w.last_stderr
        d = w.batch()
        paths = {c["id"]: c["path"] for c in d["crs"]}
        check("the next command converts the tree, says so once, and every recorded path exists",
              converted.startswith("converted .agents/changes to the new tree")
              and all(w.at(p).is_dir() for p in paths.values()), converted)
        check("queued goes to 1-pending, ready to 2-actives, working stays; archives and trash "
              "are renamed",
              "4-batch/1-pending/" in paths[queued] and "4-batch/2-actives/" in paths[ready]
              and paths[working] == f".agents/changes/3-requests/{w.name}/{Path(paths[working]).name}"
              and "5-archives/" in paths["CR-190"] and "6-trash/" in paths["CR-191"]
              and not (w.state / "4-archives").exists() and not (w.state / "5-trash").exists()
              and (w.state / "STATUS.json").is_file(), str(paths))
        w.chantier("status")
        check("a second command converts nothing", "converted" not in w.last_stderr, w.last_stderr)
        driver_round(w, working, "old_tree2.py", "N = 2\n")
        w.ready(working, w.cr(working)["pr"])
        w.chantier("order", "merged", working)
        check("the working CR moves to 3-done on `order merged`, and 3-requests/ is gone",
              "4-batch/3-done/" in w.cr(working)["path"]
              and not (w.state / "3-requests").exists(), w.cr(working)["path"])
        index = json.loads((w.state / "STATUS.json").read_text(encoding="utf-8"))
        check("the index at .agents/changes/STATUS.json has schema 3 and paths that resolve",
              index["schema"] == 3 and all((w.state / r["folder"]).is_dir()
                                           for b in index["batches"] for r in b["crs"])
              and all((w.state / e["path"]).is_dir() for e in index["merged"]), str(index)[:300])
    finally:
        w.env.pop("CHANTIER_BATCH", None)
        shutil.rmtree(w.state, ignore_errors=True)
        shutil.move(str(keep), str(w.state))
        subprocess.run(["git", "worktree", "prune"], cwd=w.work, capture_output=True)

def depends_on(item: Path, *slugs: str, raw: str | None = None) -> None:
    """The Chief of Staff's `depends.json`, in the CR's folder."""
    (item / "depends.json").write_text(raw if raw is not None else json.dumps({"after": list(slugs)}),
                                       encoding="utf-8")


def drawn(w: World, cr: str) -> tuple[set[str], dict]:
    """The label of a CR in every record that lists it (the batch's STATUS.md and STATUS.json,
    the index where it is active, the CR's own pair), and the CR's own STATUS.json."""
    own_dir = w.state / w.cr(cr)["path"]
    own = json.loads((own_dir / "STATUS.json").read_text(encoding="utf-8"))
    batch = json.loads((w.folder() / "STATUS.json").read_text(encoding="utf-8"))
    index = json.loads((w.state / "STATUS.json").read_text(encoding="utf-8"))
    labels = {own["label"]} | {r["label"] for r in batch["crs"] if r["cr"] == cr}
    labels |= {r["label"] for b in index["batches"] for r in b["crs"] if r["cr"] == cr}
    texts = [(w.folder() / "STATUS.md").read_text(encoding="utf-8"),
             (own_dir / "STATUS.md").read_text(encoding="utf-8")]
    return {lb for lb in labels if all(lb in t for t in texts)} | {
        "MISSING " + lb for lb in labels if not all(lb in t for t in texts)}, own


def icon_is(w: World, cr: str, icon: str, what: str) -> dict:
    labels, own = drawn(w, cr)
    check(f"{what}: {icon} in STATUS.md and STATUS.json, at every level",
          len(labels) == 1 and next(iter(labels)).startswith(icon + " "), str(labels))
    return own


def dependencies(w: World) -> None:
    note("\n## 14d. A CR declares what it depends on; a slot is a running Driver")
    one, two = prepare_cr(w, "Cycle one")[1], prepare_cr(w, "Cycle two")[1]
    depends_on(one, two.name)
    depends_on(two, one.name)
    w.reset()
    code, _ = w.start(str(one), str(two), expect=2)
    check("a cycle is refused at `open`, naming it; nothing is opened or moved",
          code == 2 and "cycle" in w.last_stderr and one.is_dir() and two.is_dir()
          and not list((w.state / "4-batch").glob("batch.json")), w.last_stderr)
    depends_on(two, "no-such-cr")
    code, _ = w.start(str(two), expect=2)
    check("an unknown slug is refused, named", code == 2 and "no-such-cr" in w.last_stderr
          and two.is_dir(), w.last_stderr)
    depends_on(two, raw="{not json")
    code, _ = w.start(str(two), expect=2)
    check("a malformed `depends.json` is refused", code == 2 and "depends.json" in w.last_stderr
          and two.is_dir(), w.last_stderr)

    base_, next_ = prepare_cr(w, "Dep base")[1], prepare_cr(w, "Dep next")[1]
    depends_on(next_, base_.name)
    w.start(str(base_), str(next_), "--slots", 3, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    a, b = (c["id"] for c in w.batch()["crs"])
    check("`open` records `after` as CR ids", w.cr(b).get("after") == [a] and "after" not in w.cr(a),
          str(w.batch()["crs"]))
    icon_is(w, a, "⚪", "a queued CR with a free slot")
    icon_is(w, b, "🟠", "a queued CR with `waits`")
    _, out = w.chantier("status")
    check("`status` shows what a queued CR waits for",
          any(ln.startswith(b) and f"waits for {a} queued" in ln for ln in out), str(out))
    board = json.loads((w.state / "4-batch" / "STATUS.json").read_text(encoding="utf-8"))
    check("the STATUS files name what a queued CR waits for, as `status` does",
          any(r["cr"] == b and r["waits"] == [f"{a} queued"] and f"waits for {a} queued" in r["label"]
              for r in board["crs"]), str(board["crs"]))
    code, _ = w.chantier("take", b, expect=2)
    check("a CR is refused until its dependency is ready, and the refusal names it",
          code == 2 and f"waits for {a} queued" in w.last_stderr and w.cr(b)["status"] == "queued",
          w.last_stderr)
    w.chantier("take", a)
    start_driver(w, a)
    code, _ = w.chantier("take", b, expect=2)
    check("a working dependency is not enough", code == 2 and f"{a} working" in w.last_stderr,
          w.last_stderr)
    driver_round(w, a, "dep_a.py", "A = 1\n")
    w.ready(a, w.cr(a)["pr"])
    _, out = w.chantier("take", b)
    check("once it is ready, the dependent starts on its branch (even in a parallel batch)",
          any(f"base {w.cr(a)['branch']}" in ln for ln in out), str(out))
    w.chantier("order", "merged", a)
    _, out = w.chantier("handoff", b)
    check("when the dependency is merged, the base is the default branch",
          any("base origin/main" in ln for ln in out), str(out))
    after_archive = prepare_cr(w, "Dep late")[1]
    depends_on(after_archive, base_.name)
    _, out = w.chantier("order", "add", "--note", str(after_archive))
    late = w.batch()["crs"][-1]
    check("a dependency already archived as merged is met and not recorded",
          "after" not in late and late["status"] == "queued"
          and w.chantier("take", late["id"])[0] == 0, str(out))
    cancelled = prepare_cr(w, "Dep dropped")[1]
    w.chantier("order", "add", "--note", str(cancelled))
    dropped = w.batch()["crs"][-1]["id"]
    w.chantier("order", "drop", dropped)
    icon_is(w, dropped, "⚪", "a dropped CR")
    waiting = prepare_cr(w, "Dep waiting")[1]
    depends_on(waiting, cancelled.name)
    w.chantier("order", "add", "--note", str(waiting))
    code, _ = w.chantier("take", w.batch()["crs"][-1]["id"], expect=2)
    check("a cancelled dependency stays unmet", code == 2 and f"{dropped} cancelled" in w.last_stderr,
          w.last_stderr)

    w.reset()
    s1, s2 = prepare_cr(w, "Stack first")[1], prepare_cr(w, "Stack second")[1]
    depends_on(s2, s1.name)
    w.start(str(s1), str(s2), "--mode", "stack", *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    x, y = (c["id"] for c in w.batch()["crs"])
    code, _ = w.chantier("stack", y, x, expect=2)
    check("a stack order that puts a CR below its dependency is refused",
          code == 2 and x in w.last_stderr and w.batch()["crs"][0]["order"] == 1, w.last_stderr)
    code, _ = w.chantier("stack", x, y)
    check("the order that respects it is taken", code == 0)
    _, out = w.chantier("order", "after", y, "--note", "-")
    check("`order after` with `-` frees a queued CR; it is logged and printed for the Foreman",
          "after" not in w.cr(y) and out[0].startswith("[chief-of-staff→foreman] order O-1: after")
          and w.batch()["orders"][-1]["kind"] == "after" and len(w.batch()["crs"]) == 2
          and any("base origin/main" in ln for ln in w.chantier("handoff", y)[1]), str(out))
    _, out = w.chantier("order", "after", y, "--note", x)
    check("`order after` replaces the dependencies of a queued CR, with no new number",
          w.cr(y).get("after") == [x] and len(w.batch()["crs"]) == 2
          and w.chantier("take", y, expect=2)[0] == 2 and f"waits for {x} queued" in w.last_stderr,
          str(out))
    code, _ = w.chantier("order", "after", x, "--note", y, expect=2)
    check("`order after` refuses a cycle and changes nothing", code == 2 and "cycle" in w.last_stderr
          and "after" not in w.cr(x) and w.cr(y).get("after") == [x], w.last_stderr)
    code, _ = w.chantier("order", "after", "CR-999", "--note", x, expect=2)
    check("`order after` refuses an unknown CR", code == 2 and "CR-999" in w.last_stderr, w.last_stderr)
    code, _ = w.chantier("order", "after", y, "--note", "CR-999", expect=2)
    check("`order after` refuses an unknown dependency, and keeps the old one",
          code == 2 and "CR-999" in w.last_stderr and w.cr(y).get("after") == [x], w.last_stderr)
    w.chantier("take", x)
    code, _ = w.chantier("order", "after", x, "--note", "-", expect=2)
    check("`order after` refuses a CR that is not queued", code == 2 and "queued" in w.last_stderr,
          w.last_stderr)

    w.reset()
    q1, q2 = prepare_cr(w, "Slot one")[1], prepare_cr(w, "Slot two")[1]
    w.start(str(q1), str(q2), "--slots", 2, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    c1, c2 = (c["id"] for c in w.batch()["crs"])
    w.chantier("take", c1)
    w.chantier("order", "qa", "--note", "try it")
    check("an open QA order holds a slot: `status` counts it",
          w.chantier("status")[1][0].split(" live ")[1].startswith("2/2"), str(w.last_out))
    code, _ = w.chantier("take", c2, expect=2)
    check("with the QA driver and a CR, no slot is free for the next", code == 2
          and "no free slot" in w.last_stderr and "O-1 qa" in w.last_stderr, w.last_stderr)
    icon_is(w, c1, "🟡", "a working CR")
    icon_is(w, c2, "🟠", "a queued CR with no free slot (a QA order holds the last one)")
    code, _ = w.chantier("order", "qa", "--note", "again", expect=2)
    check("a second QA order is refused too: its driver would have no slot",
          code == 2 and "no free slot" in w.last_stderr, w.last_stderr)
    w.chantier("order", "done", "O-1")
    icon_is(w, c2, "⚪", "a queued CR once `order done` frees the slot")
    state = w.folder() / "batch.json"
    w.chantier("order", "budget", "--note", "10")
    state.write_text(json.dumps({**w.batch(), "spent_usd": 2}))
    w.chantier("order", "budget", "--note", "1")
    icon_is(w, c2, "🟠", "a queued CR on a spent budget (`take` refuses it)")
    w.chantier("order", "budget", "--note", "10")
    icon_is(w, c2, "⚪", "a queued CR once the budget is raised")
    code, _ = w.chantier("take", c2)
    check("the QA driver's end frees its slot", code == 0)
    start_driver(w, c2)
    w.chantier("handback", c2, "blocked", "waits: the stack driver")
    own = icon_is(w, c2, "🟠", "a CR blocked with `waits:`")
    check("`waits:` keeps severity red and its Next names the thing, not the user's answer",
          own["severity"] == "red" and own["label"] == "🟠 blocked Waits 1/3"
          and "the stack driver" in own["next"] and "user's answer" not in own["next"], str(own))
    w.chantier("take", c2, "--note", "the stack driver landed")
    w.chantier("handback", c2, "blocked", "question: which one?")
    icon_is(w, c2, "🔴", "a CR blocked for any other reason")
    start_driver(w, c1)
    driver_round(w, c1, "icons_one.py", "ONE = 1\n")
    w.ready(c1, w.cr(c1)["pr"])
    icon_is(w, c1, "🔵", "a ready CR")
    w.chantier("order", "merged", c1)
    icon_is(w, c1, "✅", "a merged CR")
    w.env.pop("CHANTIER_BATCH", None)


def release_merge_on_approval(w: World) -> None:
    note("\n## 15. A release PR is the user's to merge: no approval covers it")
    _, version = prepare_cr(w, "Release v1.2.0")
    w.reset()
    w.start(str(version), "--release", 1, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman4", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    fm.turn()
    rel = w.batch()["crs"][0]["id"]
    w.chantier("release", "start", rel)
    commit(w, rel, "VERSION", "1.2.0\n", "release: v1.2.0")
    w.chantier("gate", rel, GATE)
    ship(w, rel, "release: v1.2.0")
    pr = w.cr(rel)["pr"]
    w.chantier("handback", rel, "ready", pr)
    fm.turn()
    check("without a grant, the prepared release PR goes to the user, never to a merge",
          fm.asked[-1] == f"ready {rel} {pr}" and w.cr(rel)["status"] == "ready", str(fm.asked))
    drivers = len(fm.started)
    w.chantier("order", "approve", rel, "--note", f"merge the release PR {pr}")
    for o in w.batch()["orders"]:
        if not o["done"]:
            w.chantier("order", "done", o["id"], "--epoch", 1)
    code, out = w.chantier("release", "go", rel, "--note", f"merge the release PR {pr}", expect=2)
    check("an approval never lets the Foreman merge a release PR",
          code == 2 and out[0].startswith("no: the release PR") and len(fm.started) == drivers
          and not any(a.startswith(f"merged {rel} ") for a in fm.asked), str(out))
    w.chantier("order", "merged", rel)
    fm.turn()
    check("the user's merge starts the next Driver, which goes on",
          len(fm.started) == drivers + 1 and w.cr(rel)["status"] == "working", str(fm.started))
    w.chantier("handback", rel, "ready", "v1.2.0")
    fm.turn()
    check("the batch pauses", fm.paused)
    last = w.folder()
    priced_foreman(w)
    if sys.platform == "win32":  # elsewhere a file in use does not stop a rename
        with open(last / "STATUS.md", encoding="utf-8"):
            code, _ = w.chantier("close", "--batch", w.name, "--yes", expect=None)
        check("`close` on a folder in use deletes nothing and can run again",
              code != 0 and "in use" in w.last_stderr and (last / "batch.json").is_file(),
              w.last_stderr)
    w.chantier("close", "--batch", w.name, "--yes")
    w.number_after = int(w.name.split("-")[1]) + 1


def lost_messages(w: World) -> None:
    note("\n## 16. Lost messages: the wake catches up, and nothing is left unsaid")
    titles = ("Lost one", "Lost two", "Lost three")
    prepared = [prepare_cr(w, title)[1] for title in titles]
    w.reset()
    w.start(*(str(p) for p in prepared), "--slots", 3, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    check("batch numbers go on rising after the last batch's folder is deleted",
          w.name == f"batch-{w.number_after:02d}", w.name)
    w.chantier("foreman", "set", "local_foreman5", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    fm.turn()
    one, two, three = (c["id"] for c in w.batch()["crs"])
    check("a date in the trash is not a CR number", len(one) == len("CR-101"), one)

    _, out = w.chantier("order", "note", three, "--note", "first")  # its line never reaches the Foreman
    order = out[0].split()[2].rstrip(":")
    _, out = w.chantier("status", "--refresh", "--epoch", 1, expect=None)
    check("a wake shows the order whose line never came, and records the heartbeat",
          any(ln.startswith(f"orders pending: {order} note {three} first") for ln in out)
          and "live 3/3" in out[0] and w.batch()["heartbeat"], str(out))
    fm.turn()
    check("the Foreman tells the Driver and marks the order done",
          all(o["done"] for o in w.batch()["orders"])
          and any(m == f"{three} first" for m in fm.messages), str(fm.messages))
    check("the line that arrives late changes nothing",
          w.chantier("order", "done", order, "--epoch", 1)[1] == [f"{order} already done"])

    driver_round(w, one, "lost.py", f"WHO = '{one}'\n")
    w.ready(one, w.cr(one)["pr"])
    fm.turn()
    check("a ready CR is told", fm.asked[-1].startswith(f"ready {one} "))
    driver_round(w, two, "lost.py", f"WHO = '{two}'\n")
    w.sh("git", "push", "--quiet", "origin", f"{w.cr(one)['branch']}:main")  # the user merges
    _, out = w.ready(two, w.cr(two)["pr"])
    check("a hand-back records what the Driver says; whether the PR still merges is the "
          "Foreman's to notice with the forge's CLI", w.cr(two)["status"] == "ready", str(out))
    _, out = w.chantier("status", "--refresh", "--epoch", 1, expect=None)
    check("a wake names the activity of each working CR and says what it knows of the spend",
          any(ln.startswith(f"activity {three} ") for ln in out)
          and not any("longest silent" in ln for ln in out)
          and any(ln.startswith(("spent $", "spend not updated")) for ln in out), str(out))
    driver_round(w, three, "other.py", "OTHER = True\n")
    w.ready(three, w.cr(three)["pr"])
    fm.turn()

    _, out = w.chantier("status")
    check("status counts the asks unread", any("asks unread" in ln for ln in out), str(out))
    _, out = w.chantier("asks", "refused", one, "the", "host", "said", "no")
    check("the Foreman's own ask is recorded and printed, with its id",
          re.fullmatch(rf"\[foreman→chief-of-staff\] ask A-\d+: refused {one} the host said no",
                       out[0]), str(out))
    _, out = w.chantier("asks")
    check("`asks` gives every ask still unread, sent or not",
          out[0].startswith(f"A-1: ready {one} ")
          and out[-1].endswith(f"refused {one} the host said no"), str(out))
    first_id = out[0].split(":")[0]
    _, out = w.chantier("asks", "--read", first_id)
    check("one ask is marked heard", out == ["read 1"], str(out))
    _, out = w.chantier("asks")
    check("the others stay", out and not out[0].startswith("A-1:"), str(out))
    w.chantier("asks", "--read", "all")
    _, out = w.chantier("asks")
    check("an ask is read once", out == ["no unread ask"], str(out))


def lifecycle_regressions(w: World) -> None:
    note("\n## 12. Lifecycle recovery")
    w.reset()
    _, original = prepare_cr(w, "Preserve failed opening")
    code, _ = w.chantier("open", str(original), "--remote", "nowhere",
                         *FROM_AGENTS_MD, expect=4)
    check("a remote Git does not know is refused before anything moves",
          code == 4 and "nowhere" in w.last_stderr and (original / "03-change-spec.md").is_file()
          and not list((w.state / "4-batch").glob("batch.json")), w.last_stderr)
    check("chantier wrote nothing outside .agents/changes",
          all(line[3:].startswith(".agents/changes/")
              for line in w.sh("git", "status", "--porcelain", "-uall").splitlines()))


def copilot_cost(w: World, d: dict) -> None:
    assigned = next((c for c in d["crs"] if c.get("agent")), None)
    if not assigned:
        check("Copilot cost has a Driver to attribute", False)
        return
    named = next(c for c in d["crs"] if c["id"] != assigned["id"])
    home = w.root / "copilot-home"
    events = home / "session-state" / "uuid-foreman" / "events.jsonl"
    events.parent.mkdir(parents=True)
    agents = [(assigned["agent"], "cr-driver", "driver"),
              ("cost-coder", "coder", f"{named['id']} coder")]
    events.write_text("".join(json.dumps(
        {"type": "subagent.started", "agentId": agent,
         "data": {"agentType": role, "agentDisplayName": name}}) + "\n"
        for agent, role, name in agents), encoding="utf-8")

    def call(agent, usd, source="billed", role=None):
        return {"agent_id": agent, "agent": role, "model": "gpt-5.6-luna", "llm_calls": 1,
                "estimated_usd": usd, "cost_source": source}

    records = w.root / "copilot-usage.jsonl"
    calls = [call(None, 1.0), call(assigned["agent"], 0.5),
             call("cost-coder", 0.25, "estimated"), call("unmapped", 0.125, role="coder")]
    records.write_text("".join(json.dumps(c) + "\n" for c in calls), encoding="utf-8")
    fake_args = [sys.executable, str(FAKE_USAGE)]
    fake_command = subprocess.list2cmdline(fake_args) if sys.platform == "win32" \
        else shlex.join(fake_args)
    env = {"COPILOT_HOME": str(home), "CHANTIER_SESSION_USAGE": fake_command,
           "FAKE_USAGE_RECORDS": str(records), "FAKE_USAGE_SESSION": "uuid-foreman",
           "FAKE_USAGE_EXIT": "0", "FAKE_USAGE_ERROR": "",
           "UV_INDEX": "https://example.invalid/simple",
           "FAKE_EXPECT_UV_INDEX": "https://example.invalid/simple"}
    # the batch ran on Claude: for this section, its file says Copilot
    state = w.folder() / "batch.json"
    claude = state.read_text()
    state.write_text(json.dumps({**json.loads(claude), "host": "copilot"}))
    code, out = w.chantier("cost", "--batch", w.name, env=env)
    check("Copilot cost lists the Foreman, then each agent type: no parent link, so Driver or "
          "worker is not told",
          code == 0 and out == [
              f"{w.name}: $1.875 over 4 model calls (1 estimated, not billed)",
              "Foreman: $1.000 (1 calls, 53%)", "Agent cr-driver: $0.500 (1 calls, 27%)",
              "Agent coder: $0.375 (2 calls, 20%)",
              "Orchestration (steering + Drivers): not measured (no parent link on this host)",
              "Chief of Staff, steering the batch (outside the budget): unknown: not measured on this host",
              "Chief of Staff, grill and specifications with the user (outside the budget): unknown: not measured on this host",
              "Chief of Staff, whole session: unknown: not measured on this host; compactions: not measured on this host"] and "$0.00" not in "\n".join(out[-3:]), str(out))
    code, out = w.chantier("cost", "--explain", "--batch", w.name, env=env)
    check("Copilot cost --explain says `not measured` where the host gives no detail",
          code == 0 and out[2].count("not measured") == 1 and "restarts: not measured" in out[4]
          and out[-2:] == ["Cache expiry: not measured on this host",
                           "Not counted: compaction calls are not measured on this host"],
          str(out))
    code, out = w.chantier("cost", "--batch", w.name, "--by", "cr", env=env)
    check("Copilot cost attributes calls by agent, name and other",
          code == 0 and out[1:] == [
              "foreman: $1.000 (1 calls)", f"{assigned['id']}: $0.500 (1 calls)",
              f"{named['id']}: $0.250 (1 calls)", "other: $0.125 (1 calls)",
              "Chief of Staff, steering the batch (outside the budget): unknown: not measured on this host",
              "Chief of Staff, grill and specifications with the user (outside the budget): unknown: not measured on this host",
              "Chief of Staff, whole session: unknown: not measured on this host; compactions: not measured on this host"], str(out))

    def fails(label, expected, message, overrides=None):
        code, out = w.chantier("cost", "--batch", w.name, env={**env, **(overrides or {})},
                               expect=expected)
        check(label, code == expected and not out and message in w.last_stderr,
              f"exit {code}, stdout {out}, stderr {w.last_stderr}")

    records.write_text("", encoding="utf-8")
    fails("Copilot cost refuses empty usage", 4, "no priced call")
    fails("Copilot cost reports a failed usage command", 4, "failed (1): boom",
          {"FAKE_USAGE_EXIT": "1", "FAKE_USAGE_ERROR": "boom"})
    records.write_text(json.dumps(call(None, None)) + "\n", encoding="utf-8")
    fails("Copilot cost refuses a call without a price", 4, "has no price")
    records.write_text("not JSON\n", encoding="utf-8")
    fails("Copilot cost refuses unreadable records", 4, "unreadable record")
    missing = [str(w.root / "missing-session-usage")]
    missing_command = subprocess.list2cmdline(missing) if sys.platform == "win32" \
        else shlex.join(missing)
    fails("Copilot cost reports a missing command", 2, "not found",
          {"CHANTIER_SESSION_USAGE": missing_command})
    state.write_text(claude)


def copilot_missing_transcript(w: World) -> None:
    w.reset()
    _, missing = prepare_cr(w, "Missing transcript")
    w.start(str(missing), *FROM_AGENTS_MD, env={"CHANTIER_HOST": "copilot"})
    code, out = w.chantier("cost", "--batch", w.name, env={"COPILOT_HOME": str(w.root / "copilot-home")},
                           expect=2)
    check("a missing Copilot transcript names the session variable",
          code == 2 and not out and "$COPILOT_AGENT_SESSION_ID" in w.last_stderr,
          f"exit {code}, stdout {out}, stderr {w.last_stderr}")


def copilot_uv(w: World) -> None:
    sys.path.insert(0, str(SKILL / "scripts" / "cli" / "src"))
    try:
        from chantier import costs
    finally:
        sys.path.pop(0)
    index_variables = ("UV_INDEX", "UV_DEFAULT_INDEX", "UV_INDEX_URL", "UV_EXTRA_INDEX_URL",
                       "UV_FIND_LINKS")
    env = {name: "https://example.invalid/simple" for name in index_variables}
    env.update({"CHANTIER_SESSION_USAGE": "", "COPILOT_HOME": str(w.root / "empty-copilot"),
                "UV_OFFLINE": "1", "HTTPS_PROXY": "http://127.0.0.1:9",
                "SSL_CERT_FILE": str(w.root / "cert.pem")})
    result = subprocess.CompletedProcess([], 0, stdout=json.dumps(
        {"estimated_usd": 1.0, "llm_calls": 1, "cost_source": "billed"}) + "\n", stderr="")
    with mock.patch.dict(os.environ, env), mock.patch.object(costs.shutil, "which", return_value="uv"), \
            mock.patch.object(costs.subprocess, "run", return_value=result) as run:
        costs.copilot_session_costs("uuid-foreman")
        argv = run.call_args.args[0]
        child_env = run.call_args.kwargs["env"]
        check("Copilot cost invokes uv with the inline script and exact session",
              argv == ["uv", "run", "--no-config", "--script", str(costs.SESSION_USAGE_SCRIPT),
                       "--agent", "cli", "--session-root",
                       str(Path(env["COPILOT_HOME"]) / "session-state"),
                       "calls", "--name", r"^uuid\-foreman$"], str(argv))
        check("uv ignores inherited index sources but retains offline and proxy settings",
              child_env is not None and all(name not in child_env for name in index_variables)
              and child_env.get("UV_OFFLINE") == "1"
              and child_env.get("HTTPS_PROXY") == "http://127.0.0.1:9"
              and child_env.get("SSL_CERT_FILE") == env["SSL_CERT_FILE"]
              and all(os.environ.get(name) == env[name] for name in index_variables))


def cost_audit(w: World) -> None:
    """The window of a batch's cost: a relay's sum, a reused Foreman, a Driver of an unknown type."""
    slug = "".join(ch if ch.isalnum() else "-" for ch in str(w.work.resolve()))
    main = w.root / "claude-projects" / slug / "uuid-foreman.jsonl"
    state = w.folder() / "batch.json"
    original, original_state = main.read_text(), state.read_text()

    def msg(mid, out, **fields):
        return json.dumps({"type": "assistant", **fields, "message": {
            "id": mid, "model": "claude-sonnet-5-5", "usage": {
                "input_tokens": 10, "output_tokens": out, "cache_read_input_tokens": 20_000,
                "cache_creation": {"ephemeral_1h_input_tokens": 2_000}}}}) + "\n"

    # `pause` ends no window: a call made after it is spend, and a `<synthetic>` record costs nothing
    main.write_text(original + msg("later", 900_000, timestamp="2999-01-01T00:00:00.000Z"))
    code, out = w.chantier("cost", "--batch", w.name)
    check("a call made after the pause is counted, and a `<synthetic>` record costs nothing",
          code == 0 and out[0].startswith(f"{w.name}: $10.6") and "over 95 model calls" in out[0],
          str(out))
    main.write_text(original)
    # a relay: the next Foreman's transcript is summed with the first
    main.with_name("uuid-foreman-2.jsonl").write_text(msg("r1", 300) + msg("r2", 300))
    d = json.loads(original_state)
    state.write_text(json.dumps({**d, "foreman_transcripts": ["uuid-foreman", "uuid-foreman-2"]}))
    code, out = w.chantier("cost", "--batch", w.name)
    check("a relay's Foreman transcripts are summed", code == 0
          and out[0] == f"{w.name}: $1.634 over 96 model calls", str(out))
    state.write_text(original_state)
    main.write_text(original)
    # the fixture: the Foreman, Drivers with workers (cr-driver), a Driver with none (qa-driver) and
    # a root agent of a type nobody knows (my-own-driver, with a worker); each gets its own line
    sub = main.with_suffix("") / "subagents"
    created = datetime.fromisoformat(json.loads(original_state)["created"].replace("Z", "+00:00"))
    when = [(created + timedelta(seconds=s)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            for s in (10, 2 * 3600)]  # two hours apart: the 1-hour cache has expired
    events = w.folder() / "events.jsonl"
    original_events = events.read_text(encoding="utf-8")
    events.write_text(original_events + json.dumps(  # a Driver after another on CR-101
        {"t": when[0], "actor": "foreman", "kind": "agent", "cr": "CR-101", "agent": "odd"}) + "\n"
        + json.dumps(  # a QA driver, recorded by `agents set O-<k>`: a Driver, not the Foreman's own
            {"t": when[0], "actor": "foreman", "kind": "agent", "cr": "O-1", "agent": "lone"}) + "\n",
        encoding="utf-8")
    for name, kind, parent, n in (("odd", "my-own-driver", None, 2), ("odd-worker", "coder", "odd", 1),
                                  ("lone", "qa-driver", None, 3)):
        f = sub / f"agent-{name}.jsonl"
        f.write_text("".join(msg(f"{name}{i}", 900, **({"timestamp": when[i]} if name == "odd" else {}))
                             for i in range(n)))
        f.with_suffix("").with_suffix(".meta.json").write_text(
            json.dumps({"agentType": kind, **({"parentAgentId": parent} if parent else {})}))
    code, out = w.chantier("cost", "--batch", w.name)
    lines = [l for l in out[1:] if l.startswith(("Foreman", "Driver", "Worker", "Agent"))]
    check("`cost` shows the Foreman, each Driver type and each worker type on its own line, in "
          "that order, with their own calls",
          code == 0 and [l.split(":")[0] for l in lines] == [
              "Foreman", "Driver cr-driver", "Driver qa-driver", "Driver my-own-driver",
              "Worker coder"]
          and "Driver cr-driver: $0.913 (48 calls, 53%)" in out
          and "Worker coder: $0.323 (17 calls, 19%)" in out
          and "Driver my-own-driver: $0.038 (2 calls, 2%)" in out
          and "Orchestration (steering + Drivers): 81% of the batch's spend" in out, str(out))
    printed = [int(a.replace(".", "")) for l in lines for a in re.findall(r"\$(\d+\.\d{3}) \(", l)]
    check("the lines add up to the total as printed", out[0] == f"{w.name}: $1.722 over 100 model calls"
          and sum(printed) == 1722, str(out))
    code, out = w.chantier("cost", "--explain", "--batch", w.name)
    text = "\n".join(out)
    shares = [int(s) for s in re.findall(r"(?:reads|writes|output|input) (\d+)%", out[2])]
    check("`cost --explain` gives, per line, the agents, the model, the shares of cost, the calls "
          "after the cache expired and the restarts", code == 0
          and out[2].startswith("  1 agent, 30 calls; model claude-sonnet-5-5; cost: cache reads")
          and len(shares) == 4 and sum(shares) == 100
          and "no timestamps" in out[2] and "4 agents, 48 calls" in text
          and "1 of 1 timed calls after the cache expired; 1 restarted on a CR that already had one"
          in text and "0 restarted on a CR that already had one" in text, str(out))
    check("`cost --explain` says the lifetime it used and ends with what the figures do not count",
          "5 min after a 5-minute cache write, 1 h after a 1-hour one" in out[-2]
          and out[-1] == "Not counted: 0 compaction calls, which leave no record (about $0.12 each, $0.00)",
          str(out))
    foreman_transcript = main.read_text()
    main.write_text(foreman_transcript + json.dumps(
        {"type": "system", "subtype": "compact_boundary", "timestamp": when[0]}) + "\n")
    code, out = w.chantier("cost", "--explain", "--batch", w.name)
    check("a compaction boundary is counted in what the figures do not count",
          out[-1].startswith("Not counted: 1 compaction calls") and "$0.12 each, $0.12" in out[-1],
          str(out))
    main.write_text(foreman_transcript)
    code, out = w.chantier("cost", "--by", "cr", "--batch", w.name)
    crs = [int(a.replace(".", "")) for l in out[1:-1] for a in re.findall(r"\$(\d+\.\d{3}) \(", l)]
    check("`cost --by cr` still adds up to the Drivers and workers, the Foreman first among them",
          code == 0 and abs(sum(crs) - 1722) <= 3 and "foreman: $0.391 (30 calls)" in out
          and any(l.startswith("CR-101: $0.361 (19 calls") for l in out)
          and any(l.startswith("O-1: $0.057 (3 calls") for l in out), str(out))
    for name in ("odd", "odd-worker", "lone"):
        (sub / f"agent-{name}.jsonl").unlink()
        (sub / f"agent-{name}.meta.json").unlink()
    events.write_text(original_events, encoding="utf-8")
    state.write_text(original_state)
    main.write_text(original)


def fake_transcripts(w: World, d: dict) -> None:
    from_root = str(w.work.resolve())
    slug = "".join(ch if ch.isalnum() else "-" for ch in from_root)
    main = w.root / "claude-projects" / slug / "uuid-foreman.jsonl"
    sub = main.with_suffix("") / "subagents"
    sub.mkdir(parents=True)

    def msg(mid, model, out, **fields):
        return json.dumps({"type": "assistant", **fields, "message": {
            "id": mid, "model": model, "usage": {
                "input_tokens": 10, "output_tokens": out, "cache_read_input_tokens": 20_000,
                "cache_creation": {"ephemeral_1h_input_tokens": 2_000}}}}) + "\n"

    def user(content):
        return json.dumps({"type": "user", "message": {"content": content}}) + "\n"

    result = [{"type": "tool_result", "content": "ok"}]  # the same turn goes on: not a wake
    earlier = msg("old", "claude-sonnet-5-5", 900_000, timestamp="2000-01-01T00:00:00.000Z")
    # a call in the opening second, with a fraction: a text comparison drops it
    opening = d["created"].removesuffix("Z") + ".250Z"
    synthetic = json.dumps({"type": "assistant", "message": {  # an API error: no tokens
        "id": "syn", "model": "<synthetic>", "usage": {
            "input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0}}}) + "\n"
    main.write_text(earlier + synthetic + "".join(
        (user("a wake") if i % 3 == 0 else user(result))
        + msg(f"f{i}", "claude-sonnet-5-5", 300, **({"timestamp": opening} if i == 0 else {}))
        for i in range(30)))
    chief = main.with_name("uuid-chief.jsonl")  # the Chief of Staff: an earlier subject, then now
    chief.write_text(earlier + msg("c1", "claude-sonnet-5-5", 300))
    (sub / "agent-earlier.jsonl").write_text(earlier)  # the session's earlier batch costs nothing
    for c in d["crs"]:
        if c.get("agent") and c["status"] != "cancelled":
            f = sub / f"agent-{c['agent']}.jsonl"
            f.write_text("".join(msg(f"{c['id']}{i}", "claude-sonnet-5-5", 900) for i in range(12)))
            f.with_suffix("").with_suffix(".meta.json").write_text(
                json.dumps({"agentType": "cr-driver"}))
            worker = sub / f"agent-worker-{c['agent']}.jsonl"  # started by the Driver
            worker.write_text("".join(msg(f"w{c['id']}{i}", "claude-sonnet-5-5", 900)
                                      for i in range(4)))
            worker.with_suffix("").with_suffix(".meta.json").write_text(
                json.dumps({"agentType": "coder", "parentAgentId": c["agent"]}))

class SurfaceWorld(World):
    """A planning surface (its own git repository) with two projects, each with its clone and
    worktrees outside the surface. `state` is the demo project's planning folder."""

    def __init__(self, root: Path):
        super().__init__(root)
        self.work = root / "code"  # the demo project's clone: the code repository
        self.surface = root / "surface"
        self.project = self.surface / "projects" / "demo"
        self.state = self.project / "changes"

    def chantier(self, *args, project="demo", cwd=None, **kw):
        head = ("--project", project) if project else ()
        return super().chantier(*head, *args, cwd=cwd or self.surface, **kw)

    def build(self) -> None:
        super().build()
        self.sh("git", "clone", "--quiet", str(self.root / "origin.git"), str(self.root / "code2"),
                cwd=self.root)
        self.sh("git", "init", "--quiet", "-b", "main", str(self.surface), cwd=self.root)
        self.sh("git", "config", "user.name", "scenario", cwd=self.surface)
        self.sh("git", "config", "user.email", "scenario@example.com", cwd=self.surface)
        (self.surface / "AGENTS.md").write_text("# Surface rules\n\nPlan on the default branch.\n")
        for name, suffix, archive in (("demo", "", "yes"), ("other", "2", "no")):
            folder = self.surface / "projects" / name
            folder.mkdir(parents=True)
            (folder / "checkout.yml").write_text(
                f"repo: ../../../code{suffix}\nworktrees: ../../../wt{suffix}\n")
            (folder / "project.md").write_text(
                f"# {name}\n\n- Remote: {self.root / 'origin.git'}\n- Archive in the PR: {archive}\n")
        self.sh("git", "add", ".", cwd=self.surface)
        self.sh("git", "commit", "--quiet", "-m", "init", cwd=self.surface)

    def prepare(self, title: str, project="demo") -> Path:
        _, out = self.chantier("file", title, project=project)
        inbox = self.surface / out[0].removeprefix("filed ").split(";", 1)[0]
        (inbox / "01-intent.md").write_text(f"# {title}\n\nThe original request is in intake.\n")
        (inbox / "02-answers.md").write_text("# Decisions\n\nNo open questions.\n")
        (inbox / "03-change-spec.md").write_text(f"# {title}\n\nImplement {title}.\n")
        _, out = self.chantier("triage", inbox, "--priority", "P1", project=project)
        return self.surface / out[0].removeprefix("triaged ").rsplit(" (", 1)[0]

    def surface_files(self) -> list[str]:
        p = subprocess.run(["git", "status", "--porcelain", "-uall"], cwd=self.surface,
                           capture_output=True, text=True, encoding="utf-8", check=True)
        return [ln.split(maxsplit=1)[1].strip('"') for ln in p.stdout.splitlines()]


LOCAL_FILES = {"STATUS.md", "STATUS.json", ".lock", ".lifecycle.lock", ".long-gate.lock",
               ".batch-number", "seat.json", "batch.json", "events.jsonl", "brief.md"}


def surface_publishes(w: SurfaceWorld, label: str) -> None:
    """The surface's git sees the CR documents and evidence, never a running batch's local files."""
    files = w.surface_files()
    local = [f for f in files if Path(f).name in LOCAL_FILES or Path(f).name.startswith(".closing-")
             or "/work/gates/" in f or f.endswith((".log", ".tmp"))]
    check(f"{label}: the surface's git lists no local file", not local, str(local))
    check(f"{label}: and still lists the CR's documents",
          any(f.endswith("03-change-spec.md") for f in files), str(files))


def external_surface(tmp: Path) -> None:
    note("\n## 20. A planning surface: the project's plans in a repository of their own")
    OPENED.clear()
    tmp.mkdir()
    w = SurfaceWorld(tmp)
    w.build()
    # at the surface's root, with two projects: a command names the project
    code, out = w.chantier("preflight", project=None)
    check("preflight at a surface lists its projects and passes",
          code == 0 and any("demo" in ln and "other" in ln for ln in out), str(out))
    code, _ = w.chantier("status", project=None, expect=2)
    check("a command at a surface with two projects exits 2 naming both",
          "demo" in w.last_stderr and "other" in w.last_stderr and "--project" in w.last_stderr,
          w.last_stderr)
    away = w.root / "code.away"
    (w.root / "code").rename(away)
    code, out = w.chantier("preflight", expect=2)
    check("a missing clone fails preflight and names the path and the remote",
          any("P8" in ln and "code" in ln and "origin.git" in ln for ln in out), str(out))
    away.rename(w.root / "code")
    w.chantier("init")
    ignore = (w.state / ".gitignore").read_text(encoding="utf-8")
    check("`init` makes the planning folder and its .gitignore of local files",
          (w.state / "1-inbox").is_dir() and "seat.json" in ignore and "/4-batch/batch.json" in ignore
          and "work/gates/" in ignore and not (w.work / ".agents").exists(), ignore)
    code, out = w.chantier("preflight")
    check("preflight passes in the surface's main checkout", code == 0, str(out))
    item = w.prepare("Surface work")
    item2 = w.prepare("Surface second")
    w.start(item, "--direct", "--slots", 1, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    check("the batch opens in the project's planning folder, the CR path is relative to it",
          w.batch()["crs"][0]["path"].startswith("4-batch/") and (w.state / "4-batch" / "batch.json").is_file()
          and not (w.work / ".agents").exists(), str(w.batch()["crs"][0]))
    code, _ = w.chantier("open", item2, "--direct", *FROM_AGENTS_MD, expect=None)
    check("a second open on the same project is refused", code != 0, w.last_stderr)
    # another project of the surface opens its own batch at once; the seat is one per project
    other = w.prepare("Other work", project="other")
    w.chantier("init", project="other")
    _, out = w.chantier("open", other, "--direct", "--slots", 1, *FROM_AGENTS_MD, project="other")
    other_batch = out[0].split()[1]
    w.chantier("seat", "take", "sess-a", "--env", "remote", "--title", "[remote] surface", "--link", "l")
    _, out = w.chantier("seat", "get", project="other")
    check("two projects of one surface each run a batch, and the seat is one per project",
          out == ["seat none"] and (w.project / "changes" / "seat.json").is_file(), str(out))
    w.chantier("seat", "leave", "sess-a")
    w.chantier("foreman", "set", "uuid-chief", "--epoch", 1, "--batch", other_batch, project="other")
    code, out = w.chantier("take", "CR-101", "--epoch", 1, "--batch", other_batch, project="other")
    check("a project set to keep its archive out of the PR says so in the facts",
          "archive: not in the PR" in out and any(ln.startswith("clone: ") and "code2" in ln for ln in out),
          str(out))
    shutil.rmtree(w.surface / "projects" / "other" / "changes" / "4-batch")
    # the demo batch, as a Driver of the project lives it
    w.chantier("foreman", "set", "uuid-chief", "--epoch", 1)
    w.chantier("foreman", "transcript", "uuid-chief", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    fm.turn()
    cr = w.batch()["crs"][0]["id"]
    c = w.cr(cr)
    facts = fm.facts
    cli_line = next((ln for ln in facts if ln.startswith("cli:")), "")
    archive_line = next((ln for ln in facts if ln.startswith("archive: ")), "")
    check("the facts carry `cli:` with --project, the clone and the archive path",
          f'--project "{w.project.as_posix()}"' in cli_line.replace("\\", "/")
          and any(ln.startswith("clone: ") and "/code" in ln.replace("\\", "/") for ln in facts)
          and re.search(r"in the PR at \.agents/changes/5-archives/\d{6}-\d{4}-101-", archive_line),
          str(facts))
    check("the worktree is created under the project's `worktrees` folder, outside the surface",
          Path(c["worktree"]).is_dir() and Path(c["worktree"]).resolve().is_relative_to(
              (w.root / "wt").resolve()), c["worktree"])
    _, out = w.chantier("rules")
    text = "\n".join(out).replace("\\", "/")
    check("`rules` lists the project's instructions, then the surface's",
          out[0] == "project:" and "surface:" in out and "/code/AGENTS.md" in text
          and "/surface/AGENTS.md" in text
          and text.index("/code/AGENTS.md") < text.index("surface:") < text.index("/surface/AGENTS.md"),
          text)
    surface_publishes(w, "after the take")
    # the remote board of one project: its own folder only, never the other project or the clone
    port = free_port()
    bp = BoardProc(w, "board", "--project", "demo", "--port", port, cwd=w.surface)
    try:
        start = bp.line()
        check("`board` at a surface starts on the project's folder", bool(start) and start.startswith("board on ")
              and "projects/demo/changes" in start.replace("\\", "/"), str(start))
        code, _, body = fetch(port, "/")
        check("the surface's board lists the project's CR", code == 200 and "Surface work" in body, body[:200])
        for label, rel in (("the other project's folder", "../../other/changes/1-inbox"),
                           ("the code clone", "../../../../code/app.py")):
            code, _, _ = fetch(port, "/file?p=" + urllib.parse.quote(rel))
            check(f"the surface's board refuses {label}", code == 404, str(code))
    finally:
        bp.stop()
    # the Driver's round: a change, the long gate, a PR without the archive, then with it
    w.chantier("round", cr, "--note", "edit surface.py")
    commit(w, cr, "surface.py", "SURFACE = True\n")
    w.chantier("gate", cr, GATE)
    ship(w, cr, "feat: surface")
    check("`ship` says the archive is missing from the PR, at its path",
          "archive missing from the PR at .agents/changes/5-archives/" in "\n".join(w.last_out),
          str(w.last_out))
    wt = Path(c["worktree"])
    where = archive_line.split(" at ", 1)[1].strip()
    folder = w.at(c["path"])
    target = wt / where
    shutil.copytree(folder, target, ignore=shutil.ignore_patterns("work", "*.log"))
    (target / "evidence").mkdir(exist_ok=True)
    (target / "evidence" / "check.txt").write_text("ok\n")
    msg = w.root / "commit-msg.txt"
    msg.write_text(f"{cr}: archive\n\n{TRAILER}\n")
    w.sh("git", "add", "-f", "--", ".agents", cwd=wt)
    w.sh("git", "commit", "--quiet", "-F", str(msg), cwd=wt)
    ship(w, cr, "feat: surface")
    check("with the archive in the PR, `ship` raises nothing about it",
          "archive missing" not in "\n".join(w.last_out), str(w.last_out))
    tree = w.sh("git", "ls-tree", "-r", "--name-only", "HEAD", where, cwd=wt).splitlines()
    check("the PR's archive holds the documents and the evidence, and no work folder",
          any(f.endswith("03-change-spec.md") for f in tree) and any(f.endswith("evidence/check.txt") for f in tree)
          and not any("/work/" in f for f in tree), str(tree))
    surface_publishes(w, "after the PR")
    check("the project's clone stays clean: its worktrees hold the Driver's commits",
          w.sh("git", "status", "--porcelain", cwd=w.work) == "", w.sh("git", "status", "--porcelain", cwd=w.work))
    w.ready(cr, w.cr(cr)["pr"])
    fm.turn()
    merge_pr(w, w.cr(cr)["pr"])
    w.chantier("order", "merged", cr)
    delivery = w.at(w.cr(cr)["path"]) / "delivery.md"
    page = delivery.read_text(encoding="utf-8") if delivery.is_file() else ""
    check("`order merged` writes delivery.md: the PR, the merge time, where the archive is",
          w.cr(cr)["pr"] in page and re.search(r"Merged: \d{4}-\d\d-\d\dT", page)
          and f"Archive in the PR: yes, at {where}" in page, page)
    fm.turn()
    check("the batch pauses once its CR is merged", fm.paused, str(w.batch()["status"]))
    slug = "".join(ch if ch.isalnum() else "-" for ch in str(w.surface.resolve()))
    chief = w.root / "claude-projects" / slug / "uuid-chief.jsonl"  # the session's own transcript
    chief.parent.mkdir(parents=True, exist_ok=True)
    chief.write_text(json.dumps({"type": "assistant", "timestamp": datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"), "message": {"id": "c1", "model": "claude-sonnet-5-5", "usage": {
            "input_tokens": 10, "output_tokens": 100, "cache_read_input_tokens": 0}}}) + "\n")
    (w.folder() / "retro.md").write_text("# Retro\n\n## Pause 1\n\n- one, fix one\n", encoding="utf-8")
    w.chantier("close", "--batch", w.name, "--yes")
    archives = list((w.state / "5-archives").glob("*-101-*"))
    check("`close` puts the merged CR in 5-archives with its delivery.md, the gate log staying off the surface's git",
          len(archives) == 1 and (archives[0] / "delivery.md").is_file(), str(archives))
    check("`close` keeps the retro in the surface's CR archive, and the CR's archive in its PR "
          "holds no retro.md",
          len(archives) == 1 and (archives[0] / "retro.md").is_file()
          and not any(f.endswith("retro.md") for f in tree), str(archives))
    surface_publishes(w, "after the close")
    w.env.pop("CHANTIER_BATCH", None)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="chantier-scenario-"))
    w = World(tmp)
    started = time.monotonic()
    try:
        w.build()
        if not ARGS.external_only:
            scenario(w)
        external_surface(tmp / "external")
    except Exception as e:  # a crash is a failed check with its reason
        check("scenario ran to the end", False, f"{type(e).__name__}: {e}")
    finally:
        if not ARGS.keep:
            subprocess.run(["git", "worktree", "prune"], cwd=w.work, capture_output=True)
            shutil.rmtree(tmp, ignore_errors=True)
    elapsed = time.monotonic() - started
    total = CHECKS["pass"] + CHECKS["fail"]
    head = [f"# chantier global scenario on {ARGS.forge}: {CHECKS['pass']}/{total} checks passed",
            "", f"- Run: {time.strftime('%Y-%m-%d %H:%M:%S')}, {elapsed:.1f} s",
            f"- Workspace: `{tmp}`{' (kept)' if ARGS.keep else ' (removed)'}", ""]
    results = HERE / "results"
    results.mkdir(exist_ok=True)
    out = results / f"{ARGS.forge}-{time.strftime('%Y%m%d-%H%M%S')}.md"
    out.write_text("\n".join(head + LOG) + "\n", encoding="utf-8")
    print(f"{ARGS.forge}: {CHECKS['pass']}/{total} checks passed in {elapsed:.1f} s; transcript {out}")
    return 0 if CHECKS["fail"] == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--forge", choices=sorted(FAKE), default="github",
                        help="the fake forge CLI the Drivers ship to")
    parser.add_argument("--external-only", action="store_true",
                        help="run only the planning-surface case")
    parser.add_argument("--keep", action="store_true", help="keep the temporary workspace")
    parser.add_argument("--verbose", action="store_true", help="print the transcript live")
    ARGS = parser.parse_args()
    sys.exit(main())
