#!/usr/bin/env python3
"""Global scenario: one whole chantier batch, end to end, through the real CLI.

A scripted Foreman feeds events to `chantier event` and carries out the actions it prints; scripted
Drivers commit in their CR worktree, run the gates, ship to a bare origin, wait on a fake `gh`
and hand back. The Chief of Staff steers with `chantier order`. Nothing calls a model.

    python3 evals/scenario/run_scenario.py [--keep] [--verbose]

Exit 0 when every check passes; the transcript is written to evals/results/scenario-<time>.md.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2]
FAKE_GH = Path(__file__).with_name("fake_gh.py")
LOG: list[str] = []
CHECKS = {"pass": 0, "fail": 0}


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
        self.gh_state = root / "gh-state.json"
        self.env = {**os.environ, "PYTHONPATH": str(SKILL / "scripts" / "cli" / "src"),
                    "CHANTIER_SKILL_DIR": str(SKILL),
                    "CHANTIER_GH": str(root / "bin" / ("gh.cmd" if sys.platform == "win32"
                                                       else "gh")),
                    "FAKE_GH_STATE": str(self.gh_state), "CHANTIER_WAIT_INTERVAL": "0.05",
                    "CHANTIER_CLAUDE_PROJECTS": str(root / "claude-projects"),
                    "CLAUDE_CODE_ENTRYPOINT": "claude-desktop"}
        for var in ("CHANTIER_ROOT", "CHANTIER_BATCH"):
            self.env.pop(var, None)

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
        (self.work / ".gitignore").write_text("__pycache__/\n")
        self.sh("git", "add", ".")
        self.sh("git", "commit", "--quiet", "-m", "init")
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
        note(f"    $ chantier {' '.join(map(str, args))}  → exit {p.returncode}")
        for ln in out + ([f"stderr: {p.stderr.strip()}"] if p.stderr.strip() else []):
            note(f"      {ln}")
        if expect is not None and p.returncode != expect:
            check(f"chantier {' '.join(map(str, args))} exits {expect}", False,
                  f"exit {p.returncode}: {p.stderr.strip()[:200]}")
        return p.returncode, out

    def batch(self, name="night"):
        return json.loads((self.work / ".agents/changes/batches" / name / "batch.json").read_text())

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
                self.spawned.append(rest)
                self.w.chantier("agents", "set", rest.split()[0], f"agent-{len(self.spawned)}",
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
         "--quiet", "-m", f"{cr_id}: {filename}", cwd=wt)
    w.chantier("gate", cr_id)
    w.chantier("report", cr_id, "round-done")
    body = w.work / ".agents/changes/batches/night/crs" / cr_id / "pr-body.md"
    body.write_text(f"## {c['title']}\n\nCloses the backlog item.\n")
    w.chantier("ship", cr_id)


def scenario(w: World) -> None:
    note("## 1. Setup and preflight")
    w.chantier("setup")
    check("setup writes no config file for the defaults",
          not (w.work / ".agents/chantier.json").exists())
    (w.work / ".agents").mkdir(exist_ok=True)
    (w.work / ".agents/chantier.json").write_text(json.dumps(
        {"gates": {"fast": [f'"{sys.executable}" -m compileall -q .'], "long": []}}, indent=2))
    w.sh("git", "add", ".")
    w.sh("git", "commit", "--quiet", "-m", "chantier setup")
    w.sh("git", "push", "--quiet")
    code, out = w.chantier("preflight", env={"CLAUDE_CODE_ENTRYPOINT": "claude-vscode"}, expect=2)
    check("preflight refuses Claude in VS Code (P1) and says to start nothing",
          code == 2 and out[0].startswith("P1 FAIL") and out[-1].endswith("start nothing"))
    check("a refused preflight creates no batch", not (w.work / ".agents/changes/batches").exists()
          or not any((w.work / ".agents/changes/batches").iterdir()))
    code, out = w.chantier("preflight")
    check("preflight passes on Claude Desktop", code == 0 and out[-1] == "preflight passed")

    note("\n## 2. The Chief of Staff opens the batch and starts the Foreman")
    w.chantier("open", "night", "Fix login timeout", "Add CSV export", "Dark mode", "Audit log",
          "--slots", 2, "--qa", "2", "--budget", 50, "--chief-of-staff", "local_chantier")
    w.chantier("foreman", "set", "local_foreman1")
    fm = Foreman(w, epoch=1)
    w.chantier("foreman", "transcript", "uuid-foreman", "--epoch", 1)
    d = w.batch()
    check("four CRs, each with a branch and a worktree",
          len(d["crs"]) == 4 and all(Path(c["worktree"]).is_dir() for c in d["crs"]))
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
    fm.event("anomaly", "CR-102", "fix the QA finding")
    check("a QA finding resumes CR-102 with a new Driver",
          fm.spawned[-1] == "CR-102 resume round: fix the QA finding")
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
    check("the freed slot goes to CR-104", "CR-104" in fm.spawned)
    out = fm.event("--order", "O-1")
    check("an order read twice is done once", out == ["ok O-1 already done"])
    _, out = w.chantier("order", "add", "--note", "Rate limit the login endpoint")
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
    for i, cr_id in enumerate(("CR-101", "CR-102", "CR-104", "CR-105"), 3):
        w.chantier("order", "merged", cr_id)
        fm.event("--order", f"O-{i}")
    check("the last merge makes the Foreman land the batch", fm.landed)
    d = w.batch()
    check("the batch is landed and its worktrees removed",
          d["status"] == "landed" and not any(Path(c["worktree"]).exists() for c in d["crs"]))
    check("the batch report lists every CR",
          all(c["id"] in (w.work / ".agents/changes/batches/night/report.md").read_text()
              for c in d["crs"]))
    prs = {c["id"]: c["pr"] for c in d["crs"] if c["pr"]}
    check("four PRs were opened on the fake forge", len(set(prs.values())) == 4)

    note("\n## 9. Cost")
    fake_transcripts(w, d)
    _, out = w.chantier("cost", "--by", "cr", "--batch", "night")
    check("cost prices the Foreman and each Driver",
          out[0].startswith("night: $") and any(ln.startswith("CR-101: $") for ln in out))
    events = (w.work / ".agents/changes/batches/night/events.jsonl").read_text().splitlines()
    kinds = {json.loads(e)["kind"] for e in events}
    check("events.jsonl holds the whole story",
          {"open", "spawn", "ship", "wait", "qa-done", "order", "cancel", "land"} <= kinds)


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
    results = SKILL / "evals" / "results"
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
