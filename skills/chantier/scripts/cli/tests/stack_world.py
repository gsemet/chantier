"""A stack batch (CRs taken, each in its worktree) built once per run and copied per test.

The record, the STATUS files and git's worktree links hold the absolute path of the folder the state
was built in: a copy rewrites it, so no test depends on the template's folder."""

from __future__ import annotations

import json
import os
import shutil
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import host, open_batch, record
from conftest import Chantier, sh, shared_state

FACTORY: list[pytest.TempPathFactory] = []  # the run's, for the helpers that no fixture reaches
TAKEN: list[list[str]] = []  # the first output line of each `take` of the last `stack_of`


@pytest.fixture(autouse=True)
def _remember_factory(tmp_path_factory: pytest.TempPathFactory) -> None:
    FACTORY[:] = [tmp_path_factory]


def _overwrite(src: str, dst: str) -> str:
    """`copy2` over a file git made read-only (a loose object the copied repository already has)."""
    if os.path.exists(dst):
        os.chmod(dst, stat.S_IWRITE)
        os.unlink(dst)
    return shutil.copy2(src, dst)


def rewrite_paths(files: list[Path], old: str, new: str) -> None:
    pairs = [
        (old, new),
        (old.replace("\\", "/"), new.replace("\\", "/")),
        (json.dumps(old)[1:-1], json.dumps(new)[1:-1]),
    ]
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        fixed = text
        for a, b in pairs:
            fixed = fixed.replace(a, b)
        if fixed != text:
            path.unlink()  # a worktree's `.git` is hidden on Windows: it cannot be opened to write
            path.write_bytes(fixed.encode("utf-8"))


def _links(work: Path) -> list[Path]:
    """The files that name an absolute path: the planning folder's and git's worktree links."""
    found = [p for p in (work / ".agents").rglob("*") if p.is_file()]
    found += [p for p in (work / ".git" / "worktrees").rglob("gitdir") if p.is_file()]
    wts = work.parent / f"{work.name}.worktrees"
    found += [p / ".git" for p in wts.iterdir()] if wts.exists() else []
    return found


@dataclass(frozen=True)
class Batch:
    """A batch to prepare: its `name` tells the variants apart; the first `took` CRs (all by
    default) are taken and each has a git worktree unless `worktrees` is off; `after` runs last."""

    name: str
    titles: tuple[str, ...]
    args: tuple[object, ...] = ("--mode", "stack")
    took: int | None = None
    worktrees: bool = True
    after: Callable[[Path], None] = lambda repo: None


def stack_of(
    batch: Batch, repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> list[dict[str, Any]]:
    """The CRs of the batch, in `repo` (the test's copy of the prepared repository). The first
    test to ask builds it; the others copy the first one's, with its paths rewritten."""
    built_here: list[bool] = []
    taken: list[str] = []
    wts = f"{repo.name}.worktrees"

    def build(folder: Path) -> None:
        built_here.append(True)
        ids = open_batch(repo, chantier, monkeypatch, *batch.titles, args=batch.args)
        for cr in ids[: batch.took]:
            code, out, err = chantier("take", cr, "--epoch", 1)
            assert code == 0, err
            taken.append(out[0])
        for cr in record(repo)["crs"][: batch.took if batch.worktrees else 0]:
            sh("git", "worktree", "add", "-q", "-b", cr["branch"], cr["worktree"], "HEAD", cwd=repo)
        batch.after(repo)
        shutil.copytree(repo, folder / "proj")
        if (repo.parent / wts).exists():
            shutil.copytree(repo.parent / wts, folder / "worktrees")
        kept = {"base": str(repo.parent), "leases": chantier.leases, "taken": taken}  # type: ignore[attr-defined]
        (folder / "base.json").write_text(json.dumps(kept), encoding="utf-8")

    folder = shared_state(FACTORY[0], batch.name, build)
    if not built_here:
        kept = json.loads((folder / "base.json").read_text(encoding="utf-8"))
        shutil.copytree(folder / "proj", repo, dirs_exist_ok=True, copy_function=_overwrite)
        if (folder / "worktrees").exists():
            shutil.copytree(folder / "worktrees", repo.parent / wts)
        rewrite_paths(_links(repo), kept["base"], str(repo.parent))
        host(monkeypatch)
        chantier.leases.update(kept["leases"])  # type: ignore[attr-defined]
        taken = kept["taken"]
        monkeypatch.setenv("CHANTIER_BATCH", record(repo)["id"])
    TAKEN[:] = [taken]
    return list(record(repo)["crs"])
