"""Fixtures: a fresh git repository where the skill runs from this checkout's plugin."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from chantier.cli import main

SKILL = Path(__file__).resolve().parents[3]
PLUGIN_ROOT = SKILL.parents[1]


def sh(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True,
                          encoding="utf-8").stdout.strip()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    work = tmp_path / "proj"
    sh("git", "init", "--quiet", "-b", "main", str(work))
    (work / "README.md").write_text("demo\n")
    (work / "AGENTS.md").write_text("# Project instructions\n\nRun `just check`.\n")
    sh("git", "add", ".", cwd=work)
    sh("git", "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "--quiet",
       "-m", "init", cwd=work)
    # a self-managed GitLab; the fake glab is never called by what the tests run
    sh("git", "remote", "add", "origin", "git@gitlab.example.com:acme/demo.git", cwd=work)
    origin = tmp_path / "origin.git"  # `open` fetches: that address leads here
    sh("git", "clone", "--quiet", "--bare", str(work), str(origin))
    sh("git", "config", f"url.{origin.as_posix()}.insteadOf",
       "git@gitlab.example.com:acme/demo.git", cwd=work)
    monkeypatch.setenv("CHANTIER_GLAB", "fake-glab")
    monkeypatch.delenv("CHANTIER_GH", raising=False)
    monkeypatch.chdir(work)
    monkeypatch.setenv("CHANTIER_SKILL_DIR", str(SKILL))
    monkeypatch.setenv("CHANTIER_PLUGIN_ROOT", str(PLUGIN_ROOT))
    # the user's own agents live in the home folder: keep the real one out of the tests
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    for var in ("CHANTIER_ROOT", "CHANTIER_BATCH", "CHANTIER_HOST", "CLAUDE_CODE_ENTRYPOINT",
                "COPILOT_CLI", "COPILOT_AGENT_SESSION_ID", "AI_AGENT"):
        monkeypatch.delenv(var, raising=False)
    return work


@pytest.fixture
def chantier(capsys):
    """Run `chantier …` in-process; returns (exit code, stdout lines, stderr)."""

    def run(*args):
        code = main([str(a) for a in args])
        out = capsys.readouterr()
        return code, out.out.splitlines(), out.err

    return run
