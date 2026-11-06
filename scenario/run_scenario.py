#!/usr/bin/env python3
"""Global scenario: one whole chantier batch, end to end, through the real CLI.

A scripted Foreman reads the batch's state and does what its card leaves it (fills the slots,
asks the Chief of Staff, merges what the user allowed, cleans up, lands); scripted
Drivers create their worktree, commit, rebase, push and open their PRs against a bare origin and
a fake `gh` (or `glab`), and use the CLI for its record (`round`, `gate`, `ship`, `handback`).
The Chief of Staff steers with `chantier order`. Nothing calls a model: the scripted agents prove
the frame, and the checks are on what the CLI refuses, records and reports.

    uv run --no-project python scenario/run_scenario.py [--forge gitlab] [--keep] [--verbose]

Exit 0 when every check passes; the transcript is written to scenario/results/<forge>-<time>.md (ignored by git).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
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
BODY = "## Summary\n\n{title}.\n\n### Checks\n\nNone.\n"
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
        self.name = ""  # the open batch's id, `batch-<n>`: the CLI numbers it

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

    def batch(self):
        return json.loads((self.folder() / "batch.json").read_text())

    def folder(self, name=None):
        return self.state / "3-requests" / (name or self.name)

    def start(self, *args, **kw):
        """`open` takes no name: the batch is `batch-<n>`, and it is the one open batch."""
        code, out = self.chantier("open", *args, **kw)
        if code == 0:
            self.name = out[0].split()[1]
        return code, out

    def reset(self) -> None:
        """Sweep what an earlier case left open: `open` refuses a second batch."""
        for d in (self.state / "3-requests").glob("batch-*"):
            shutil.rmtree(d)

    def cr(self, cr_id):
        return next(c for c in self.batch()["crs"] if c["id"] == cr_id)


def open_pr(w: World, cr_id: str, title: str) -> str:
    """The Driver opens the PR with the forge's CLI, from the body it wrote."""
    c = w.cr(cr_id)
    body = w.work / c["path"] / "work" / "pr-body.md"
    if ARGS.forge == "github":
        _, out, _ = w.forge("pr", "create", "--base", "main", "--head", c["branch"], "--title",
                            title, "--body-file", str(body))
        return out.splitlines()[-1]
    _, out, _ = w.forge("api", "projects/local/merge_requests", "--method", "POST",
                        "--raw-field", f"source_branch={c['branch']}", "--raw-field",
                        "target_branch=main", "--raw-field", f"title={title}")
    return json.loads(out)["web_url"]


def merge_pr(w: World, pr: str) -> tuple[int, str]:
    """A merge with the forge's CLI, by the project's method (rebase)."""
    if ARGS.forge == "github":
        code, _, err = w.forge("pr", "merge", pr, "--rebase")
    else:
        code, _, err = w.forge("api", f"projects/local/merge_requests/{pr.rsplit('/', 1)[-1]}/merge",
                               "--method", "PUT")
    return code, err


