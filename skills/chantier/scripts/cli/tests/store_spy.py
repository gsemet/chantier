"""The spy of the command table of the plan's store (`test_store_command_table.py`): a wrapper
over `Repo.store` that records every call, the fingerprint of a project's folder, and the states
the rows start from, built once per session from the shared surface template."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from conftest import PLUGIN_ROOT as ROOT
from conftest import SEEDED_COMMON_DIRS, SKILL, Surface, _key, live_writer

from chantier.cli import main
from chantier.core.repo import Repo
from chantier.store.base import PlanStore

WRITES = (
    "write_text",
    "write_json",
    "write_bytes",
    "make_folder",
    "write_config",
    "move",
    "remove",
)
MAIN = ("--default-branch", "main")


@dataclass
class Spy:
    """The store of a `Repo`, recording each call in order; the fingerprint of the project's
    folder is taken when `check_publish` is called."""

    real: PlanStore
    project: Path
    calls: list[tuple[str, tuple[str, ...], dict[str, Any]]] = field(default_factory=list)
    prints: list[dict[str, bytes | None]] = field(default_factory=list)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.real, name)

    def _record(self, name: str, rels: tuple[str, ...], **extra: Any) -> None:
        self.calls.append((name, rels, extra))

    def check_publish(
        self, rels: list[str], *, config: bool = False, command: str | None = None
    ) -> None:
        self.prints.append(fingerprint(self.project))
        self._record("check_publish", tuple(rels), config=config, command=command)
        self.real.check_publish(rels, config=config, command=command)

    def ensure_gitignore(self) -> None:
        self._record("ensure_gitignore", ())
        self.real.ensure_gitignore()

    def move(self, rel_src: str, rel_dst: str) -> None:
        self._record("move", (rel_src, rel_dst))
        self.real.move(rel_src, rel_dst)

    def make_folder(self, rel: str, exist_ok: bool) -> None:
        self._record("make_folder", (rel,))
        self.real.make_folder(rel, exist_ok)

    def write_config(self, data: bytes) -> None:
        self._record("write_config", ())
        self.real.write_config(data)

    def _one(self, name: str, rel: str, *args: Any, **kw: Any) -> Any:
        self._record(name, (rel,))
        return getattr(self.real, name)(rel, *args, **kw)

    def write_text(self, rel: str, text: str) -> None:
        self._one("write_text", rel, text)

    def write_json(self, rel: str, data: Any, **kw: Any) -> None:
        self._one("write_json", rel, data, **kw)

    def write_bytes(self, rel: str, data: bytes) -> None:
        self._one("write_bytes", rel, data)

    def remove(self, rel: str) -> None:
        self._one("remove", rel)


def fingerprint(project: Path) -> dict[str, bytes | None]:
    """Every path of the project's folder, outside the clone, with its bytes."""
    found: dict[str, bytes | None] = {}
    for p in sorted(project.rglob("*")):
        rel = p.relative_to(project).as_posix()
        if rel == ".repo" or rel.startswith(".repo/"):
            continue
        # a lock file is held (and unreadable on Windows) while a command runs: its presence only
        found[rel] = p.read_bytes() if p.is_file() and not p.name.endswith(".lock") else None
    return found


def unguarded(found: dict[str, bytes | None]) -> dict[str, bytes | None]:
    """Without the planning folder's `.gitignore` (written through the store, never checked) and
    the folder that holds it."""
    return {k: v for k, v in found.items() if k not in ("changes", "changes/.gitignore")}


def under(path: str, base: str) -> bool:
    return path == base or path.startswith(base + "/")


def install_spy(monkeypatch: pytest.MonkeyPatch) -> dict[int, Spy]:
    """`Repo.store` answers a spy over the real store, one per store; the dict holds them."""
    made: dict[int, Spy] = {}
    real_store = Repo.store.fget  # type: ignore[attr-defined]

    def store(self: Repo) -> Spy:
        real = real_store(self)
        if id(real) not in made:
            made[id(real)] = Spy(real, self.project_dir or self.root)
        return made[id(real)]

    monkeypatch.setattr(Repo, "store", property(store))
    return made


def _environment(mp: pytest.MonkeyPatch, home: Path) -> None:
    mp.setenv("CHANTIER_SKILL_DIR", str(SKILL))
    mp.setenv("CHANTIER_PLUGIN_ROOT", str(ROOT))
    mp.setenv("HOME", str(home))
    mp.setenv("USERPROFILE", str(home))
    mp.setenv("CHANTIER_HOST", "claude")
    mp.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")
    for var in ("CHANTIER_ROOT", "CHANTIER_BATCH", "COPILOT_CLI", "AI_AGENT"):
        mp.delenv(var, raising=False)


def _run(*argv: object) -> None:
    code = main([str(a) for a in argv])
    assert code == 0, argv


def _build(root: Path, state: str) -> None:
    """`backlog`: items in the inbox and a trashed one; `batch`: and a batch of three CRs."""
    changes = root / "projects" / "demo" / "changes"
    if state == "backlog":
        for title in ("idea a", "Alpha", "Beta", "Gamma", "Delta", "Old"):
            _run("file", title)
        for name in ("alpha", "beta", "gamma", "delta"):
            (changes / "1-inbox" / name / "03-change-spec.md").write_text(
                f"# {name}\n\nDo it.\n", encoding="utf-8"
            )
        _run("abandon", "1-inbox/old")
    else:
        _run("open", *(f"1-inbox/{n}" for n in ("alpha", "beta", "gamma")), *MAIN)


def build_states(surface_template: Path, factory: pytest.TempPathFactory) -> dict[str, Path]:
    """`bare`: the surface template; `backlog`: items filed; `batch`: and a batch opened."""
    home = factory.mktemp("table-home")
    made = {"bare": surface_template}
    for state, source in (("backlog", "bare"), ("batch", "backlog")):
        root = factory.mktemp(f"table-{state}") / "surface"
        shutil.copytree(made[source], root)
        with pytest.MonkeyPatch.context() as mp:
            _environment(mp, home)
            mp.chdir(root)
            mp.setattr("chantier.core.repo.PROJECT", None)
            live_writer(root.resolve() / ".git")
            _build(root, state)
        made[state] = root
    return made


def enter_state(source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Surface:
    """A copy of one state, the session running in it, its clone's git folder known."""
    root = tmp_path / "surface"
    shutil.copytree(source, root)
    monkeypatch.chdir(root)
    live_writer(root.resolve() / ".git")
    project = (root / "projects" / "demo").resolve()
    monkeypatch.setitem(SEEDED_COMMON_DIRS, _key(project / ".repo"), str(project / ".repo/.git"))
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")
    return Surface(root.resolve(), project, project / ".repo")
