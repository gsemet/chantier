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
    sh("git", "add", ".", cwd=work)
    sh("git", "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "--quiet",
       "-m", "init", cwd=work)
    monkeypatch.chdir(work)
    monkeypatch.setenv("CHANTIER_SKILL_DIR", str(SKILL))
    monkeypatch.setenv("CHANTIER_PLUGIN_ROOT", str(PLUGIN_ROOT))
    monkeypatch.setenv("CHANTIER_MODELS_USER", str(tmp_path / "user-models.yml"))
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