class Foreman:
    """Does what foreman.md leaves it, from `batch.json` (a real one reads `chantier status`):
    the pending orders, the asks, the merges the user allowed, the free slots, the QA drivers,
    the cleanup, the landing."""

    def __init__(self, w: World, epoch: int):
        self.w, self.epoch = w, epoch
        self.started: list[str] = []
        self.asked: list[str] = []
        self.messages: list[str] = []
        self.cancelled: list[str] = []
        self.qa: list[str] = []  # the folders of the QA drivers it started
        self.told: set = set()
        self.facts: list[str] = []
        self.landed = False

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
        """`take`, then the Driver (a scripted one) with the facts in its prompt."""
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
        """Before `land`: the merged CRs' worktrees and branches, the Foreman's own hands."""
        for c in self.w.batch()["crs"]:
            if c["status"] != "merged":
                continue
            if Path(c["worktree"]).is_dir():
                subprocess.run(["git", "worktree", "remove", c["worktree"]], cwd=self.w.work,
                               capture_output=True)
            # the PR is merged (status above), the check the card asks for; -d would refuse
            # after a rebase or squash merge
            subprocess.run(["git", "branch", "-D", c["branch"]], cwd=self.w.work,
                           capture_output=True)

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
                last = c["notes"][-1] if c.get("notes") else ""
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
        if d["status"] != "landed" and d["crs"] and all(c["status"] in ENDED for c in d["crs"]) \
                and all(o["done"] for o in d["orders"]):
            self.remove_merged()
            self.w.chantier("land", "--epoch", self.epoch)
            self.landed = True

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
    body = w.work / c["path"] / "work" / "pr-body.md"
    body.parent.mkdir(exist_ok=True)
    push(w, cr_id)
    first = cr_id not in OPENED
    body.write_text(BODY.format(title=c["title"]))
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
    code, out = w.chantier("preflight")
    check("preflight passes on Claude Desktop with no setup", code == 0
          and out[-1] == "preflight passed")
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
    w.start(*(str(backlog) for _, backlog in items), "--parallel",
            "--slots", 2, "--budget", 50, *FROM_AGENTS_MD)
    check("the batch is numbered, has no name, and `--batch` takes the number",
          w.name == "batch-01" and w.folder().is_dir()
          and w.chantier("status", "--batch", "1")[0] == 0
          and w.chantier("status", "--batch", "batch-01")[0] == 0, w.name)
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
    check("opening moves the entire prepared folders into requests",
          all(not backlog.exists() for _, backlog in items)
          and all(f"/3-requests/{w.name}/" in c["path"]
                  and (w.work / c["path"] / "intake/request.md").is_file()
                  and (w.work / c["path"] / "03-change-spec.md").is_file() for c in d["crs"]))
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
    board = (w.state / "3-requests/STATUS.md").read_text(encoding="utf-8")
    check("the board shows the open batch and what `triage` just moved",
          f"[{w.name}]({w.name}/STATUS.md)" in board and "Fix login timeout" in board
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
          code == 0 and out[0].startswith(f"pass {GATE} at ") and "log" in out[0], str(out))
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
    _, out = w.chantier("handback", "CR-101", "ready", pr101)
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
    w.chantier("handback", "CR-102", "ready", w.cr("CR-102")["pr"])
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
          re.search(r"/5-trash/\d{6}-\d{4}-103-", w.cr("CR-103")["path"])
          and (w.work / w.cr("CR-103")["path"] / "02-answers.md").is_file()
          and "⚪ dropped" in (w.work / w.cr("CR-103")["path"] / "STATUS.md").read_text("utf-8"))
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
    w.chantier("handback", "CR-104", "ready", w.cr("CR-104")["pr"])
    driver_round(w, "CR-105", "ratelimit.py", "LIMIT = 10\n")
    w.chantier("handback", "CR-105", "ready", w.cr("CR-105")["pr"])
    fm.turn()
    check("the change on CR-101 reaches a new Driver, with the note, and the order is done",
          fm.started[-1] == "CR-101 note: change: also log the timeout"
          and all(o["done"] for o in w.batch()["orders"]), str(fm.started))
    w.chantier("handback", "CR-101", "ready", pr101)
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

    note("\n## 8. The user merges; the Foreman cleans up and lands the batch")
    code, _ = w.chantier("land", "--epoch", 2, expect=2)
    check("land is refused while PRs are not merged", code == 2 and w.batch()["status"] == "open")
    fake_transcripts(w, w.batch())
    orders = len(w.batch()["orders"])
    first = w.cr("CR-101")
    collisions = [w.state / "4-archives" / f"{stamp}-{Path(first['path']).name}" for stamp in
                  ((datetime.now(timezone.utc) + timedelta(minutes=m)).strftime("%y%m%d-%H%M")
                   for m in (0, 1))]
    for collision in collisions:
        collision.mkdir(parents=True)
        (collision / "sentinel.txt").write_text("do not overwrite")
    code, _ = w.chantier("order", "merged", "CR-101", expect=3)
    check("archive collisions are refused without losing either CR folder",
          code == 3 and all((c / "sentinel.txt").read_text() == "do not overwrite"
                            for c in collisions)
          and (w.work / first["path"] / "03-change-spec.md").is_file()
          and w.cr("CR-101")["status"] == "ready" and len(w.batch()["orders"]) == orders)
    for collision in collisions:
        shutil.rmtree(collision)
    _, out = w.chantier("order", "merged", "CR-101")
    check("`order merged` archives the CR at once", w.cr("CR-101")["status"] == "merged"
          and "/4-archives/" in w.cr("CR-101")["path"], str(out))
    fm.turn()
    for cr_id in ("CR-102", "CR-104", "CR-105"):
        w.chantier("order", "merged", cr_id)
        fm.turn()
    check("the last merge makes the Foreman land the batch", fm.landed)
    d = w.batch()
    check("the Foreman removed the merged worktrees and branches; the cancelled one stays",
          d["status"] == "landed" and all(
              Path(c["worktree"]).exists() == (c["status"] == "cancelled") for c in d["crs"])
          and not any(w.sh("git", "branch", "--list", c["branch"]) for c in d["crs"]
                      if c["status"] == "merged"))
    check("merged CR folders move intact to archives",
          all(re.search(r"/4-archives/\d{6}-\d{4}-\d{3}-", c["path"])
              and (w.work / c["path"] / "03-change-spec.md").is_file()
              and (w.work / c["path"] / "STATUS.md").is_file()
              and (w.work / c["path"] / "STATUS.json").is_file()
              for c in d["crs"] if c["status"] == "merged"))
    report = (w.folder() / "STATUS.md").read_text(encoding="utf-8")
    check("the batch's STATUS.md, once landed, lists every CR",
          "landed" in report and all(c["id"].removeprefix("CR-") in report for c in d["crs"]))
    board_index(w, d)
    prs = {c["id"]: c["pr"] for c in d["crs"] if c["pr"]}
    check("four PRs were opened on the fake forge by the Drivers", len(set(prs.values())) == 4)

    note("\n## 9. Cost")
    code, out = w.chantier("cost", "--by", "cr", "--batch", w.name)
    check("Claude cost prices the Foreman and each Driver",
          code == 0 and out[:2] == [f"{w.name}: $1.608 over 94 model calls",
                                    "foreman: $0.391 (30 calls)"]
          and set(out[2:-1]) == {f"CR-10{i}: $0.304 (16 calls)" for i in (1, 2, 4, 5)}, str(out))
    check("the Chief of Staff's two figures and context size come apart from the batch's spend",
          out[-1] == "Chief of Staff: $0.01 since the batch opened, $9.02 the whole session, "
                     "context 22,010 tokens"
          and abs(w.batch()["spent_usd"] - 1.608) < 0.001 and w.batch()["chief_transcript"]
          == "uuid-chief", str(out))
    code, out = w.chantier("cost", "--summary", "--batch", w.name)
    check("the summary gives the total, the budget and the split by level: the Foreman, the "
          "Drivers (the agents that started others) and the workers",
          code == 0 and out[0] == "Total: $1.61 of a $50 budget"
          and out[1] == "Foreman $0.39 (24%), Drivers $0.91 (57%), workers $0.31 (19%)"
          and out[2].startswith("Most: CR-10") and out[-2].startswith("Chief of Staff: $0.01")
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
    archived = (w.work / w.cr("CR-101")["path"] / "STATUS.md").read_text(encoding="utf-8")
    check("a landed batch's CR page keeps its cost and no link into the batch, and does not call "
          "the cost final: only `close` does",
          "$0.30 so far" in archived and "../STATUS.md" not in archived
          and "- [x] Merged" in archived, archived)
    cost_audit(w)

    note("\n## 10. Copilot cost")
    copilot_cost(w, d)
    copilot_uv(w)

    note("\n## 11. Event log")
    events = (w.folder() / "events.jsonl").read_text().splitlines()
    kinds = {json.loads(e)["kind"] for e in events}
    check("events.jsonl holds the whole story",
          {"open", "take", "round", "gate", "ship", "note", "handback",
           "order", "order-done", "cancel", "land"} <= kinds, str(sorted(kinds)))
    calls = (w.root / "gh-state.json.calls").read_text()
    created, merged = (("create", '"merge"'), ('"POST"', '/merge"'))[ARGS.forge == "gitlab"]
    check("only the agents called the forge: the Drivers created the PRs, nobody merged",
          created in calls and merged not in calls and "edit" not in calls and '"PUT"' not in calls,
          calls[-300:])
    close_batch(w)
    copilot_missing_transcript(w)
    lifecycle_regressions(w)
    stack_batch(w)
    release(w)
    granted_fixes(w)
    qa_on_head(w)
    dependencies(w)
    release_merge_on_approval(w)
    lost_messages(w)
    failed_opening(w)
    cancel_during_gate(w)
    rails(w)
    foreman_in_a_worktree(w)


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
    folder = w.work / c["path"]
    text = (folder / "STATUS.md").read_text(encoding="utf-8")
    check("a CR's STATUS.md says where it stands and links back to its batch",
          all(part in text for part in ("**Now:**", "**Next:**", "## Progress", "- [x] Round 1",
                                        "- [x] Long gate", "- [x] Shipped", "- [x] Handed back",
                                        "## Documents", "[specification](03-change-spec.md)",
                                        "## Where", f"[{w.name}](../STATUS.md)")), text)
    view = json.loads((folder / "STATUS.json").read_text(encoding="utf-8"))
    check("its STATUS.json says the same, with more",
          view["cr"] == "CR-104" and view["state"] == "ready" and view["step"] == "Notify"
          and view["pr"]["url"] == c["pr"] and view["steps"], str(view))
    board = (w.state / "3-requests/STATUS.md").read_text(encoding="utf-8")
    batch = (w.folder() / "STATUS.md").read_text(encoding="utf-8")
    check("the status cell gives the pastille, the state, the step and the round",
          "🟢 ready Notify 1/3" in board and "🟢 ready Notify 1/3" in batch, board)
    index = json.loads((w.state / "3-requests/STATUS.json").read_text(encoding="utf-8"))
    rows = [r for b in index["batches"] for r in b["crs"]]
    own = json.loads((w.folder() / "STATUS.json").read_text(encoding="utf-8"))["crs"]
    check("the index gives each batch its heartbeat and pending orders, and each CR row its "
          "blocked reason, silent time and folder, relative to 3-requests/ in the batch's file too",
          index["schema"] == 2 and rows
          and all({"heartbeat", "orders_pending"} <= set(b) for b in index["batches"])
          and all({"blocked", "silent_minutes", "folder"} <= set(r) for r in rows + own)
          and all((w.state / "3-requests" / r["folder"] / "STATUS.json").is_file()
                  for r in rows + own if r["folder"]), str(rows[:1]))
    check("a CR that is not working has no silent time, and none is blocked here",
          all(r["silent_minutes"] is None and r["blocked"] is None
              for r in rows if r["state"] == "ready"), str(rows))
    links = [(w.state / "3-requests", ln) for ln in re.findall(r"\]\(([^)h][^)]*)\)", board)]
    links += [(w.folder(), ln) for ln in re.findall(r"\]\(([^)h][^)]*)\)", batch)]
    check("every link of the board and the batch resolves",
          links and all((start / ln).exists() for start, ln in links), str(links))


def board_index(w: World, d: dict) -> None:
    """The index the CR board reads: the landed and trashed CRs, their totals and the limit."""
    path = w.state / "3-requests/STATUS.json"
    index = json.loads(path.read_text(encoding="utf-8"))
    merged = {c["id"] for c in d["crs"] if c["status"] == "merged"}
    got = {e["cr"]: e for e in index["landed"]}
    check("the index lists the landed CRs with their state, batch, PR, cost, time and folder",
          merged <= set(got) and index["landed_total"] >= len(merged)
          and all(got[i]["state"] == "merged" and got[i]["batch"] == w.folder().name
                  and got[i]["pr"] and got[i]["cost_usd"] is not None
                  and re.fullmatch(r"20\d\d-\d\d-\d\dT\d\d:\d\d:00Z", got[i]["when"])
                  and (w.state / "3-requests" / got[i]["path"] / "STATUS.json").is_file()
                  for i in merged), str(index["landed"]))
    check("the index lists the trashed CR, with a total",
          any(e["cr"] == "CR-103" and e["state"] == "cancelled" for e in index["trashed"])
          and index["trashed_total"] >= 1, str(index["trashed"]))
    landed_before = index["landed_total"]
    stage = w.state / "4-archives"
    made = []
    for n in range(60):  # older than any real archive, none with a STATUS.json
        folder = stage / f"250101-{n // 60:02d}{n % 60:02d}-padding-{n}"
        folder.mkdir()
        made.append(folder)
        (folder / "01-intent.md").write_text(f"# Padding {n}\n", encoding="utf-8")
    w.chantier("file", "Board index probe")  # rewrites the index
    index = json.loads(path.read_text(encoding="utf-8"))
    whens = [e["when"] for e in index["landed"]]
    bare = [e for e in index["landed"] if e["cr"] is None]
    check("the index keeps the last 50 landed CRs, newest first, and counts them all",
          len(index["landed"]) == 50 and index["landed_total"] == landed_before + 60
          and whens == sorted(whens, reverse=True) and not any("padding" in e["path"] for e in index["landed"][:len(merged)]),
          f"{len(index['landed'])} of {index['landed_total']}")
    check("a folder without a STATUS.json gives its title and null for the rest",
          all(e["title"].startswith("Padding") and e["state"] is None and e["pr"] is None
              and e["cost_usd"] is None and e["batch"] is None for e in bare) and bare,
          str(bare[:1]))
    for folder in made:
        shutil.rmtree(folder)


def age_sessions(w: World, seconds: int = 600) -> None:
    """The session files of the fixture, last written `seconds` ago: `close` reads their times."""
    then = time.time() - seconds
    for base in ("claude-projects", "copilot-home"):
        for f in (w.root / base).rglob("*"):
            if f.is_file():
                os.utime(f, (then, then))


def close_refusals(w: World) -> None:
    """A landed batch's cost is not final; `order add` reopens it; `close` refuses while any
    CR, order, stack agent or session file shows that something runs."""
    name, state = w.name, w.folder() / "batch.json"
    slug = "".join(ch if ch.isalnum() else "-" for ch in str(w.work.resolve()))
    main = w.root / "claude-projects" / slug / "uuid-foreman.jsonl"
    sub = main.with_suffix("") / "subagents"
    w.chantier("status", "--refresh", "--batch", name)
    code, out = w.chantier("status", "--batch", name)
    d = w.batch()
    check("`land` records a cost marked not final, in the summary and in `status`",
          "landed, cost not final" in out[0] and any(ln.startswith("Not final") for ln in d["summary"])
          and d["status"] == "landed", str(out))
    before = state.read_text()
    code, _ = w.chantier("land", "--batch", name, "--epoch", 2, expect=2)
    check("a second `land` on a landed batch is refused and changes nothing",
          code == 2 and "already landed" in w.last_stderr and state.read_text() == before,
          w.last_stderr)
    w.chantier("status", "--refresh", "--batch", name)
    report = (w.folder() / "STATUS.md").read_text(encoding="utf-8")
    header = re.search(r"spent \$(\d+\.\d\d)([^·\n]*)", report)
    total = re.search(r"Total: \$(\d+\.\d\d)", report)
    check("STATUS.md shows one total in its header and its Cost section, marked not final",
          header and total and header[1] == total[1] and "(not final)" in header[2]
          and "Not final" in report, report)

    # a call made after the landing is spend
    late = json.dumps({"type": "assistant", "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"), "message": {
        "id": "after-land", "model": "claude-sonnet-5-5", "usage": {
            "input_tokens": 10, "output_tokens": 100_000, "cache_read_input_tokens": 20_000,
            "cache_creation": {"ephemeral_1h_input_tokens": 2_000}}}}) + "\n"
    main.write_text(main.read_text() + late)
    code, out = w.chantier("cost", "--batch", name)
    check("a call made after the landing shows in `cost`",
          out[0] == f"{name}: $2.618 over 95 model calls", str(out))

    # new work sets the landed batch running again
    added = prepare_cr(w, "Work after the landing")[1]
    code, out = w.chantier("order", "add", "--batch", name, "--note", str(added))
    d = w.batch()
    new = d["crs"][-1]["id"]
    check("`order add` on a landed batch sets it running again and clears its landing, with a line "
          "that says so",
          d["status"] == "open" and "landed" not in d and "summary" not in d
          and any("was landed: running again" in ln for ln in out) and w.cr(new)["status"] == "queued",
          str(out))
    w.chantier("cancel", new, "--epoch", 2)
    for o in w.batch()["orders"]:
        if not o["done"]:
            w.chantier("order", "done", o["id"], "--epoch", 2)
    w.chantier("land", "--epoch", 2)
    d = w.batch()
    check("`land` runs again at the end of the reopened batch, and counts the later call",
          d["status"] == "landed" and d["landed"] and "Total: $2.62" in "\n".join(d["summary"]),
          str(d.get("summary")))

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
                  and w.folder().is_dir(), w.last_stderr)
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
    state.write_text(json.dumps({**d, "host": "copilot"}))
    code, out = w.chantier("close", "--batch", name, env=env)
    check("on Copilot, `close` passes once the session file is old, and says when it cannot price "
          "rather than a false $0", code == 0 and any(ln.startswith("Spent: unknown") for ln in out)
          and w.folder().is_dir(), str(out))
    state.write_text(base)
    # the Chief of Staff's own session writes all the time and never blocks its own close
    os.utime(main.with_name("uuid-chief.jsonl"), None)


