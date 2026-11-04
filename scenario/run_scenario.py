#!/usr/bin/env python3
"""Global scenario: one whole chantier batch, end to end, through the real CLI.

A scripted Foreman feeds events to `chantier event` and carries out the actions it prints; scripted
Drivers commit in their CR worktree, run the gates, ship to a bare origin, wait on a fake `gh`
(or `glab`) and hand back. The Chief of Staff steers with `chantier order`. Nothing calls a model.

    uv run --no-project python scenario/run_scenario.py [--forge gitlab] [--keep] [--verbose]

Exit 0 when every check passes; the transcript is written to scenario/results/<forge>-<time>.md (ignored by git).
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent / "skills" / "chantier"
FAKE = {"github": ("CHANTIER_GH", "gh", Path(__file__).with_name("fake_gh.py")),
        "gitlab": ("CHANTIER_GLAB", "glab", Path(__file__).with_name("fake_glab.py"))}
PR_LINK = {"github": "https://github.com/acme/demo/pull/",
           "gitlab": "https://gitlab.example.com/acme/demo/-/merge_requests/"}
FAKE_USAGE = Path(__file__).with_name("fake_session_usage.py")
LOG: list[str] = []
CHECKS = {"pass": 0, "fail": 0}
GATE = "uv run --no-project python -m compileall -q ."
FROM_AGENTS_MD = ("--fast-gate", GATE, "--long-gate", GATE, "--default-branch", "main")
TRAILER = "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"


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
        var, exe, _ = FAKE[ARGS.forge]
        self.env = {**os.environ, "PYTHONPATH": str(SKILL / "scripts" / "cli" / "src"),
                    "CHANTIER_SKILL_DIR": str(SKILL),
                    var: str(root / "bin" / (f"{exe}.cmd" if sys.platform == "win32" else exe)),
                    "FAKE_GH_STATE": str(self.gh_state), "CHANTIER_WAIT_INTERVAL": "0.05",
                    "CHANTIER_CLAUDE_PROJECTS": str(root / "claude-projects"),
                    "CLAUDE_CODE_ENTRYPOINT": "claude-desktop", "CHANTIER_HOST": "claude"}
        for var in ("CHANTIER_ROOT", "CHANTIER_BATCH", "CHANTIER_PLUGIN_ROOT",
                    *(v for v, _, _ in FAKE.values() if v != FAKE[ARGS.forge][0])):
            self.env.pop(var, None)
        self.last_stderr = ""
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
            f"Run `{GATE}` for both fast and long gates.\n")
        (self.work / ".gitignore").write_text("__pycache__/\n")
        self.sh("git", "add", ".")
        self.sh("git", "commit", "--quiet", "-m", "init", "-m", TRAILER)
        self.sh("git", "remote", "add", "origin", str(origin))
        self.sh("git", "push", "--quiet", "-u", "origin", "main")
        var, _, script = FAKE[ARGS.forge]
        gh = Path(self.env[var])
        gh.parent.mkdir()
        if sys.platform == "win32":
            gh.write_text(f'@"{sys.executable}" "{script}" %*\r\n')
        else:
            gh.write_text(f"#!/bin/sh\nexec {sys.executable} {script} \"$@\"\n")
            gh.chmod(0o755)
        self.gh(checks=[], runs=[], next_pr=40)

    def gh(self, **kw) -> None:
        d = json.loads(self.gh_state.read_text()) if self.gh_state.exists() else {}
        d.update(kw)
        self.gh_state.write_text(json.dumps(d))

    def chantier(self, *args, env=None, expect=0, cwd=None):
        p = subprocess.run([sys.executable, "-m", "chantier", *map(str, args)], cwd=cwd or self.work,
                           env={**self.env, **(env or {})}, capture_output=True, text=True,
                           encoding="utf-8")
        out = p.stdout.strip().splitlines()
        self.last_stderr = p.stderr.strip()
        note(f"    $ chantier {' '.join(map(str, args))}  → exit {p.returncode}")
        for ln in out + ([f"stderr: {self.last_stderr}"] if self.last_stderr else []):
            note(f"      {ln}")
        if expect is not None and p.returncode != expect:
            check(f"chantier {' '.join(map(str, args))} exits {expect}", False,
                  f"exit {p.returncode}: {self.last_stderr[:200]}")
        return p.returncode, out

    def batch(self):
        return json.loads((self.state / "batches" / self.name / "batch.json").read_text())

    def cr(self, cr_id):
        return next(c for c in self.batch()["crs"] if c["id"] == cr_id)


class Foreman:
    """Carries out the action lines `chantier event` prints, as the Foreman would."""

    def __init__(self, w: World, epoch: int):
        self.w, self.epoch = w, epoch
        self.spawned: list[str] = []
        self.asked: list[str] = []
        self.messages: list[str] = []
        self.cancelled: list[str] = []
        self.landed = False

    def event(self, *args) -> list[str]:
        _, out = self.w.chantier("event", *args, "--epoch", self.epoch)
        self.carry_out(out)
        return out

    def carry_out(self, actions: list[str]) -> None:
        for action in actions:
            verb, _, rest = action.partition(" ")
            if verb == "spawn":
                role, target, *note = rest.split(" ", 2)
                _, prompt = self.w.chantier("spawn", role, target,
                                            *(["--note", note[0]] if note else []))
                check(f"`chantier spawn {role} {target}` names the plugin's agent",
                      prompt[:2] == [f"agent: chantier:{role}", "mode: background"], str(prompt))
                self.prompt = prompt
                key = {"cr-driver": target, "release-driver": target,
                       "qa-driver": f"qa:{target}"}.get(role, "stack")
                self.spawned.append(" ".join([key, *note]))
                self.w.chantier("agents", "set", key, f"agent-{len(self.spawned)}",
                                "--epoch", self.epoch)
            elif verb == "ask-chief-of-staff":
                self.asked.append(rest)
            elif verb == "message":
                self.messages.append(rest)
            elif verb == "cancel":
                self.cancelled.append(rest)
                self.w.chantier("cancel", rest, "--epoch", self.epoch)
            elif verb == "merge":
                code, lines = self.w.chantier("merge", rest, "--epoch", self.epoch, expect=None)
                if code:
                    self.asked.append(f"refused {rest} {self.w.last_stderr}")
                else:
                    self.carry_out(lines[1:])
            elif verb == "land":
                self.w.chantier("land", "--epoch", self.epoch)
                self.landed = True


def driver_round(w: World, cr_id: str, filename: str, content: str) -> None:
    """A Coder's change, then the Driver's gates and ship."""
    c = w.cr(cr_id)
    wt = Path(c["worktree"])
    (wt / filename).write_text(content)
    w.sh("git", "add", ".", cwd=wt)
    w.sh("git", "-c", "user.name=coder", "-c", "user.email=coder@example.com", "commit",
         "--quiet", "-m", f"{cr_id}: {filename}", "-m", TRAILER, cwd=wt)
    w.chantier("gate", cr_id)
    w.chantier("report", cr_id, "round-done")
    body = w.work / c["path"] / "work" / "pr-body.md"
    if not body.exists():
        code, _ = w.chantier("ship", cr_id, expect=2)
        check(f"{cr_id} cannot ship before its PR body is written", code == 2)
    body.write_text(f"## {c['title']}\n\nCloses the backlog item.\n")
    w.chantier("ship", cr_id)


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

    note("\n## 2. The Chief of Staff opens the batch from AGENTS.md and starts the Foreman")
    items = [prepare_cr(w, title) for title in
             ("Fix login timeout", "Add CSV export", "Dark mode", "Audit log")]
    code, _ = w.chantier("open", "missing-gates", f"@{items[0][1]}", "--no-worktrees", expect=2)
    check("a missing gate blocks the batch without moving the prepared CR",
          code == 2 and "no fast gate" in w.last_stderr and items[0][1].is_dir())
    code, _ = w.chantier("open", "raw-title", "Fix login", "--no-worktrees", *FROM_AGENTS_MD,
                         expect=1)
    check("a raw title cannot bypass the prepared CR", code == 1 and items[0][1].is_dir())
    w.chantier("open", "night", *(f"@{backlog}" for _, backlog in items),
               "--slots", 2, "--qa", "2", "--budget", 50, "--chief-of-staff", "local_chantier",
               *FROM_AGENTS_MD)
    w.chantier("foreman", "set", "local_foreman1")
    fm = Foreman(w, epoch=1)
    w.chantier("foreman", "transcript", "uuid-foreman", "--epoch", 1)
    d = w.batch()
    check("four CRs, each with a branch and a worktree",
          len(d["crs"]) == 4 and all(Path(c["worktree"]).is_dir() for c in d["crs"]))
    check("opening moves the entire prepared folders into requests",
          all(not backlog.exists() for _, backlog in items)
          and all("/backlog/3-requests/" in c["path"]
                  and (w.work / c["path"] / "intake/request.md").is_file()
                  and (w.work / c["path"] / "03-change-spec.md").is_file() for c in d["crs"]))
    check("the batch keeps the gates the Chief of Staff read in AGENTS.md",
          d["settings"]["gates"] == {"fast": [GATE], "long": [GATE]})
    fm.event("start")
    check("the Foreman spawns two Drivers (two slots)", fm.spawned == ["CR-101", "CR-102"])

    note("\n## 3. CR-101: one round, green CI, hand-back")
    driver_round(w, "CR-101", "login.py", "TIMEOUT_S = 30\n")
    w.gh(checks_seq=[[{"name": "test", "bucket": "pending", "link": ""}],
                     [{"name": "test", "bucket": "pass", "link": ""}]])
    code, out = w.chantier("wait", "ci", "CR-101")
    check("CR-101 CI goes green", out[0].startswith("ci pass"))
    pr101 = w.cr("CR-101")["pr"]
    fm.event("hand-back-ready", "CR-101", pr101)
    check("hand-back frees a slot: CR-103 spawned", fm.spawned[-1] == "CR-103")
    check("the Chief of Staff is told CR-101 is ready with its PR",
          fm.asked[-1] == f"ready CR-101 {pr101}")
    fm.event("driver-done", "CR-101")
    check("the ended Driver after a hand-back needs nothing", fm.spawned[-1] == "CR-103")

    note("\n## 4. CR-102: red CI classified as product, a second round, then QA")
    driver_round(w, "CR-102", "export.py", "def export():\n    return 'csv'\n")
    w.gh(checks_seq=None, checks=[{"name": "test", "bucket": "fail",
                                   "link": "https://github.com/acme/demo/actions/runs/77/job/1"}],
         runs=[], log="AssertionError: export header missing")
    code, out = w.chantier("wait", "ci", "CR-102", expect=4)
    check("CR-102 CI goes red (exit 4)", code == 4)
    code, out = w.chantier("ci", "classify", "CR-102")
    check("the red is classified as product", out[0] == "product")
    w.chantier("report", "CR-102", "ci-red", "export header missing")
    driver_round(w, "CR-102", "export.py", "def export():\n    return 'id,name\\n'\n")
    w.gh(checks=[{"name": "test", "bucket": "pass", "link": ""}])
    w.chantier("wait", "ci", "CR-102")
    fm.event("hand-back-ready", "CR-102", w.cr("CR-102")["pr"])
    check("a QA CR goes to its QA driver first", fm.spawned[-1] == "qa:CR-102")
    w.chantier("qa", "start", "CR-102")
    findings = w.root / "qa-findings.md"
    findings.write_text("# QA\n\n- The export button is hidden on mobile\n")
    code, _ = w.chantier("qa", "done", "CR-102", "--findings", findings, expect=2)
    check("QA without proof in evidence/ is refused", code == 2 and "no proof" in w.last_stderr,
          w.last_stderr)
    evidence = w.work / w.cr("CR-102")["path"] / "evidence"
    evidence.mkdir()
    (evidence / "mobile.txt").write_text("$ open /export at 375px: no export button\n")
    _, out = w.chantier("qa", "done", "CR-102", "--findings", findings)
    fm.event("qa-done", "CR-102", "1 findings")
    check("a QA finding resumes CR-102 with a new Driver and the findings file",
          fm.spawned[-1].startswith("CR-102 resume round: QA found 1 findings: ")
          and fm.spawned[-1].endswith("qa-findings.md"), fm.spawned[-1])
    driver_round(w, "CR-102", "export_ui.py", "VISIBLE_ON_MOBILE = True\n")
    fm.event("hand-back-ready", "CR-102", w.cr("CR-102")["pr"])
    w.chantier("qa", "start", "CR-102")
    findings.write_text("# QA\n\nNo findings.\n")
    w.chantier("qa", "done", "CR-102", "--findings", findings)
    fm.event("qa-done", "CR-102", "0")
    check("a clean QA pass hands CR-102 to the Chief of Staff",
          fm.asked[-1].startswith(f"ready CR-102 {PR_LINK[ARGS.forge]}"))

    note("\n## 5. Steering: the user drops CR-103 and adds a new item")
    _, out = w.chantier("order", "drop", "CR-103")
    check("`chantier order` prints the message with an order id", out == [
        "[chief-of-staff→foreman] order O-1 drop CR-103"])
    # Windows finds a process by its command line only, so the sleeper names its worktree
    wt103 = w.cr("CR-103")["worktree"]
    sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)", wt103],
                               cwd=wt103)
    fm.event("--order", "O-1")
    deadline = time.monotonic() + 5
    while sleeper.poll() is None and time.monotonic() < deadline:
        time.sleep(0.05)
    check("dropping a live CR cancels it and stops its processes",
          fm.cancelled == ["CR-103"] and sleeper.poll() is not None
          and w.cr("CR-103")["status"] == "cancelled")
    check("a dropped CR returns intact to its original backlog folder",
          w.cr("CR-103")["path"] == w.cr("CR-103")["origin"]
          and (w.work / w.cr("CR-103")["path"] / "02-answers.md").is_file())
    check("the freed slot goes to CR-104", "CR-104" in fm.spawned)
    out = fm.event("--order", "O-1")
    check("an order read twice is done once", out == ["ok O-1 already done"])
    _, added = prepare_cr(w, "Rate limit the login endpoint")
    _, out = w.chantier("order", "add", "--note", f"@{added}")
    fm.event("--order", "O-2")
    check("an added item becomes CR-105 with a worktree and takes the second free slot",
          fm.spawned[-1] == "CR-105" and w.cr("CR-105")["status"] == "working"
          and Path(w.cr("CR-105")["worktree"]).is_dir())

    note("\n## 6. A Foreman restart: the old one is refused")
    w.chantier("foreman", "set", "local_foreman2")
    w.chantier("foreman", "transcript", "uuid-foreman", "--epoch", 2)
    code, _ = w.chantier("event", "tick", "--epoch", 1, expect=3)
    check("a stale Foreman (epoch 1) is refused with exit 3", code == 3)
    fm.epoch = 2

    note("\n## 7. CR-104 is lost twice, then hands back; CR-105 runs")
    fm.event("driver-done", "CR-104")
    check("a Driver that ends without a hand-back is resumed",
          fm.spawned[-1] == "CR-104 resume")
    driver_round(w, "CR-104", "audit.py", "AUDIT = []\n")
    fm.event("hand-back-ready", "CR-104", w.cr("CR-104")["pr"])
    driver_round(w, "CR-105", "ratelimit.py", "LIMIT = 10\n")
    fm.event("hand-back-ready", "CR-105", w.cr("CR-105")["pr"])
    _, out = w.chantier("status")
    check("status fits in ten lines and shows every CR",
          len(out) <= 10 and all(f"CR-10{i}" in "\n".join(out) for i in range(1, 6)))

    note("\n## 8. The user merges; the Foreman lands the batch")
    code, _ = w.chantier("land", "--epoch", 2, expect=2)
    check("land is refused while PRs are not merged", code == 2 and w.batch()["status"] == "open")
    fake_transcripts(w, w.batch())
    first = w.cr("CR-101")
    collision =w.work / ".agents/changes/backlog/4-archives" / Path(first["path"]).name
    collision.mkdir(parents=True)
    (collision / "sentinel.txt").write_text("do not overwrite")
    w.chantier("order", "merged", "CR-101")
    code, _ = w.chantier("event", "--order", "O-3", "--epoch", 2, expect=3)
    check("archive collisions are refused without losing either CR folder",
          code == 3 and (collision / "sentinel.txt").read_text() == "do not overwrite"
          and (w.work / first["path"] / "03-change-spec.md").is_file()
          and w.cr("CR-101")["status"] == "ready")
    (collision / "sentinel.txt").unlink()
    collision.rmdir()
    fm.event("--order", "O-3")
    for i, cr_id in enumerate(("CR-102", "CR-104", "CR-105"), 4):
        w.chantier("order", "merged", cr_id)
        fm.event("--order", f"O-{i}")
    check("the last merge makes the Foreman land the batch", fm.landed)
    d = w.batch()
    check("merged worktrees are removed, while the cancelled worktree is preserved",
          d["status"] == "landed" and all(
              Path(c["worktree"]).exists() == (c["status"] == "cancelled") for c in d["crs"]))
    check("merged CR folders move intact to archives only after confirmation",
          all("/backlog/4-archives/" in c["path"]
              and (w.work / c["path"] / "03-change-spec.md").is_file()
              and (w.work / c["path"] / "report.md").is_file()
              for c in d["crs"] if c["status"] == "merged"))
    check("the batch report lists every CR",
          all(c["id"] in (w.state / "batches/night/report.md").read_text()
              for c in d["crs"]))
    prs = {c["id"]: c["pr"] for c in d["crs"] if c["pr"]}
    check("four PRs were opened on the fake forge", len(set(prs.values())) == 4)

    note("\n## 9. Cost")
    code, out = w.chantier("cost", "--by", "cr", "--batch", "night")
    check("Claude cost prices the Foreman and each Driver",
          code == 0 and out[:2] == ["night: $1.304 over 78 model calls",
                                    "foreman: $0.391 (30 calls)"]
          and set(out[2:]) == {f"CR-10{i}: $0.228 (12 calls)" for i in (1, 2, 4, 5)}, str(out))
    code, out = w.chantier("cost", "--summary", "--batch", "night")
    check("the summary gives the total, the budget and orchestration against work",
          code == 0 and out[0] == "Total: $1.30 of a $50 budget"
          and out[1] == "Orchestration $1.30 (100%), work $0.00 (0%)"
          and out[2].startswith("Most: CR-10") and "Chief of Staff" in out[3], str(out))
    report = (w.state / "batches/night/report.md").read_text(encoding="utf-8")
    check("the batch report gives each CR's cost and the summary",
          "| $0.23 |" in report and "## Cost" in report and "Total: $1.30" in report, report)

    note("\n## 10. Copilot cost")
    copilot_cost(w, d)
    copilot_uv(w)

    note("\n## 11. Event log")
    events = (w.state / "batches/night/events.jsonl").read_text().splitlines()
    kinds = {json.loads(e)["kind"] for e in events}
    check("events.jsonl holds the whole story",
          {"open", "spawn", "ship", "wait", "qa-done", "order", "cancel", "land"} <= kinds)
    lifecycle_regressions(w)
    rebase_after_merge(w)
    release(w)
    release_merge_on_approval(w)
    lost_messages(w)


def rebase_after_merge(w: World) -> None:
    note("\n## 13. A merge that leaves a ready PR in conflict")
    _, one = prepare_cr(w, "Clash one")
    _, two = prepare_cr(w, "Clash two")
    w.chantier("open", "clash", f"@{one}", f"@{two}", "--slots", 2, *FROM_AGENTS_MD)
    w.name, w.env["CHANTIER_BATCH"] = "clash", "clash"
    w.chantier("foreman", "set", "local_foreman-clash")
    fm = Foreman(w, epoch=1)
    fm.event("start")
    first, second = (c["id"] for c in w.batch()["crs"])
    for cr_id in (first, second):
        driver_round(w, cr_id, "clash.py", f"WHO = '{cr_id}'\n")
        fm.event("hand-back-ready", cr_id, w.cr(cr_id)["pr"])
    w.sh("git", "push", "--quiet", "origin", f"{w.cr(first)['branch']}:main")  # the user merges
    _, out = w.chantier("order", "merged", first)
    lines = fm.event("--order", out[0].split()[2])
    check("the ready CR that no longer merges goes back to a Driver",
          f"rebase {second}" in lines[0] and fm.spawned[-1] == second, str(lines))
    w.sh("git", "fetch", "--quiet", "origin")


def release(w: World) -> None:
    note("\n## 14. A release: the project's procedure, approvals, a fix, a grant")
    _, change = prepare_cr(w, "Last change")
    _, version = prepare_cr(w, "Release v1.1.0")
    bad = (("--release", 3), ("--release", 2, "--qa", "2"), ("--release", 2, "--auto-merge-fixes",
                                                             "rebase"),
           ("--autonomous-releases", 1, "--budget", 5))
    for args in bad:
        code, _ = w.chantier("open", "ship", f"@{change}", f"@{version}", *FROM_AGENTS_MD, *args,
                             expect=1)
        check(f"open refuses {args}", code == 1 and change.is_dir())
    w.chantier("open", "ship", f"@{change}", f"@{version}", "--release", 2, "--slots", 2,
               "--chief-of-staff", "local_chantier", *FROM_AGENTS_MD)
    w.name, w.env["CHANTIER_BATCH"] = "ship", "ship"
    w.chantier("foreman", "set", "local_foreman3")
    fm = Foreman(w, epoch=1)
    work, rel = (c["id"] for c in w.batch()["crs"])
    fm.event("start")
    check("the release waits for the batch's other CRs", fm.spawned == [work])
    driver_round(w, work, "last.py", "LAST = True\n")
    fm.event("hand-back-ready", work, w.cr(work)["pr"])
    code, _ = w.chantier("merge", work, expect=1)
    check("chantier refuses to merge an ordinary CR", code == 1 and "the user merges" in w.last_stderr)
    _, out = w.chantier("order", "merged", work)
    fm.event("--order", out[0].split()[2])
    check("once it is merged, the Release driver starts", fm.spawned[-1] == rel
          and fm.prompt[0] == "agent: chantier:release-driver"
          and any('(section "Release driver")' in ln for ln in fm.prompt)
          and any("every irreversible action waits" in ln for ln in fm.prompt), str(fm.spawned))

    tag = "push tag v1.1.0"
    w.chantier("release", "start", rel)
    notes = w.work / w.cr(rel)["path"] / "work" / "notes-v1.1.0.md"
    notes.write_text("# v1.1.0\n")
    w.chantier("report", rel, "draft", notes)
    _, out = w.chantier("status")
    check("status shows the draft on the release's line",
          any(ln.startswith(rel) and notes.as_posix() in ln for ln in out), str(out))
    code, out = w.chantier("release", "go", rel, "--note", tag, expect=2)
    check("an irreversible action without approval is refused, with the line to send",
          code == 2 and f"hand-back blocked approval: {tag}" in out[0], str(out))
    fm.event("hand-back-blocked", rel, f"approval: {tag}")
    check("the Chief of Staff gets the approval to ask", fm.asked[-1].startswith(f"blocked {rel} approval:"))
    code, _ = w.chantier("order", "approve", work, "--note", tag, expect=1)
    check("only the release CR takes an approval", code == 1)
    _, out = w.chantier("order", "approve", rel, "--note", tag)
    fm.event("--order", out[0].split()[2])
    check("the approval goes to a new Release driver", fm.spawned[-1] == rel
          and any(ln.startswith("Approved by the user") for ln in fm.prompt), str(fm.prompt))
    code, out = w.chantier("release", "go", rel, "--note", tag)
    check("the approval opens that action", code == 0 and out[0].startswith(f"go: {tag}"))
    code, _ = w.chantier("release", "go", rel, "--note", "publish v1.1.0", expect=2)
    check("an approval is spent once", code == 2)

    fm.event("hand-back-blocked", rel, "fix: the heavy suite fails; work/fix-1.md")
    _, fix = prepare_cr(w, "Fix the heavy suite")
    code, _ = w.chantier("order", "grant", rel, "--note", "releases=1 auto-merge=rebase", expect=1)
    check("a grant without a budget is refused", code == 1 and "budget" in w.last_stderr)
    _, out = w.chantier("order", "grant", rel, "--note",
                        "releases=1 auto-merge=rebase budget=5")
    spawned = len(fm.spawned)
    fm.event("--order", out[0].split()[2])
    check("a grant leaves a release that waits for its fix alone",
          len(fm.spawned) == spawned and w.cr(rel)["status"] == "blocked")
    _, out = w.chantier("order", "fix", rel, "--note", f"@{fix}")
    fm.event("--order", out[0].split()[2])
    fix_id = w.batch()["crs"][-1]["id"]
    check("a fix becomes a CR of the batch; the release waits for it",
          fm.spawned[-1] == fix_id and w.cr(rel)["status"] == "queued"
          and w.cr(fix_id)["fix_for"] == rel, str(fm.spawned))
    driver_round(w, fix_id, "heavy.py", "FIXED = True\n")
    w.gh(merge_refused=True)
    fm.event("hand-back-ready", fix_id, w.cr(fix_id)["pr"])
    check("a merge the forge refuses goes to the Chief of Staff, the fix stays ready",
          fm.asked[-1].startswith(f"refused {fix_id}") and w.cr(fix_id)["status"] == "ready",
          fm.asked[-1])
    w.gh(merge_refused=False)
    fm.carry_out([f"merge {fix_id}"])
    check("under the grant the CLI merges the fix, and the release starts again",
          w.cr(fix_id)["status"] == "merged" and fm.spawned[-1] == rel
          and fm.asked[-1].startswith(f"merged {fix_id} "), str(fm.asked))

    _, out = w.chantier("release", "start", rel)
    check("each new attempt is counted", out[0].startswith("attempt 2:"), str(out))
    w.chantier("report", rel, "note", "release commit")
    wt = Path(w.cr(rel)["worktree"])
    (wt / "VERSION").write_text("1.1.0\n")
    w.sh("git", "add", ".", cwd=wt)
    w.sh("git", "-c", "user.name=release", "-c", "user.email=release@example.com", "commit",
         "--quiet", "-m", "release: v1.1.0", "-m", TRAILER, cwd=wt)
    (w.work / w.cr(rel)["path"] / "work" / "pr-body.md").write_text("Release v1.1.0\n")
    w.chantier("ship", rel)
    code, _ = w.chantier("merge", rel, expect=2)
    check("the release PR does not merge without a go", code == 2)
    state = w.state / "batches" / "ship" / "batch.json"
    data = w.batch()
    state.write_text(json.dumps({**data, "spent_usd": 6}))
    code, out = w.chantier("release", "go", rel, "--note", "publish v1.1.0", expect=5)
    check("past the budget, a grant opens nothing", code == 5 and "budget" in out[0], str(out))
    state.write_text(json.dumps(data))
    code, out = w.chantier("release", "go", rel, "--note", "publish v1.1.0")
    check("the grant opens the action without asking", code == 0 and "without asking" in out[0])
    w.gh(merge_refused=True)
    fm.event("hand-back-blocked", rel, "merge: rebase")
    check("the Foreman merges the release PR; refused, it goes to the Chief of Staff",
          fm.asked[-1].startswith(f"refused {rel}") and w.cr(rel)["status"] == "blocked",
          fm.asked[-1])
    w.gh(merge_refused=False)
    drivers = len(fm.spawned)
    code, out = w.chantier("merge", rel, "--escalated")
    check("the Chief of Staff merges it once, and only the forge moves",
          code == 0 and "order merged" in out[0] and w.cr(rel)["status"] == "blocked", str(out))
    _, out = w.chantier("order", "merged", rel)
    fm.event("--order", out[0].split()[2])
    check("`order merged` sends the release on with a new Driver, not to the archives",
          len(fm.spawned) == drivers + 1 and fm.spawned[-1] == rel
          and "/4-archives/" not in w.cr(rel)["path"], str(fm.spawned))
    w.chantier("release", "published", rel, "--note", "v1.1.0 https://forge.example/v1.1.0")
    code, _ = w.chantier("release", "go", rel, "--note", "publish v1.1.1", expect=2)
    check("the grant ends with its number of releases", code == 2)
    fm.event("hand-back-ready", rel, "https://forge.example/v1.1.0")
    check("the release done, the Chief of Staff hears it and the batch lands",
          fm.asked[-1] == f"released {rel} https://forge.example/v1.1.0" and fm.landed
          and "/4-archives/" in w.cr(rel)["path"], str(fm.asked))
    calls = (w.root / "gh-state.json.calls").read_text()
    check("the forge saw the merges", calls.count("merge") >= 2)


def release_merge_on_approval(w: World) -> None:
    note("\n## 15. A release PR merges on the user's approval, with no new Driver")
    _, version = prepare_cr(w, "Release v1.2.0")
    w.chantier("open", "approve", f"@{version}", "--release", 1, "--chief-of-staff",
               "local_chantier", *FROM_AGENTS_MD)
    w.name, w.env["CHANTIER_BATCH"] = "approve", "approve"
    w.chantier("foreman", "set", "local_foreman4")
    fm = Foreman(w, epoch=1)
    fm.event("start")
    rel = w.batch()["crs"][0]["id"]
    w.chantier("release", "start", rel)
    wt = Path(w.cr(rel)["worktree"])
    (wt / "VERSION").write_text("1.2.0\n")
    w.sh("git", "add", ".", cwd=wt)
    w.sh("git", "-c", "user.name=release", "-c", "user.email=release@example.com", "commit",
         "--quiet", "-m", "release: v1.2.0", "-m", TRAILER, cwd=wt)
    (w.work / w.cr(rel)["path"] / "work" / "pr-body.md").write_text("Release v1.2.0\n")
    w.chantier("ship", rel)
    fm.event("hand-back-blocked", rel, "merge: rebase")
    check("without a grant, the merge is an approval to ask",
          fm.asked[-1].startswith(f"blocked {rel} approval: merge the release PR"), str(fm.asked))
    drivers = len(fm.spawned)
    _, out = w.chantier("order", "approve", rel, "--note", "merge the release PR")
    fm.event("--order", out[0].split()[2])
    check("the approval merges it at once: the only Driver is the one that goes on after",
          fm.asked[-1].startswith(f"merged {rel} ") and len(fm.spawned) == drivers + 1
          and w.cr(rel)["status"] == "working", str(fm.asked))
    fm.event("hand-back-ready", rel, "v1.2.0")
    check("the batch lands", fm.landed)


def lost_messages(w: World) -> None:
    note("\n## 16. Lost messages: the wake catches up, and nothing is left unsaid")
    titles = ("Lost one", "Lost two", "Lost three")
    prepared = [prepare_cr(w, title)[1] for title in titles]
    w.chantier("open", "lost", *(f"@{p}" for p in prepared), "--slots", 3, *FROM_AGENTS_MD)
    w.name, w.env["CHANTIER_BATCH"] = "lost", "lost"
    w.chantier("foreman", "set", "local_foreman5")
    fm = Foreman(w, epoch=1)
    fm.event("start")
    one, two, three = (c["id"] for c in w.batch()["crs"])

    _, out = w.chantier("order", "first", three)  # its line never reaches the Foreman
    order = out[0].split()[2]
    fm.event("tick")
    check("a wake runs an order whose line never came",
          all(o["done"] for o in w.batch()["orders"])
          and any(m.startswith(f"{three} first") for m in fm.messages), str(fm.messages))
    check("the line that arrives late changes nothing",
          fm.event("--order", order) == [f"ok {order} already done"])

    driver_round(w, one, "lost.py", f"WHO = '{one}'\n")
    fm.event("hand-back-ready", one, w.cr(one)["pr"])
    check("a ready CR is told", fm.asked[-1].startswith(f"ready {one} "))
    driver_round(w, two, "lost.py", f"WHO = '{two}'\n")
    w.sh("git", "push", "--quiet", "origin", f"{w.cr(one)['branch']}:main")  # the user merges
    asked = len(fm.asked)
    spawned = len(fm.spawned)
    fm.event("hand-back-ready", two, w.cr(two)["pr"])
    check("a hand-back in conflict tells the Chief of Staff nothing, and waits for its Driver's end",
          len(fm.asked) == asked and len(fm.spawned) == spawned
          and w.cr(two)["status"] == "ready", str(fm.asked))
    fm.event("driver-done", two)
    check("the Driver's end sends it back to a new one",
          fm.spawned[-1] == two and w.cr(two)["status"] == "working", str(fm.spawned))

    driver_round(w, three, "other.py", "OTHER = True\n")
    fm.event("hand-back-ready", three, w.cr(three)["pr"])
    wt = Path(w.cr(three)["worktree"])
    w.sh("git", "fetch", "--quiet", "origin", cwd=wt)
    w.sh("git", "checkout", "--quiet", "--detach", "origin/main", cwd=wt)
    (wt / "other.py").write_text("OTHER = False\n")
    w.sh("git", "add", ".", cwd=wt)
    w.sh("git", "-c", "user.name=user", "-c", "user.email=user@example.com", "commit", "--quiet",
         "-m", "the user moves main", "-m", TRAILER, cwd=wt)
    w.sh("git", "push", "--quiet", "origin", "HEAD:main", cwd=wt)
    w.sh("git", "checkout", "--quiet", w.cr(three)["branch"], cwd=wt)
    out = fm.event("tick")
    check("a wake sends back a ready PR that stopped merging, with no merge to trigger it",
          f"ok rebase {three}" in out and fm.spawned[-1] == three, str(out))

    _, out = w.chantier("status")
    check("status counts the asks unread", any("asks unread" in ln for ln in out), str(out))
    _, out = w.chantier("asks", "refused", one, "the", "host", "said", "no")
    check("the Foreman's own ask is recorded and printed",
          out == [f"[foreman→chief-of-staff] ask refused {one} the host said no"], str(out))
    _, out = w.chantier("asks")
    check("`asks` gives every ask still unread, sent or not",
          out[0].startswith(f"ask ready {one} ")
          and out[-1] == f"ask refused {one} the host said no", str(out))
    _, out = w.chantier("asks")
    check("an ask is read once", out == ["no unread ask"], str(out))


def lifecycle_regressions(w: World) -> None:
    note("\n## 12. Lifecycle recovery")
    _, original = prepare_cr(w, "Preserve failed opening")
    code, _ = w.chantier("open", "rollback", f"@{original}", "--fast-gate", GATE,
                         "--long-gate", GATE, "--default-branch", "missing", expect=4)
    check("a failed worktree creation restores the prepared folder",
          code == 4 and (original / "03-change-spec.md").is_file()
          and not (w.state / "batches/rollback/batch.json").exists())
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
    code, out = w.chantier("cost", "--batch", "night", "--host", "copilot", "--update", env=env)
    check("Copilot cost groups billed and estimated calls by role",
          code == 0 and out == [
              "night: $1.875 over 4 model calls (1 estimated, not billed)",
              "foreman: $1.000 (1 calls)", "cr-driver: $0.500 (1 calls)",
              "coder: $0.375 (2 calls)"], str(out))
    check("Copilot cost updates the batch's recorded spend", w.batch()["spent_usd"] == 1.875)
    code, out = w.chantier("cost", "--batch", "night", "--host", "copilot", "--by", "cr",
                           env=env)
    check("Copilot cost attributes calls by agent, name and other",
          code == 0 and out[1:] == [
              "foreman: $1.000 (1 calls)", f"{assigned['id']}: $0.500 (1 calls)",
              f"{named['id']}: $0.250 (1 calls)", "other: $0.125 (1 calls)"], str(out))

    def fails(label, expected, message, overrides=None):
        code, out = w.chantier("cost", "--batch", "night", "--host", "copilot", "--update",
                               env={**env, **(overrides or {})}, expect=expected)
        check(label, code == expected and not out and message in w.last_stderr
              and w.batch()["spent_usd"] == 1.875,
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
    _, missing = prepare_cr(w, "Missing transcript")
    w.chantier("open", "cost-missing", f"@{missing}", "--no-worktrees", *FROM_AGENTS_MD)
    code, out = w.chantier("cost", "--batch", "cost-missing", "--host", "copilot",
                           env=env, expect=2)
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

    def msg(mid, model, out):
        return json.dumps({"type": "assistant", "message": {"id": mid, "model": model, "usage": {
            "input_tokens": 10, "output_tokens": out, "cache_read_input_tokens": 20_000,
            "cache_creation": {"ephemeral_1h_input_tokens": 2_000}}}}) + "\n"

    main.write_text("".join(msg(f"f{i}", "claude-sonnet-5-5", 300) for i in range(30)))
    for c in d["crs"]:
        if c.get("agent"):
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
