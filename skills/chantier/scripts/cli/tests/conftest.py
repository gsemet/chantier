"""Fixtures: a git repository with a bare origin, chantier set up, and a fake `gh` on CHANTIER_GH."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from chantier.cli import main

SKILL = Path(__file__).resolve().parents[3]
FAKE_GH = Path(__file__).with_name("fake_gh.py")


def sh(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    origin = tmp_path / "origin.git"
    work = tmp_path / "proj"
    sh("git", "init", "--quiet", "--bare", "-b", "main", str(origin))
    sh("git", "init", "--quiet", "-b", "main", str(work))
    for k, v in (("user.name", "t"), ("user.email", "t@example.com")):
        sh("git", "config", k, v, cwd=work)
    (work / "README.md").write_text("demo\n")
    sh("git", "add", ".", cwd=work)
    sh("git", "commit", "--quiet", "-m", "init", cwd=work)
    sh("git", "remote", "add", "origin", str(origin), cwd=work)
    sh("git", "push", "--quiet", "-u", "origin", "main", cwd=work)

    gh = tmp_path / "bin" / "gh"
    gh.parent.mkdir()
    gh.write_text(f"#!/bin/sh\nexec {sys.executable} {FAKE_GH} \"$@\"\n")
    gh.chmod(0o755)
    state = tmp_path / "gh-state.json"
    state.write_text(json.dumps({"checks": [], "runs": [], "next_pr": 1}))

    monkeypatch.chdir(work)
    monkeypatch.setenv("CHANTIER_SKILL_DIR", str(SKILL))
    monkeypatch.setenv("CHANTIER_GH", str(gh))
    monkeypatch.setenv("FAKE_GH_STATE", str(state))
    monkeypatch.setenv("CHANTIER_WAIT_INTERVAL", "0.05")
    monkeypatch.setenv("CHANTIER_CLAUDE_PROJECTS", str(tmp_path / "claude-projects"))
    monkeypatch.setenv("CHANTIER_MODELS_USER", str(tmp_path / "user-models.yml"))
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path / "copilot-home"))
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    for var in ("CHANTIER_ROOT", "CHANTIER_BATCH", "CLAUDE_CODE_ENTRYPOINT", "COPILOT_CLI",
                "COPILOT_AGENT_SESSION_ID", "AI_AGENT"):
        monkeypatch.delenv(var, raising=False)
    return work


@pytest.fixture
def gh_state(tmp_path):
    path = tmp_path / "gh-state.json"

    class State:
        def set(self, **kw):
            d = json.loads(path.read_text())
            d.update(kw)
            path.write_text(json.dumps(d))

        def calls(self):
            log = tmp_path / "gh-state.json.calls"
            return [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []

    return State()


@pytest.fixture
def chantier(capsys):
    """Run `chantier …` in-process; returns (exit code, stdout lines, stderr)."""

    def run(*args):
        code = main([str(a) for a in args])
        out = capsys.readouterr()
        return code, out.out.splitlines(), out.err

    return run


@pytest.fixture
def ready(repo, chantier):
    """chantier set up, one parallel batch `b1` of three CRs, two slots."""
    assert chantier("setup")[0] == 0
    code, out, err = chantier("open", "b1", "Fix login", "Add export", "Dark mode", "--slots", 2)
    assert code == 0, err
    return repo