def close_batch(w: World) -> None:
    note("\n## 11b. Closing the batch, on the user's word")
    folder, dropped = w.folder(), w.cr("CR-103")
    name = w.name
    close_refusals(w)
    code, out = w.chantier("close", "--batch", name)
    check("`close` alone says what would go, names the dropped CR's worktree and branch, and "
          "touches nothing",
          code == 0 and folder.is_dir() and Path(dropped["worktree"]).is_dir()
          and any(folder.name in ln for ln in out) and "--yes" in out[-1]
          and any(dropped["worktree"] in ln and dropped["branch"] in ln for ln in out), str(out))
    check("`close` prints the final cost, with a call made after `land` in it",
          any(ln.startswith("Total: $2.62") for ln in out) and "Not final" not in "\n".join(out),
          str(out))
    archived = w.work / w.cr("CR-101")["path"] / "STATUS.md"
    _, out = w.chantier("close", "--batch", name, "--yes")
    check("`close --yes` deletes the batch folder only, and repeats what is left to remove",
          not folder.exists() and Path(dropped["worktree"]).is_dir()
          and any(dropped["worktree"] in ln for ln in out), str(out))
    page = archived.read_text(encoding="utf-8")
    check("at `close` the archived CR page gives its cost as final, priced to then",
          re.search(r"## Cost\s+\$\d+\.\d\d\.\s*$", page) and "so far" not in page, page)
    # the Chief of Staff removes it on the same word, with git
    w.sh("git", "worktree", "remove", "--force", dropped["worktree"])
    w.sh("git", "branch", "-D", dropped["branch"])
    check("the dropped CR's worktree and branch are gone by the Chief of Staff's hands",
          not Path(dropped["worktree"]).exists()
          and not w.sh("git", "branch", "--list", dropped["branch"]))
    board = (w.state / "3-requests/STATUS.md").read_text(encoding="utf-8")
    check("the archives and the trash stay, and the board forgets the batch",
          name not in board and (w.work / dropped["path"] / "STATUS.md").is_file(), board)


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
          and not list((w.state / "3-requests").glob("batch-*")), w.last_stderr)


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
          "/5-trash/" in w.cr(cr)["path"] and out.startswith("FAIL") and "Traceback" not in err
          and "pg" in w.last_out[0], f"{out} {err} {w.last_out}")


