"""`open` in a planning surface whose project has no clone: one refusal, no traceback, nothing
written; the same line as preflight's P8."""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path

import pytest
from batch_helpers import FROM_AGENTS_MD, host
from conftest import Chantier, Surface

from chantier.core.errors import EXIT_PRECONDITION

NO_CLONE = "no clone of the project at "


def remove(folder: Path) -> None:
    """`rmtree` that also deletes git's read-only objects on Windows."""

    def writable(func: object, path: str, _err: object) -> None:
        os.chmod(path, stat.S_IWRITE)
        func(path)  # type: ignore[operator]

    shutil.rmtree(folder, onerror=writable)


@pytest.mark.parametrize(
    ("args", "configured"),
    [((), False), (("--factory",), False), (("--factory",), True)],
    ids=["no-cr", "factory", "factory-configured-cell"],
)
def test_open_refuses_a_project_with_no_clone(
    surface: Surface,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    args: tuple[str, ...],
    configured: bool,
) -> None:
    host(monkeypatch)
    expected = surface.clone
    if configured:
        expected = surface.project / "gone"
        (surface.project / "checkout.yml").write_text("repo: gone\nworktrees: ../../../wt\n")
    remove(surface.clone)
    changes = surface.project / "changes"
    before = sorted(p.relative_to(changes).as_posix() for p in changes.rglob("*"))
    code, _, err = chantier("--project", "demo", "open", *FROM_AGENTS_MD, *args)
    assert code == EXIT_PRECONDITION
    assert NO_CLONE + expected.as_posix() in err and "Traceback" not in err
    assert not (changes / "4-batch" / "batch.json").exists()
    after = sorted(p.relative_to(changes).as_posix() for p in changes.rglob("*"))
    assert after == before


def test_preflight_names_the_missing_clone(surface: Surface, chantier: Chantier) -> None:
    remove(surface.clone)
    code, out, _ = chantier("--project", "demo", "preflight")
    assert code == EXIT_PRECONDITION
    assert any(NO_CLONE + surface.clone.as_posix() in line for line in out)
