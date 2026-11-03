#!/usr/bin/env python3
"""Stage the current directory for one eval case: a git repo and a batch in a state.

    uv run --no-project python evals/lib/seed.py <bare|running|cost>

Runs the real CLI (no model); the batch state is reached through `chantier` commands only.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2]
WORK = Path.cwd()
ENV = {**os.environ, "PYTHONPATH": str(SKILL / "scripts" / "cli" / "src"), "CHANTIER_SKILL_DIR": str(SKILL)}


def sh(*args):
    subprocess.run(args, cwd=WORK, check=True, capture_output=True, text=True)


def chantier(*args):
    p = subprocess.run([sys.executable, "-m", "chantier", *map(str, args)], cwd=WORK, env=ENV,
                       capture_output=True, text=True)
    if p.returncode:
        sys.exit(f"seed: chantier {' '.join(map(str, args))}: {p.stderr.strip()}")
    return p.stdout.strip().splitlines()


def repo():
    if not (WORK / ".git").exists():
        sh("git", "init", "--quiet", "-b", "main")
    sh("git", "config", "user.name", "eval")
    sh("git", "config", "user.email", "eval@example.com")
    (WORK / "app.py").write_text("def login():\n    return True\n")
    (WORK / "AGENTS.md").write_text("# Project instructions\n\nDefault branch: `main`.\n"
                                   "Run `uv run --no-project python -m compileall -q .` "
                                   "for both gates.\n")
    (WORK / ".gitignore").write_text("__pycache__/\n.chantier-fixtures/\n")
    sh("git", "add", ".")
    sh("git", "commit", "--quiet", "-m", "init", "-m",
       "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>")


def prepared(title):
    line = chantier("file", title)[0]
    folder = WORK / line.removeprefix("filed ").split(";", 1)[0]
    (folder / "01-intent.md").write_text(f"# {title}\n")
    (folder / "02-answers.md").write_text("# Decisions\n\nNo open questions.\n")
    (folder / "03-change-spec.md").write_text(f"# {title}\n\nImplement {title}.\n")
    return f"@{folder}"


def running(claude_projects_dir=None):
    """Batch `night`: CR-101 ready with a PR, CR-102 working in round 2, CR-103 blocked."""
    items = [prepared(title) for title in ("Fix login timeout", "Add CSV export", "Dark mode")]
    gate = "uv run --no-project python -m compileall -q ."
    extra = ["--claude-projects-dir", claude_projects_dir] if claude_projects_dir else []
    chantier("open", "night", *items, "--slots", 2, "--no-worktrees",
             "--chief-of-staff", "local_chantier_eval", "--fast-gate", gate, "--long-gate", gate,
             "--default-branch", "main", *extra)
    chantier("foreman", "set", "local_foreman_eval")
    chantier("event", "start", "--epoch", 1)
    chantier("agents", "set", "CR-101", "a101", "--epoch", 1)
    chantier("agents", "set", "CR-102", "a102", "--epoch", 1)
    chantier("report", "CR-101", "pr-opened", "https://github.com/acme/demo/pull/40")
    chantier("report", "CR-101", "ci-green")
    chantier("report", "CR-101", "round-done", "r1 APPROVE")
    chantier("event", "hand-back-ready", "CR-101", "https://github.com/acme/demo/pull/40",
        "--epoch", 1)
    chantier("agents", "set", "CR-103", "a103", "--epoch", 1)
    chantier("report", "CR-102", "round-done", "r1 FIX-REQUIRED missing header")
    chantier("report", "CR-102", "round-done", "r2 in progress")
    chantier("event", "hand-back-blocked", "CR-103",
        "the design system has no dark tokens; the user must choose a palette", "--epoch", 1)


def cost():
    """`running`, plus Foreman and subagent transcripts: Sonnet, $1.60 in total."""
    running(".chantier-fixtures/claude-projects")
    chantier("foreman", "transcript", "uuid-eval", "--epoch", 1)
    slug = "".join(ch if ch.isalnum() else "-" for ch in str(WORK.resolve()))
    main = WORK / ".chantier-fixtures" / "claude-projects" / slug / "uuid-eval.jsonl"
    sub = main.with_suffix("") / "subagents"
    sub.mkdir(parents=True)

    def msg(mid, out):
        return json.dumps({"type": "assistant", "message": {
            "id": mid, "model": "claude-sonnet-5-5",
            "usage": {"input_tokens": 0, "output_tokens": out, "cache_read_input_tokens": 0,
                      "cache_creation": {}}}}) + "\n"

    main.write_text(msg("f1", 100_000))  # $1.00
    for agent, kind, out in (("a101", "cr-driver", 30_000), ("a102", "cr-driver", 20_000),
                             ("c9", "coder", 10_000)):  # $0.30, $0.20, $0.10
        (sub / f"agent-{agent}.jsonl").write_text(msg(agent, out))
        (sub / f"agent-{agent}.meta.json").write_text(json.dumps({"agentType": kind}))


if __name__ == "__main__":
    kind = sys.argv[1] if len(sys.argv) > 1 else "bare"
    repo()
    {"bare": lambda: None, "running": running, "cost": cost}[kind]()
    print(f"seeded {kind} in {WORK}")