def rails(w: World) -> None:
    note("\n## 19. The rails: rounds, slots 0, the budget, the long gate")
    _, a = prepare_cr(w, "Rail one")
    _, b = prepare_cr(w, "Rail two")
    slow = w.root / "slow_long.py"
    slow.write_text("import time\ntime.sleep(2)\n")
    long_gate = f'"{sys.executable}" "{slow}"'
    w.reset()
    w.start(str(a), str(b), "--parallel", "--slots", 1, "--budget", 1, "--default-branch", "main")
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman7", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    fm.turn()
    one, two = (c["id"] for c in w.batch()["crs"])
    check("one slot: one Driver", fm.started == [one])
    for _ in range(3):
        w.chantier("round", one)
    code, _ = w.chantier("round", one, expect=5)
    check("the fourth round is refused: the round limit is a rail (exit 5)",
          code == 5 and "round limit" in w.last_stderr and w.cr(one)["round"] == 3, w.last_stderr)
    _, out = w.chantier("status")
    check("status shows the rounds against the limit",
          any(ln.startswith(f"{one} working r3/3") for ln in out), str(out))
    w.chantier("order", "rounds", one, "--note", "4")
    fm.turn()  # the Driver is live: the Foreman tells it, the order is done
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
    _, out = w.chantier("handback", one, "ready", w.cr(one)["pr"])
    check("the hand-back stands: CI is the Driver's judgement, not the CLI's",
          w.cr(one)["status"] == "ready", str(out))
    code, _ = w.chantier("take", two, expect=2)
    check("slots 0 pauses: no Driver starts", code == 2 and "no free slot" in w.last_stderr)
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
    log = max((w.work / w.cr(two)["path"] / "work" / "gates").glob("*.log"))
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
    log = max((w.work / w.cr(two)["path"] / "work" / "gates").glob("*.log"))
    check("a long gate whose command died still holds the next one while its suite runs",
          code == 0 and waited >= 1 and "its command still runs" in log.read_text("utf-8"),
          f"{waited:.1f}s {out}")


