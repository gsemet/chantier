"""Fixtures: a fresh git repository where the skill runs from this checkout's plugin."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any, NamedTuple

import pytest
from forge_world import World

from chantier.cli import main
from chantier.core import git as git_module

SKILL = Path(__file__).resolve().parents[3]
PLUGIN_ROOT = SKILL.parents[1]
Chantier = Callable[..., tuple[int, list[str], str]]
SEEDED_COMMON_DIRS: dict[str, str] = {}  # folder -> its git common dir, for the `repo` copies


def _key(folder: Path | str | None) -> str:
    return os.path.normcase(os.path.realpath(folder or os.getcwd()))


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


@pytest.fixture(scope="session")
def repo_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The git repository every test starts from, built once: `repo` copies it (git is slow)."""
    work = tmp_path_factory.mktemp("template") / "proj"
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
    return work


@pytest.fixture
def repo(repo_template: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    work = tmp_path / "proj"
    shutil.copytree(repo_template, work)
    monkeypatch.chdir(work)
    # a plain copy keeps its own `.git`: `chantier` answers that without a git process, while
    # nothing moves it (a test that makes a worktree or moves the folder asks the real git)
    monkeypatch.setitem(SEEDED_COMMON_DIRS, _key(work), str(work / ".git"))
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
        "CLAUDE_CODE_SESSION_ID",
        "COPILOT_CLI",
        "COPILOT_AGENT_SESSION_ID",
        "AI_AGENT",
    ):
        monkeypatch.delenv(var, raising=False)
    return work


class Surface(NamedTuple):
    root: Path  # the planning surface, a git repository: the session's folder
    project: Path  # `projects/demo`, with its `checkout.yml`
    clone: Path  # the project's code repository, `projects/demo/.repo`


@pytest.fixture(scope="session")
def surface_template(repo_template: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The external planning surface every `surface` test starts from, built once per session
    (and per worker): a git repository with one project `demo`, whose clone is a copy of the
    template repository inside the project's folder."""
    root = tmp_path_factory.mktemp("surface-template") / "surface"
    project = root / "projects" / "demo"
    project.mkdir(parents=True)
    (project / "checkout.yml").write_text("repo: .repo\nworktrees: ../../../wt\n")
    shutil.copytree(repo_template, project / ".repo")
    sh("git", "init", "--quiet", "-b", "main", str(root))
    sh("git", "add", "projects/demo/checkout.yml", cwd=root)
    sh(
        "git",
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.com",
        "commit",
        "-qm",
        "init",
        cwd=root,
    )
    return root


@pytest.fixture
def surface(
    repo: Path, surface_template: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Surface:
    """A small external planning surface with one project `demo`, whose clone is a copy of `repo`
    inside the project's folder; the session runs in the surface."""
    root = tmp_path / "surface"
    shutil.copytree(surface_template, root)
    monkeypatch.chdir(root)
    return Surface(
        root.resolve(),
        (root / "projects" / "demo").resolve(),
        (root / "projects" / "demo" / ".repo").resolve(),
    )


@pytest.fixture
def chantier(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> Chantier:
    """Run `chantier ...` in-process; returns (exit code, stdout lines, stderr).

    Every command asks git for the repository's common folder, a process of 0.1 s on Windows:
    a test's repository does not move, so the answer is kept per folder."""
    real_git = git_module.git
    asked: dict[str, str] = {}

    def git_cached(*args: str, cwd: Path | None = None, **kw: Any) -> str:
        if args[:3] != ("rev-parse", "--path-format=absolute", "--git-common-dir"):
            return str(real_git(*args, cwd=cwd, **kw))
        key = _key(cwd)
        if key in SEEDED_COMMON_DIRS and (Path(SEEDED_COMMON_DIRS[key]) / "HEAD").is_file():
            return SEEDED_COMMON_DIRS[key]
        if key not in asked:
            asked[key] = str(real_git(*args, cwd=cwd, **kw))
        return asked[key]

    monkeypatch.setattr("chantier.core.repo.git", git_cached)

    def run(*args: object) -> tuple[int, list[str], str]:
        code = main([str(a) for a in args])
        out = capsys.readouterr()
        return code, out.out.splitlines(), out.err

    return run


@pytest.fixture
def world(surface: Surface, monkeypatch: pytest.MonkeyPatch) -> World:
    """`forge_world.World`: a surface of four projects and a fake forge."""
    return World(surface, monkeypatch)
