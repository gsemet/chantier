"""Fixtures: a fresh git repository where the skill runs from this checkout's plugin."""

from __future__ import annotations

import importlib.util
import subprocess
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

from chantier.cli import main

SKILL = Path(__file__).resolve().parents[3]
PLUGIN_ROOT = SKILL.parents[1]
Chantier = Callable[..., tuple[int, list[str], str]]


def load_script(name: str, path: Path) -> ModuleType:
    """Import a script of the repository by its path."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sh(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(
        args, cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    work = tmp_path / "proj"
    sh("git", "init", "--quiet", "-b", "main", str(work))
    (work / "README.md").write_text("demo\n")
    (work / "AGENTS.md").write_text("# Project instructions\n\nRun `just check`.\n")
    sh("git", "add", ".", cwd=work)
    sh(
        "git",
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.com",
        "commit",
        "--quiet",
        "-m",
        "init",
        cwd=work,
    )
    # `open` checks that the remote exists; nothing reaches it
    sh("git", "remote", "add", "origin", "git@gitlab.example.com:acme/demo.git", cwd=work)
    monkeypatch.chdir(work)
    monkeypatch.setenv("CHANTIER_SKILL_DIR", str(SKILL))
    monkeypatch.setenv("CHANTIER_PLUGIN_ROOT", str(PLUGIN_ROOT))
    # the user's own agents live in the home folder: keep the real one out of the tests
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    for var in (
        "CHANTIER_ROOT",
        "CHANTIER_BATCH",
        "CHANTIER_HOST",
        "CLAUDE_CODE_ENTRYPOINT",
        "COPILOT_CLI",
        "COPILOT_AGENT_SESSION_ID",
        "AI_AGENT",
    ):
        monkeypatch.delenv(var, raising=False)
    return work


@pytest.fixture
def chantier(capsys: pytest.CaptureFixture[str]) -> Chantier:
    """Run `chantier …` in-process; returns (exit code, stdout lines, stderr)."""

    def run(*args: object) -> tuple[int, list[str], str]:
        code = main([str(a) for a in args])
        out = capsys.readouterr()
        return code, out.out.splitlines(), out.err

    return run
