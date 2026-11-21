"""The rig of the writer's tests: a real surface, a real bare origin, a cycle driven with no
sleep and no thread (`WriterLoop.poll(now)` takes the monotonic time)."""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from conftest import Surface, sh

from chantier.core.repo import Repo
from chantier.writer.loop import WriterLoop
from chantier.writer.record import read

QUIET = 31.0  # a cycle runs every 30 s: the quiet (10 s) has passed by the next one
EVERY = 31.0  # past the 30 s between two cycles
IDENT = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
}


class Rig:
    """A surface with an origin; the writer's loop, a second clone that plays another machine."""

    def __init__(self, surface: Surface, origin: Path, other: Path) -> None:
        self.surface, self.origin, self.other = surface, origin, other
        self.root = surface.root
        self.repo = Repo._external(self.root, str(surface.project))
        self.loop = WriterLoop(self.repo)
        self.clock = 0.0

    def git(self, *args: str, cwd: Path | None = None) -> str:
        return sh("git", *args, cwd=cwd or self.root)

    def write(self, rel: str, text: str = "x\n", where: Path | None = None) -> None:
        file = (where or self.root) / rel
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8")

    def tick(self, gap: float = EVERY) -> dict[str, Any]:
        """One poll `gap` seconds after the last; the entry as the cycle left it."""
        self.clock += gap
        self.loop.poll(self.clock)
        return read(self.repo.git_dir)

    def until(self, state: str, limit: int = 8) -> dict[str, Any]:
        """Poll (a cycle each) until the entry is in this state."""
        entry = self.tick()
        for _ in range(limit):
            if entry["state"] == state and not entry["pending"] and not entry["ahead"]:
                break
            entry = self.tick()
        return entry

    def repo_at(self, rel: str) -> None:
        """A git repository of its own (with a file) at this path of the surface."""
        sh("git", "init", "-q", str(self.root / rel))
        self.write(f"{rel}/f.txt")

    def settle(self) -> dict[str, Any]:
        """A change seen, quiet, committed and pushed: three polls."""
        self.tick()
        self.tick(QUIET)
        return self.tick(EVERY)

    def entry(self) -> dict[str, Any]:
        return read(self.repo.git_dir)

    def lines(self) -> list[dict[str, Any]]:
        file = self.surface.project / "changes" / "forge-journal.jsonl"
        if not file.is_file():
            return []
        return [json.loads(x) for x in file.read_text(encoding="utf-8").splitlines() if x]

    def types(self) -> list[str]:
        return [x["type"] for x in self.lines() if x.get("source") == "writer"]

    def seat(self) -> None:
        self.write("projects/demo/changes/seat.json", json.dumps({"session": "s1"}))

    def pushed(self) -> str:
        return self.git("rev-parse", "main", cwd=self.origin)

    def head(self) -> str:
        return self.git("rev-parse", "HEAD")


@pytest.fixture(scope="module")
def origin_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One bare origin per module, with the first commit of the surface template."""
    return tmp_path_factory.mktemp("writer-origin") / "origin.git"


def _main_sha(bare: Path) -> str:
    """The commit of `main` in a bare repository, read from its refs with no git process."""
    loose = bare / "refs" / "heads" / "main"
    if loose.is_file():
        return loose.read_text(encoding="ascii").strip()
    for line in (bare / "packed-refs").read_text(encoding="ascii").splitlines():
        if line.endswith(" refs/heads/main"):
            return line.split()[0]
    raise AssertionError(f"no main in {bare}")


def _set_url(config: Path, url: Path) -> None:
    text = config.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^(\s*url = ).*$", lambda m: m.group(1) + url.as_posix(), text)
    config.write_text(text, encoding="utf-8", newline="\n")


@pytest.fixture(scope="module")
def other_template(origin_template: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A clone of the module's origin, copied per test for the second machine."""
    return tmp_path_factory.mktemp("writer-other") / "other"


@pytest.fixture
def rig(
    surface: Surface,
    tmp_path: Path,
    origin_template: Path,
    other_template: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[], Rig]:
    for name, value in IDENT.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("LANG", "fr_FR.UTF-8")
    monkeypatch.setenv("LANGUAGE", "fr")
    monkeypatch.delenv("LC_ALL", raising=False)
    monkeypatch.setattr("chantier.hub.state.WAIT_S", 5.0, raising=False)

    def make() -> Rig:
        if not origin_template.exists():
            sh("git", "clone", "--bare", str(surface.root), str(origin_template))
            sh("git", "clone", "-q", str(origin_template), str(other_template))
        origin = tmp_path / "origin.git"
        shutil.copytree(origin_template, origin)
        # `remote add`, `fetch`, `branch -u`, `remote set-head`, written as git leaves them
        git_dir = surface.root / ".git"
        with (git_dir / "config").open("a", encoding="utf-8", newline="\n") as config:
            config.write(
                f'[remote "origin"]\n\turl = {origin.as_posix()}\n'
                "\tfetch = +refs/heads/*:refs/remotes/origin/*\n"
                '[branch "main"]\n\tremote = origin\n\tmerge = refs/heads/main\n'
            )
        remote_refs = git_dir / "refs" / "remotes" / "origin"
        remote_refs.mkdir(parents=True, exist_ok=True)
        (remote_refs / "main").write_text(_main_sha(origin) + "\n", encoding="ascii")
        (remote_refs / "HEAD").write_text("ref: refs/remotes/origin/main\n", encoding="ascii")
        other = tmp_path / "other"
        shutil.copytree(other_template, other)
        _set_url(other / ".git" / "config", origin)
        found = Rig(surface, origin, other)
        found.loop.lock.release()  # the fixture's own process holds nothing: start fresh
        return found

    return make