def stack_batch(w: World) -> None:
    note("\n## 13. A stack by default, one open batch, a stack merged in part")
    w.reset()
    bottom, middle, top = (prepare_cr(w, t)[1] for t in ("Stack bottom", "Stack middle", "Stack top"))
    _, joined = prepare_cr(w, "Stack joiner")
    w.start(str(bottom), str(middle), str(top), *FROM_AGENTS_MD)
    d = w.batch()
    check("`open` makes a stack of four slots by default; the batch is `batch-<n>`",
          d["mode"] == "stack" and d["slots"] == 4 and re.fullmatch(r"batch-\d\d", d["id"])
          and d["id"] == w.name and w.folder().name == w.name
          and d["crs"][0]["branch"].startswith(f"chantier/{w.name}/")
          and Path(d["crs"][0]["worktree"]).name == f"{w.name}-{d['crs'][0]['id']}", str(d))
    code, _ = w.chantier("open", str(joined), *FROM_AGENTS_MD, expect=2)
    check("a second `open` is refused while a batch is open, and says which",
          code == 2 and w.name in w.last_stderr and "order add" in w.last_stderr
          and joined.is_dir() and len(list((w.state / "3-requests").glob("batch-*"))) == 1,
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
        w.chantier("handback", cr, "ready", w.cr(cr)["pr"])

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
          and w.cr(four)["path"].startswith(f".agents/changes/3-requests/{w.name}/")
          and len(list((w.state / "3-requests").glob("batch-*"))) == 1
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
    w.chantier("handback", four, "ready", w.cr(four)["pr"])

    _, out = w.chantier("order", "merged", one)
    d = w.batch()
    check("the bottom merges alone: it is archived at once and the batch stays open",
          w.cr(one)["status"] == "merged" and "/4-archives/" in w.cr(one)["path"]
          and (w.work / w.cr(two)["path"]).is_dir() and d["status"] == "open"
          and all(w.cr(c)["status"] == "ready" for c in (two, three, four)), str(out))
    _, out = w.chantier("take", "stack", "--epoch", 1)
    check("what remains forms another stack: the first now stands on the default branch",
          out[0].endswith(f"{two} → {three} → {four}")
          and f"{two} ready" in out[1] and "base origin/main" in out[1]
          and f"base {w.cr(two)['branch']}" in out[2], str(out))
    w.chantier("agents", "set", "stack", "agent-stack", "--epoch", 1)
    code, _ = w.chantier("take", "stack", "--epoch", 1, expect=2)
    check("one stack driver at a time, and the batch does not land under it",
          code == 2 and w.chantier("land", "--epoch", 1, expect=2)[0] == 2
          and w.batch()["status"] == "open")
    w.chantier("ship", two, w.cr(two)["pr"])
    ships = [json.loads(e) for e in (w.folder() / "events.jsonl").read_text().splitlines()]
    last = [e for e in ships if e["kind"] == "ship" and e["cr"] == two][-1]
    check("the restacked PR is recorded on the default branch", last["base"] == "main", str(last))
    w.chantier("agents", "set", "stack", "-", "--epoch", 1)
    for cr in (two, three, four):
        w.chantier("order", "merged", cr)
    fm.turn()
    check("the stack merged piece by piece: the batch lands, then closes",
          fm.landed and w.batch()["status"] == "landed"
          and w.chantier("close", "--batch", w.name.removeprefix("batch-"), "--yes")[0] == 0
          and not w.folder().exists())
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
          code == 2 and "once every other CR" in w.last_stderr, w.last_stderr)
    driver_round(w, work, "last.py", "LAST = True\n")
    w.chantier("handback", work, "ready", w.cr(work)["pr"])
    fm.turn()
    check("an ordinary ready CR goes to the user, never to a merge",
          fm.asked[-1].startswith(f"ready {work} "), str(fm.asked))
    w.chantier("order", "merged", work)
    fm.turn()
    check("once it is merged, the release CR is taken, with the grant in its facts",
          fm.started[-1] == rel and any(ln.startswith("grant: every irreversible action waits")
                                        for ln in fm.facts), str(fm.facts))

    tag = "push tag v1.1.0"
    _, out = w.chantier("release", "start", rel)
    check("an attempt is counted", out[0].startswith("attempt 1"), str(out))
    notes = w.work / w.cr(rel)["path"] / "work" / "notes-v1.1.0.md"
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
    w.chantier("handback", fix_id, "ready", w.cr(fix_id)["pr"])
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
          w.cr(fix_id)["status"] == "merged" and "/4-archives/" in w.cr(fix_id)["path"]
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
    w.gh(merge_refused=True)
    w.chantier("handback", rel, "blocked", f"merge: {w.cr(rel)['pr']}")
    fm.turn()
    check("the Foreman merges the release PR under the grant; refused by the forge, it asks",
          fm.asked[-1].startswith(f"refused {rel}") and w.cr(rel)["status"] == "blocked",
          fm.asked[-1])
    check("a blocked CR shows red", "🔴 blocked" in (w.folder() / "STATUS.md").read_text("utf-8"))
    w.gh(merge_refused=False)
    drivers = len(fm.started)
    fm.turn()
    check("merged with the forge's CLI, `order merged --epoch` sends the release on with a new "
          "Driver, not to the archives",
          len(fm.started) == drivers + 1 and fm.started[-1].startswith(f"{rel} merged:")
          and "/4-archives/" not in w.cr(rel)["path"]
          and all(o["done"] for o in w.batch()["orders"]), str(fm.started))
    check("the merged PR is not the next attempt's", w.cr(rel).get("pr") is None)
    w.chantier("release", "published", rel, "--note", "v1.1.0 https://forge.example/v1.1.0")
    code, _ = w.chantier("release", "go", rel, "--note", "publish v1.1.1", expect=2)
    check("the grant ends with its number of releases", code == 2)
    _, out = w.chantier("handback", rel, "ready", "https://forge.example/v1.1.0")
    check("a released CR is archived, and the batch can land",
          "/4-archives/" in w.cr(rel)["path"] and "chantier land" in out[1], str(out))
    fm.turn()
    check("the release done, the batch lands", fm.landed, str(fm.asked))
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
    work = w.work / w.cr(rel)["path"] / "work"
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
    spec = w.work / fix["path"] / "03-change-spec.md"
    check("a fix file becomes a fix CR of the batch, its specification kept",
          fix["kind"] == "fix" and fix["title"] == "Fix step 1" and fix["status"] == "queued"
          and spec.read_text() == files[0].read_text(), str(fix))
    w.chantier("order", "add", "--note", files[3], "--fix-for", rel)
    check("past three, a fix is the user's go", len(w.batch()["crs"]) == 5)
    for c in w.batch()["crs"]:
        w.chantier("order", "drop", c["id"])
    for o in w.batch()["orders"]:
        if not o["done"]:
            w.chantier("order", "done", o["id"], "--epoch", 1)
    w.chantier("land", "--epoch", 1)
    w.chantier("close", "--batch", w.name, "--yes")


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
    fm.turn()
    check("the Foreman starts a QA driver on the folder, and the CR goes on without it",
          fm.qa == [shown] and fm.started == [cr] and w.cr(cr)["status"] == "working",
          str(fm.qa))
    _, out = w.chantier("status")
    check("`status` shows the QA order and its folder until it is done",
          any(ln.startswith(f"orders pending: O-2 qa {shown}") for ln in out), str(out))
    w.chantier("cancel", cr, "--epoch", 1)
    code, _ = w.chantier("land", "--epoch", 1, expect=2)
    check("a batch does not land under a running QA", code == 2 and "O-2" in w.last_stderr,
          w.last_stderr)
    (folder / "findings.md").write_text("# QA\n\n- The export button is hidden on mobile\n")
    w.chantier("order", "done", "O-2", "--epoch", 1)
    w.chantier("land", "--epoch", 1)
    w.chantier("close", "--batch", w.name, "--yes")
    check("its findings stay in the inbox, an ordinary item",
          (folder / "findings.md").is_file())
    w.chantier("abandon", folder)


