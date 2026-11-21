"""A surface of four projects with a fake forge, for the tests of the forge hub and of the surface
server (`world` is the fixture, in `conftest.py`)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from chantier import connectors
from chantier.commands.forge_stack_gh import pr_parts
from chantier.core.repo import Repo
from chantier.hub import journal
from chantier.hub.cycle import Hub

if TYPE_CHECKING:
    from conftest import Surface

LINK = "https://github.com/acme/{}/pull/{}"
OPEN: dict[str, Any] = {
    "state": "open",
    "conflicting": False,
    "checking": False,
    "checks": "green",
    "base": "main",
    "head": "a" * 40,
    "merged_at": None,
    "closed_at": None,
}
T1, T2 = "2026-11-18T10:00:00Z", "2026-11-18T10:00:05Z"
MAIN, B1 = "main", "chantier/b/cr-1"
FIRST_PR = {"alpha": 10, "beta": 20, "gamma": 30, "delta": 40}
CYCLE, QUIET = 20.0, 20.0
EXIT_USAGE, EXIT_PRECONDITION = 1, 2
BOARD_LINE = {"type": "board@1", "action": "move", "items": ["x"], "text": "x", "wakes": True}
NEW_VERSION = "9.9.9"
CALLS = 2  # alpha and beta: one call each


def crs_of(name: str, state: str = "ready", count: int = 2) -> list[dict[str, Any]]:
    return [
        {
            "id": f"CR-{i + 1}",
            "status": state,
            "order": i,
            "pr": LINK.format(name, FIRST_PR[name] + i),
            "pr_draft": False,
            "pr_base": "main",
            "branch": f"chantier/b/cr-{i + 1}",
        }
        for i in range(count)
    ]


def write_batch(project: Path, status: str, crs: list[dict[str, Any]]) -> None:
    folder = project / "changes" / "4-batch"
    folder.mkdir(parents=True, exist_ok=True)
    data = {"id": "batch-01", "status": status, "settings": {"default_branch": "main"}, "crs": crs}
    (folder / "batch.json").write_text(json.dumps(data), encoding="utf-8")


class World:
    """A surface of four projects: alpha and beta run a batch of two ready CRs, gamma's is paused,
    delta's CRs are merged. The forge answers `forge` (a PR number to the fields that differ
    from `OPEN`); every call of the seam is kept in `calls`."""

    def __init__(self, surface: Surface, monkeypatch: pytest.MonkeyPatch) -> None:
        self.root = surface.root
        write_batch(self.project("alpha"), "running", crs_of("alpha"))
        write_batch(self.project("beta"), "running", crs_of("beta"))
        write_batch(self.project("gamma"), "paused", crs_of("gamma"))
        write_batch(self.project("delta"), "running", crs_of("delta", "merged"))
        self.forge: dict[int, dict[str, Any]] = {}
        self.calls: list[list[str]] = []
        self.asked: list[frozenset[str]] = []  # the optional facts of each call
        self.failure: Exception | None = None
        monkeypatch.setattr(connectors, "read", self.read)
        self.hub = Hub(self.repo("alpha"), NEW_VERSION)

    def project(self, name: str) -> Path:
        folder = self.root / "projects" / name
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def repo(self, name: str) -> Repo:
        return Repo.find(self.root, str(self.project(name)))

    def read(
        self, links: list[str], facts: frozenset[str] = frozenset()
    ) -> dict[int, dict[str, Any]]:
        self.calls.append(links)
        self.asked.append(facts)
        if self.failure:
            raise self.failure
        return {n: {**OPEN, **self.forge.get(n, {})} for n in (int(pr_parts(x)[3]) for x in links)}

    def journal(self, name: str) -> list[dict[str, Any]]:
        return journal.read(self.repo(name).store, self.repo(name).changes)[0]


def merged(base: str, at: str) -> dict[str, Any]:
    return {"state": "merged", "base": base, "merged_at": at}


def shape(entries: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    """(seq, source, type, cr, landed_with or head) of each line."""
    return [
        (e["seq"], e["source"], e["type"], e["cr"], e.get("landed_with") or e.get("head"))
        for e in entries
    ]
