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
LIVE = {"working", "qa"}
ENDED = {"merged", "cancelled"}
BACK_NOTES = ("rebase:", "QA found", "merged:")
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
                    "CLAUDE_CODE_ENTRYPOINT": "claude-desktop", "CHANTIER_HOST": "claude"}
        for var in ("CHANTIER_ROOT", "CHANTIER_BATCH", "CHANTIER_PLUGIN_ROOT"):
            self.env.pop(var, None)
        self.last_stderr = ""
        self.last_out: list[str] = []
        self.name = "night"

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
        return next((self.state / "3-requests").glob(f"*-{name or self.name}"))

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
        self.told: set = set()
        self.facts: list[str] = []
        self.landed = False

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
        key = f"qa:{target}" if target != "stack" and self.w.cr(target)["status"] == "qa" \
            else target
        self.started.append(f"{key} {note_}" if note_ else key)
        self.w.chantier("agents", "set", key, f"agent-{len(self.started)}", "--epoch", self.epoch)
        if key == target != "stack":
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
            subprocess.run(["git", "branch", "-d", c["branch"]], cwd=self.w.work,
                           capture_output=True)

    def merge(self, c: dict) -> None:
        """What the user allowed the Foreman to merge: a release's fix under the grant, the
        release PR after `release go`. Done with the forge's CLI, recorded with `order merged`."""
        cr = c["id"]
        if c.get("kind") == "release":
            action = f"merge the release PR {c['pr']}"
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
                if c.get("kind") == "fix" and (d.get("release") or {}).get("auto_merge"):
                    self.merge(c)
                else:
                    self.ask(f"ready {c['id']} {c['pr']}")
            elif c["status"] == "qa" and not c.get("qa_agent"):
                self.take(c["id"])
        d = self.w.batch()
        live = sum(c["status"] in LIVE for c in d["crs"])
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
    code, _ = w.chantier("open", "raw-title", "Fix login", *FROM_AGENTS_MD, expect=1)
    check("a raw title cannot bypass the prepared CR", code == 1 and items[0][1].is_dir())
    w.chantier("open", "night", *(f"@{backlog}" for _, backlog in items),
               "--slots", 2, "--qa", "2", "--budget", 50, *FROM_AGENTS_MD)
    w.chantier("foreman", "set", "local_foreman1")
    fm = Foreman(w, epoch=1)
    w.chantier("foreman", "transcript", "uuid-foreman", "--epoch", 1)
    d = w.batch()
    check("four CRs, each with a branch and a worktree named, none created: the CLI changes "
          "nothing in git",
          len(d["crs"]) == 4 and all(c["branch"].startswith("chantier/night/cr-10")
                                     and not Path(c["worktree"]).exists() for c in d["crs"]))
    code, _ = w.chantier("gate", "CR-103", GATE, expect=2)
    check("a command that needs the worktree says who creates it",
          code == 2 and "its Driver creates it" in w.last_stderr, w.last_stderr)
    check("opening moves the entire prepared folders into requests",
          all(not backlog.exists() for _, backlog in items)
          and all("/3-requests/01-night/" in c["path"]
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
          "[Batch 01-night](01-night/STATUS.md)" in board and "Fix login timeout" in board
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

    note("\n## 4. CR-102: two rounds, then QA")
    driver_round(w, "CR-102", "export.py", "def export():\n    return 'csv'\n")
    w.chantier("note", "CR-102", "CI red: the product; export header missing")
    driver_round(w, "CR-102", "export.py", "def export():\n    return 'id,name\\n'\n")
    _, out = w.chantier("handback", "CR-102", "ready", w.cr("CR-102")["pr"])
    check("a QA CR waits for its QA driver", w.cr("CR-102")["status"] == "qa"
          and "chantier take CR-102" in out[1], str(out))
    fm.turn()
    check("the Foreman gives CR-102 to a QA driver", fm.started[-1] == "qa:CR-102")
    code, _ = w.chantier("take", "CR-102", expect=2)
    check("a second QA driver is refused while one is recorded", code == 2
          and "has a QA driver" in w.last_stderr, w.last_stderr)
    findings = w.root / "qa-findings.md"
    findings.write_text("# QA\n\n- The export button is hidden on mobile\n")
    code, _ = w.chantier("qa", "CR-102", "--findings", findings, expect=2)
    check("QA without proof in evidence/ is refused", code == 2 and "no proof" in w.last_stderr,
          w.last_stderr)
    evidence = w.work / w.cr("CR-102")["path"] / "evidence"
    evidence.mkdir()
    (evidence / "mobile.txt").write_text("$ open /export at 375px: no export button\n")
    _, out = w.chantier("qa", "CR-102", "--findings", findings)
    check("a QA finding queues the CR with the findings file",
          out[0] == "[qa CR-102→foreman] qa done CR-102 1 findings"
          and w.cr("CR-102")["status"] == "queued", str(out))
    fm.turn()
    check("the Foreman gives CR-102 a new Driver with the findings",
          fm.started[-1].startswith("CR-102 QA found 1 findings: ")
          and fm.started[-1].endswith("qa-findings.md"), fm.started[-1])
    driver_round(w, "CR-102", "export_ui.py", "VISIBLE_ON_MOBILE = True\n")
    w.chantier("handback", "CR-102", "ready", w.cr("CR-102")["pr"])
    fm.turn()
    findings.write_text("# QA\n\nNo findings.\n")
    w.chantier("qa", "CR-102", "--findings", findings)
    fm.turn()
    check("a clean QA pass hands CR-102 to the Chief of Staff",
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
    _, out = w.chantier("order", "add", "--note", f"@{added}")
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
    w.chantier("foreman", "set", "local_foreman2")
    w.chantier("foreman", "transcript", "uuid-foreman", "--epoch", 2)
    code, _ = w.chantier("status", "--refresh", "--epoch", 1, expect=3)
    check("a stale Foreman (epoch 1) is refused with exit 3", code == 3)
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
    prs = {c["id"]: c["pr"] for c in d["crs"] if c["pr"]}
    check("four PRs were opened on the fake forge by the Drivers", len(set(prs.values())) == 4)

    note("\n## 9. Cost")
    code, out = w.chantier("cost", "--by", "cr", "--batch", "night")
    check("Claude cost prices the Foreman and each Driver",
          code == 0 and out[:2] == ["night: $1.304 over 78 model calls",
                                    "foreman: $0.391 (30 calls)"]
          and set(out[2:]) == {f"CR-10{i}: $0.228 (12 calls)" for i in (1, 2, 4, 5)}, str(out))
    code, out = w.chantier("cost", "--summary", "--batch", "night")
    check("the summary gives the total, the budget and orchestration (the agents that started "
          "others) against work",
          code == 0 and out[0] == "Total: $1.30 of a $50 budget"
          and out[1] == "Orchestration $0.39 (30%), work $0.91 (70%)"
          and out[2].startswith("Most: CR-10") and "Chief of Staff" in out[-1], str(out))
    check("the summary gives the Foreman's wakes and its context, average and peak",
          out[3] == "Foreman: 10 wakes, context 22,010 tokens on average, 22,010 at its peak",
          str(out))
    report = (w.folder() / "STATUS.md").read_text(encoding="utf-8")
    check("the batch's STATUS.md gives each CR's cost and the summary",
          "| $0.23 |" in report and "## Cost" in report and "Total: $1.30" in report, report)
    archived = (w.work / w.cr("CR-101")["path"] / "STATUS.md").read_text(encoding="utf-8")
    check("an archived CR keeps its final cost and no link into the batch",
          "$0.23." in archived and "../STATUS.md" not in archived
          and "- [x] Merged" in archived, archived)

    note("\n## 10. Copilot cost")
    copilot_cost(w, d)
    copilot_uv(w)

    note("\n## 11. Event log")
    events = (w.folder() / "events.jsonl").read_text().splitlines()
    kinds = {json.loads(e)["kind"] for e in events}
    check("events.jsonl holds the whole story",
          {"open", "take", "round", "gate", "ship", "note", "qa-done", "handback",
           "order", "order-done", "cancel", "land"} <= kinds, str(sorted(kinds)))
    calls = (w.root / "gh-state.json.calls").read_text()
    created, merged = (("create", '"merge"'), ('"POST"', '/merge"'))[ARGS.forge == "gitlab"]
    check("only the agents called the forge: the Drivers created the PRs, nobody merged",
          created in calls and merged not in calls and "edit" not in calls and '"PUT"' not in calls,
          calls[-300:])
    close_batch(w)
    lifecycle_regressions(w)
    release(w)
    release_merge_on_approval(w)
    lost_messages(w)
    failed_opening(w)
    cancel_during_gate(w)
    rails(w)


def status_files(w: World) -> None:
    c = w.cr("CR-104")
    folder = w.work / c["path"]
    text = (folder / "STATUS.md").read_text(encoding="utf-8")
    check("a CR's STATUS.md says where it stands and links back to its batch",
          all(part in text for part in ("**Now:**", "**Next:**", "## Progress", "- [x] Round 1",
                                        "- [x] Long gate", "- [x] Shipped", "- [x] Handed back",
                                        "## Documents", "[specification](03-change-spec.md)",
                                        "## Where", "[Batch 01-night](../STATUS.md)")), text)
    view = json.loads((folder / "STATUS.json").read_text(encoding="utf-8"))
    check("its STATUS.json says the same, with more",
          view["cr"] == "CR-104" and view["state"] == "ready" and view["step"] == "Notify"
          and view["pr"]["url"] == c["pr"] and view["steps"], str(view))
    board = (w.state / "3-requests/STATUS.md").read_text(encoding="utf-8")
    batch = (w.folder() / "STATUS.md").read_text(encoding="utf-8")
    check("the status cell gives the pastille, the state, the step and the round",
          "🟢 ready Notify 1/3" in board and "🟢 ready Notify 1/3" in batch, board)
    links = [(w.state / "3-requests", ln) for ln in re.findall(r"\]\(([^)h][^)]*)\)", board)]
    links += [(w.folder(), ln) for ln in re.findall(r"\]\(([^)h][^)]*)\)", batch)]
    check("every link of the board and the batch resolves",
          links and all((start / ln).exists() for start, ln in links), str(links))


def close_batch(w: World) -> None:
    note("\n## 11b. Closing the batch, on the user's word")
    folder, dropped = w.folder("night"), w.cr("CR-103")
    code, out = w.chantier("close", "--batch", "night")
    check("`close` alone says what would go, names the dropped CR's worktree and branch, and "
          "touches nothing",
          code == 0 and folder.is_dir() and Path(dropped["worktree"]).is_dir()
          and any(folder.name in ln for ln in out) and "--yes" in out[-1]
          and any(dropped["worktree"] in ln and dropped["branch"] in ln for ln in out), str(out))
    _, out = w.chantier("close", "--batch", "night", "--yes")
    check("`close --yes` deletes the batch folder only, and repeats what is left to remove",
          not folder.exists() and Path(dropped["worktree"]).is_dir()
          and any(dropped["worktree"] in ln for ln in out), str(out))
    # the Chief of Staff removes it on the same word, with git
    w.sh("git", "worktree", "remove", "--force", dropped["worktree"])
    w.sh("git", "branch", "-D", dropped["branch"])
    check("the dropped CR's worktree and branch are gone by the Chief of Staff's hands",
          not Path(dropped["worktree"]).exists()
          and not w.sh("git", "branch", "--list", dropped["branch"]))
    board = (w.state / "3-requests/STATUS.md").read_text(encoding="utf-8")
    check("the archives and the trash stay, and the board forgets the batch",
          "01-night" not in board and (w.work / dropped["path"] / "STATUS.md").is_file(), board)


def failed_opening(w: World) -> None:
    note("\n## 17. Openings that fail")
    _, item = prepare_cr(w, "Latin one specification")
    spec = item / "03-change-spec.md"
    good = spec.read_bytes()
    spec.write_bytes("# Spécification\n".encode("latin-1"))
    code, _ = w.chantier("open", "latin", f"@{item}", *FROM_AGENTS_MD, expect=None)
    check("a specification that is not UTF-8 is named, not a traceback",
          code == 2 and "not UTF-8" in w.last_stderr and "Traceback" not in w.last_stderr,
          w.last_stderr)
    spec.write_bytes(good)
    code, _ = w.chantier("open", "stuck", f"@{item}", f"@{w.root / 'nowhere'}", *FROM_AGENTS_MD,
                         expect=None)
    check("a second item that is not a prepared CR fails the opening, and the first one is "
          "restored where it was",
          code != 0 and (item / "03-change-spec.md").is_file()
          and not list((w.state / "3-requests").glob("*-stuck")), w.last_stderr)


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
    w.chantier("open", "halt", f"@{item}", "--default-branch", "main")
    w.name, w.env["CHANTIER_BATCH"] = "halt", "halt"
    w.chantier("foreman", "set", "local_foreman6")
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
    w.chantier("open", "rails", f"@{a}", f"@{b}", "--slots", 1, "--budget", 1,
               "--default-branch", "main")
    w.name, w.env["CHANTIER_BATCH"] = "rails", "rails"
    w.chantier("foreman", "set", "local_foreman7")
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


def release(w: World) -> None:
    note("\n## 14. A release: the project's procedure, approvals, a fix, a grant")
    _, change = prepare_cr(w, "Last change")
    _, version = prepare_cr(w, "Release v1.1.0")
    bad = (("--release", 3), ("--release", 2, "--qa", "2"), ("--release", 2, "--auto-merge-fixes"),
           ("--autonomous-releases", 1, "--budget", 5))
    for args in bad:
        code, _ = w.chantier("open", "ship", f"@{change}", f"@{version}", *FROM_AGENTS_MD, *args,
                             expect=1)
        check(f"open refuses {args}", code == 1 and change.is_dir())
    w.chantier("open", "ship", f"@{change}", f"@{version}", "--release", 2, "--slots", 2,
               *FROM_AGENTS_MD)
    w.name, w.env["CHANTIER_BATCH"] = "ship", "ship"
    w.chantier("foreman", "set", "local_foreman3")
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
    code, _ = w.chantier("order", "grant", rel, "--note", "releases=1 auto-merge=on", expect=1)
    check("a grant without a budget is refused", code == 1 and "budget" in w.last_stderr)
    w.chantier("order", "grant", rel, "--note", "releases=1 auto-merge=on budget=5")
    started = len(fm.started)
    fm.turn()
    check("a grant leaves a release that waits for its fix alone",
          len(fm.started) == started and w.cr(rel)["status"] == "blocked")
    _, out = w.chantier("order", "add", "--note", f"@{fix}", "--fix-for", rel)
    fm.turn()
    fix_id = w.batch()["crs"][-1]["id"]
    check("a fix becomes a CR of the batch; the release waits for it",
          fm.started[-1] == fix_id and w.cr(rel)["status"] == "blocked"
          and w.cr(fix_id)["fix_for"] == rel, str(fm.started))
    code, out = w.chantier("release", "go", rel, "--note", "publish v1.1.0", expect=2)
    check("no irreversible action while a fix of the release is not merged",
          code == 2 and out[0].startswith(f"no: fix {fix_id} is not merged"), str(out))
    driver_round(w, fix_id, "heavy.py", "FIXED = True\n")
    w.gh(merge_refused=True)
    w.chantier("handback", fix_id, "ready", w.cr(fix_id)["pr"])
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


def release_merge_on_approval(w: World) -> None:
    note("\n## 15. A release PR merges on the user's approval")
    _, version = prepare_cr(w, "Release v1.2.0")
    w.chantier("open", "approve", f"@{version}", "--release", 1, *FROM_AGENTS_MD)
    w.name, w.env["CHANTIER_BATCH"] = "approve", "approve"
    w.chantier("foreman", "set", "local_foreman4")
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
            code, _ = w.chantier("close", "--batch", "approve", "--yes", expect=None)
        check("`close` on a folder in use deletes nothing and can run again",
              code != 0 and "in use" in w.last_stderr and (last / "batch.json").is_file(),
              w.last_stderr)
    w.chantier("close", "--batch", "approve", "--yes")
    w.number_after = int(last.name.split("-")[0]) + 1


def lost_messages(w: World) -> None:
    note("\n## 16. Lost messages: the wake catches up, and nothing is left unsaid")
    titles = ("Lost one", "Lost two", "Lost three")
    prepared = [prepare_cr(w, title)[1] for title in titles]
    w.chantier("open", "lost", *(f"@{p}" for p in prepared), "--slots", 3, *FROM_AGENTS_MD)
    w.name, w.env["CHANTIER_BATCH"] = "lost", "lost"
    check("batch numbers go on rising after the last batch's folder is deleted",
          w.folder().name == f"{w.number_after:02d}-lost", w.folder().name)
    w.chantier("foreman", "set", "local_foreman5")
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
    _, original = prepare_cr(w, "Preserve failed opening")
    code, _ = w.chantier("open", "rollback", f"@{original}", "--remote", "nowhere",
                         *FROM_AGENTS_MD, expect=4)
    check("a remote Git does not know is refused before anything moves",
          code == 4 and "nowhere" in w.last_stderr and (original / "03-change-spec.md").is_file()
          and not list((w.state / "3-requests").glob("*-rollback")), w.last_stderr)
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
    code, out = w.chantier("cost", "--batch", "night", env=env)
    check("Copilot cost groups billed and estimated calls by role (the host's agent type)",
          code == 0 and out == [
              "night: $1.875 over 4 model calls (1 estimated, not billed)",
              "foreman: $1.000 (1 calls)", "cr-driver: $0.500 (1 calls)",
              "coder: $0.375 (2 calls)"], str(out))
    code, out = w.chantier("cost", "--batch", "night", "--by", "cr", env=env)
    check("Copilot cost attributes calls by agent, name and other",
          code == 0 and out[1:] == [
              "foreman: $1.000 (1 calls)", f"{assigned['id']}: $0.500 (1 calls)",
              f"{named['id']}: $0.250 (1 calls)", "other: $0.125 (1 calls)"], str(out))

    def fails(label, expected, message, overrides=None):
        code, out = w.chantier("cost", "--batch", "night", env={**env, **(overrides or {})},
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
    _, missing = prepare_cr(w, "Missing transcript")
    w.chantier("open", "cost-missing", f"@{missing}", *FROM_AGENTS_MD,
               env={"CHANTIER_HOST": "copilot"})
    code, out = w.chantier("cost", "--batch", "cost-missing", env=env, expect=2)
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
    main.write_text(earlier + "".join((user("a wake") if i % 3 == 0 else user(result))
                                      + msg(f"f{i}", "claude-sonnet-5-5", 300) for i in range(30)))
    (sub / "agent-earlier.jsonl").write_text(earlier)  # the session's earlier batch costs nothing
    for c in d["crs"]:
        if c.get("agent") and c["status"] != "cancelled":
            f = sub / f"agent-{c['agent']}.jsonl"
            f.write_text("".join(msg(f"{c['id']}{i}", "claude-sonnet-5-5", 900) for i in range(12)))
            f.with_suffix("").with_suffix(".meta.json").write_text(
                json.dumps({"agentType": "cr-driver"}))


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