def depends_on(item: Path, *slugs: str, raw: str | None = None) -> None:
    """The Chief of Staff's `depends.json`, in the CR's folder."""
    (item / "depends.json").write_text(raw if raw is not None else json.dumps({"after": list(slugs)}),
                                       encoding="utf-8")


def dependencies(w: World) -> None:
    note("\n## 14d. A CR declares what it depends on; a slot is a running Driver")
    one, two = prepare_cr(w, "Cycle one")[1], prepare_cr(w, "Cycle two")[1]
    depends_on(one, two.name)
    depends_on(two, one.name)
    w.reset()
    code, _ = w.start(str(one), str(two), expect=2)
    check("a cycle is refused at `open`, naming it; nothing is opened or moved",
          code == 2 and "cycle" in w.last_stderr and one.is_dir() and two.is_dir()
          and not list((w.state / "3-requests").glob("batch-*")), w.last_stderr)
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
    w.start(str(base_), str(next_), "--parallel", "--slots", 3, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    a, b = (c["id"] for c in w.batch()["crs"])
    check("`open` records `after` as CR ids", w.cr(b).get("after") == [a] and "after" not in w.cr(a),
          str(w.batch()["crs"]))
    _, out = w.chantier("status")
    check("`status` shows what a queued CR waits for",
          any(ln.startswith(b) and f"waits for {a} queued" in ln for ln in out), str(out))
    board = json.loads((w.state / "3-requests" / w.name / "STATUS.json").read_text(encoding="utf-8"))
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
    w.chantier("handback", a, "ready", w.cr(a)["pr"])
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
    waiting = prepare_cr(w, "Dep waiting")[1]
    depends_on(waiting, cancelled.name)
    w.chantier("order", "add", "--note", str(waiting))
    code, _ = w.chantier("take", w.batch()["crs"][-1]["id"], expect=2)
    check("a cancelled dependency stays unmet", code == 2 and f"{dropped} cancelled" in w.last_stderr,
          w.last_stderr)

    w.reset()
    s1, s2 = prepare_cr(w, "Stack first")[1], prepare_cr(w, "Stack second")[1]
    depends_on(s2, s1.name)
    w.start(str(s1), str(s2), *FROM_AGENTS_MD)
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
    w.start(str(q1), str(q2), "--parallel", "--slots", 2, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    c1, c2 = (c["id"] for c in w.batch()["crs"])
    w.chantier("take", c1)
    w.chantier("order", "qa", "--note", "try it")
    check("an open QA order holds a slot: `status` counts it",
          w.chantier("status")[1][0].split(" live ")[1].startswith("2/2"), str(w.last_out))
    code, _ = w.chantier("take", c2, expect=2)
    check("with the QA driver and a CR, no slot is free for the next", code == 2
          and "no free slot" in w.last_stderr and "O-1 qa" in w.last_stderr, w.last_stderr)
    code, _ = w.chantier("order", "qa", "--note", "again", expect=2)
    check("a second QA order is refused too: its driver would have no slot",
          code == 2 and "no free slot" in w.last_stderr, w.last_stderr)
    w.chantier("order", "done", "O-1")
    code, _ = w.chantier("take", c2)
    check("the QA driver's end frees its slot", code == 0)
    w.env.pop("CHANTIER_BATCH", None)


def release_merge_on_approval(w: World) -> None:
    note("\n## 15. A release PR merges on the user's approval")
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
    w.chantier("handback", rel, "blocked", f"merge: {pr}")
    fm.turn()
    check("without a grant, the merge is an approval to ask",
          fm.asked[-1] == f"blocked {rel} approval: merge the release PR {pr}", str(fm.asked))
    drivers = len(fm.started)
    w.chantier("order", "approve", rel, "--note", f"merge the release PR {pr}")
    fm.turn()
    check("the approval lets the Foreman merge; the next Driver goes on",
          any(a.startswith(f"merged {rel} ") for a in fm.asked) and len(fm.started) == drivers + 1
          and w.cr(rel)["status"] == "working", str(fm.asked))
    w.chantier("handback", rel, "ready", "v1.2.0")
    fm.turn()
    check("the batch lands", fm.landed)
    last = w.folder()
    if sys.platform == "win32":  # elsewhere a file in use does not stop a rename
        with open(last / "STATUS.md", encoding="utf-8"):
            code, _ = w.chantier("close", "--batch", w.name, "--yes", expect=None)
        check("`close` on a folder in use deletes nothing and can run again",
              code != 0 and "in use" in w.last_stderr and (last / "batch.json").is_file(),
              w.last_stderr)
    w.chantier("close", "--batch", w.name, "--yes")
    w.number_after = int(last.name.split("-")[1]) + 1


def lost_messages(w: World) -> None:
    note("\n## 16. Lost messages: the wake catches up, and nothing is left unsaid")
    titles = ("Lost one", "Lost two", "Lost three")
    prepared = [prepare_cr(w, title)[1] for title in titles]
    w.reset()
    w.start(*(str(p) for p in prepared), "--parallel", "--slots", 3, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    check("batch numbers go on rising after the last batch's folder is deleted",
          w.folder().name == f"batch-{w.number_after:02d}", w.folder().name)
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
    w.chantier("handback", one, "ready", w.cr(one)["pr"])
    fm.turn()
    check("a ready CR is told", fm.asked[-1].startswith(f"ready {one} "))
    driver_round(w, two, "lost.py", f"WHO = '{two}'\n")
    w.sh("git", "push", "--quiet", "origin", f"{w.cr(one)['branch']}:main")  # the user merges
    _, out = w.chantier("handback", two, "ready", w.cr(two)["pr"])
    check("a hand-back records what the Driver says; whether the PR still merges is the "
          "Foreman's to notice with the forge's CLI", w.cr(two)["status"] == "ready", str(out))
    _, out = w.chantier("status", "--refresh", "--epoch", 1, expect=None)
    check("a wake names the longest silent Driver and says what it knows of the spend",
          any(ln.startswith("longest silent Driver") for ln in out)
          and any(ln.startswith(("spent $", "spend not updated")) for ln in out), str(out))
    driver_round(w, three, "other.py", "OTHER = True\n")
    w.chantier("handback", three, "ready", w.cr(three)["pr"])
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
          and not list((w.state / "3-requests").glob("batch-*")), w.last_stderr)
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
              "Foreman: $1.000 (1 calls)", "Agent cr-driver: $0.500 (1 calls)",
              "Agent coder: $0.375 (2 calls)", "Chief of Staff: not measured"], str(out))
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
              "Chief of Staff: not measured"], str(out))

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

    # `land` ends no window: a call made after it is spend, and a `<synthetic>` record costs nothing
    main.write_text(original + msg("later", 900_000, timestamp="2999-01-01T00:00:00.000Z"))
    code, out = w.chantier("cost", "--batch", w.name)
    check("a call made after the landing is counted, and a `<synthetic>` record costs nothing",
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
        {"t": when[0], "actor": "foreman", "kind": "agent", "cr": "CR-101", "agent": "odd"}) + "\n",
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
          and "Driver cr-driver: $0.913 (48 calls)" in out and "Worker coder: $0.323 (17 calls)" in out
          and "Driver my-own-driver: $0.038 (2 calls)" in out, str(out))
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
          and "CR-101: $0.361 (19 calls)" in out and "other: $0.057 (3 calls)" in out, str(out))
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


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="chantier-scenario-"))
    w = World(tmp)
    started = time.monotonic()
    try:
        w.build()
        scenario(w)
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
    parser.add_argument("--keep", action="store_true", help="keep the temporary workspace")
    parser.add_argument("--verbose", action="store_true", help="print the transcript live")
    ARGS = parser.parse_args()
    sys.exit(main())
