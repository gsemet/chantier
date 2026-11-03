#!/usr/bin/env python3
"""Global scenario: one whole chantier batch, end to end, through the real CLI.

A scripted Foreman feeds events to `chantier event` and carries out the actions it prints; scripted
Drivers commit in their CR worktree, run the gates, ship to a bare origin, wait on a fake `gh`
and hand back. The Chief of Staff steers with `chantier order`. Nothing calls a model.

    uv run --no-project python evals/scenario/run_scenario.py [--keep] [--verbose]

Exit 0 when every check passes; the transcript is written to evals/results/scenario-<time>.md.
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

EVALS = Path(__file__).resolve().parents[1]
SKILL = EVALS.parent / "skills" / "chantier"
FAKE_GH = Path(__file__).with_name("fake_gh.py")
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
        self.env = {**os.environ, "PYTHONPATH": str(SKILL / "scripts" / "cli" / "src"),
                    "CHANTIER_SKILL_DIR": str(SKILL),
                    "CHANTIER_GH": str(root / "bin" / ("gh.cmd" if sys.platform == "win32"
                                                       else "gh")),
                    "FAKE_GH_STATE": str(self.gh_state), "CHANTIER_WAIT_INTERVAL": "0.05",
                    "CHANTIER_CLAUDE_PROJECTS": str(root / "claude-projects"),
                    "CLAUDE_CODE_ENTRYPOINT": "claude-desktop", "CHANTIER_HOST": "claude"}
        for var in ("CHANTIER_ROOT", "CHANTIER_BATCH", "CHANTIER_PLUGIN_ROOT"):
            self.env.pop(var, None)
        self.last_stderr = ""

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
        gh = Path(self.env["CHANTIER_GH"])
        gh.parent.mkdir()
        if sys.platform == "win32":
            gh.write_text(f'@"{sys.executable}" "{FAKE_GH}" %*\r\n')
        else:
            gh.write_text(f"#!/bin/sh\nexec {sys.executable} {FAKE_GH} \"$@\"\n")
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

    def batch(self, name="night"):
        return json.loads((self.state / "batches" / name / "batch.json").read_text())

    def cr(self, cr_id, name="night"):
        return next(c for c in self.batch(name)["crs"] if c["id"] == cr_id)


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
        for action in out:
            verb, _, rest = action.partition(" ")
            if verb == "spawn":
                role, target, *note = rest.split(" ", 2)
                _, prompt = self.w.chantier("spawn", role, target,
                                            *(["--note", note[0]] if note else []))
                check(f"`chantier spawn {role} {target}` names the plugin's agent",
                      prompt[:2] == [f"agent: chantier:{role}", "mode: background"], str(prompt))
                key = {"cr-driver": target, "qa-driver": f"qa:{target}"}.get(role, "stack")
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
            elif verb == "land":
                self.w.chantier("land", "--epoch", self.epoch)
                self.landed = True
        return out


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
          fm.asked[-1].startswith("ready CR-102 https://github.com/acme/demo/pull/"))

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
    first = w.cr("CR-101")
    collision = w.work / ".agents/changes/backlog/4-archives" / Path(first["path"]).name
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
    fake_transcripts(w, d)
    code, out = w.chantier("cost", "--by", "cr", "--batch", "night")
    check("Claude cost prices the Foreman and each Driver",
          code == 0 and out[:2] == ["night: $1.304 over 78 model calls",
                                    "foreman: $0.391 (30 calls)"]
          and set(out[2:]) == {f"CR-10{i}: $0.228 (12 calls)" for i in (1, 2, 4, 5)}, str(out))

    note("\n## 10. Copilot cost")
    copilot_cost(w, d)
    copilot_uv(w)

    note("\n## 11. Event log")
    events = (w.state / "batches/night/events.jsonl").read_text().splitlines()
    kinds = {json.loads(e)["kind"] for e in events}
    check("events.jsonl holds the whole story",
          {"open", "spawn", "ship", "wait", "qa-done", "order", "cancel", "land"} <= kinds)
    lifecycle_regressions(w)


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
    head = [f"# chantier global scenario: {CHECKS['pass']}/{total} checks passed",
            "", f"- Run: {time.strftime('%Y-%m-%d %H:%M:%S')}, {elapsed:.1f} s",
            f"- Workspace: `{tmp}`{' (kept)' if ARGS.keep else ' (removed)'}", ""]
    results = EVALS / "results"
    results.mkdir(exist_ok=True)
    out = results / f"scenario-{time.strftime('%Y%m%d-%H%M%S')}.md"
    out.write_text("\n".join(head + LOG) + "\n", encoding="utf-8")
    print(f"{CHECKS['pass']}/{total} checks passed in {elapsed:.1f} s; transcript {out}")
    return 0 if CHECKS["fail"] == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true", help="keep the temporary workspace")
    parser.add_argument("--verbose", action="store_true", help="print the transcript live")
    ARGS = parser.parse_args()
    sys.exit(main())
