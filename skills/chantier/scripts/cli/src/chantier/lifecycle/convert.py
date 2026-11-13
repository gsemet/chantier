"""The conversion of a planning tree of the old layout, once."""

from __future__ import annotations

import contextlib
import shutil
import sys
import time
from pathlib import Path
from typing import IO

from chantier.core.errors import EXIT_EXTERNAL, EXIT_PRECONDITION, ChantierError
from chantier.core.files import LOCK_TIMEOUT_S, retry, try_lock, unlock, write_file
from chantier.core.records import read_batch_json
from chantier.core.repo import Repo
from chantier.lifecycle.backfill import backfill_history
from chantier.lifecycle.session import RenderedBatch
from chantier.lifecycle.stages import STATE_FOLDERS, changes_lock, stage_layout
from chantier.status.write import write_dashboard


def _has_files(path: Path) -> bool:
    return any(not p.is_dir() or p.is_symlink() for p in path.rglob("*"))


def old_tree(repo: Repo) -> bool:
    """Does `.agents/changes/` hold the older layout? `3-requests/` alone is no sign: a working
    CR keeps its folder there until its next move. The signs are `4-archives/`, `5-trash/`, a
    batch folder with its `batch.json`, and the old index."""
    base = repo.changes
    if (base / "4-archives").is_dir() or (base / "5-trash").is_dir():
        return True
    old = base / "3-requests"
    if not old.is_dir():
        return False
    return any((old / n).exists() for n in ("STATUS.md", "STATUS.json")) or any(
        (d / "batch.json").is_file() for d in old.iterdir() if d.is_dir()
    )


def convert_old_tree(repo: Repo) -> None:
    """Convert the older tree to the current one, once, before any other work: `5-trash/` to
    `6-trash/`, `4-archives/` to `5-archives/`, the batch folder `3-requests/batch-<n>/` to
    `4-batch/` (its own files there, its queued CR in `1-pending`, its ready and blocked CRs in
    `2-actives`; a working CR stays at its old path, as its Driver holds it, and moves at its
    merge or its drop), and every recorded path rewritten. Renames only, rolled back on a
    failure; a new name that is not empty, or more than one batch, exits 2 with nothing moved."""
    if not old_tree(repo):
        return
    with changes_lock(repo):  # the lifecycle lock first, then the batch's, as every command does
        if not old_tree(repo):  # another command converted it while this one waited
            return
        parts = _convert(repo)
    print(
        "converted .agents/changes to the new tree" + (": " + ", ".join(parts) if parts else ""),
        file=sys.stderr,
    )


def _free_target(old: Path, new: Path) -> bool:
    """Is `new` to be written? An existing one that holds no file (empty folders from an `init`)
    gives way; one that holds files is refused, naming both."""
    if not new.exists() and not new.is_symlink():
        return False
    if new.is_dir() and not _has_files(new):
        return True
    raise ChantierError(
        f"cannot convert the tree: both {old} and {new} exist; merge or remove "
        "one of them. Nothing was moved.",
        EXIT_PRECONDITION,
    )


def _rename(renames: list[tuple[Path, Path]], src: Path, dst: Path) -> None:
    """Move `src` to `dst` and remember it, so that a failure puts everything back."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        retry(src.rename, dst)
    except OSError as e:
        raise ChantierError(
            f"cannot convert the tree: {src} is in use ({e}); close what "
            "holds it and run any command again. Nothing was changed.",
            EXIT_EXTERNAL,
        ) from e
    renames.append((src, dst))


def _lock_batch(batch: Path) -> tuple[IO[str], bytes]:
    """Hold the batch's own lock while its files move; its record as it was."""
    lock = open(batch / ".lock", "a+")  # noqa: SIM115  held while the files move
    deadline = time.monotonic() + LOCK_TIMEOUT_S
    while not try_lock(lock):
        if time.monotonic() > deadline:
            lock.close()
            raise ChantierError(f"batch {batch.name} is locked for over {LOCK_TIMEOUT_S} s")
        time.sleep(0.05)
    return lock, (batch / "batch.json").read_bytes()


NEW_STATE = {"queued": "1-pending", "ready": "2-actives", "blocked": "2-actives"}


def _where(repo: Repo, batch: Path, data: dict, target: Path) -> dict[Path, Path]:
    """A CR folder of the batch -> the state folder its status gives."""
    where: dict[Path, Path] = {}
    for cr in data["crs"]:
        if not cr.get("path"):
            continue
        folder = repo.planning_path(cr["path"], "recorded CR path")
        state = NEW_STATE.get(cr["status"])
        if state and folder.parent == batch.resolve() and folder.is_dir():
            where[folder] = target / state / folder.name
    return where


def _move_files(
    repo: Repo,
    batch: Path,
    target: Path,
    where: dict[Path, Path],
    renames: list[tuple[Path, Path]],
) -> list[list[str]]:
    """The batch's own files and its Demo folder move; its CRs go by status, and any other
    folder stays where it is, never taken for the batch's."""
    moves: list[list[str]] = []
    for item in sorted(batch.iterdir()):
        if item.name != ".lock" and (item.is_file() or item.name == "demo"):
            _rename(renames, item, target / item.name)
            moves.append([repo.rel(item), repo.rel(target / item.name)])
    for folder, dest in where.items():
        _rename(renames, folder, dest)
        moves.append([repo.rel(folder), repo.rel(dest)])
    return moves


def _new_path(repo: Repo, cr: dict, where: dict[Path, Path]) -> str:
    """A CR's recorded path after the move: its new folder, or the renamed archive stage."""
    path = cr["path"]
    moved = where.get(repo.planning_path(path, "recorded CR path"))
    if moved is None:
        return path.replace(".agents/changes/4-archives/", ".agents/changes/5-archives/").replace(
            ".agents/changes/5-trash/", ".agents/changes/6-trash/"
        )
    if not moved.is_dir():
        raise ChantierError(f"{cr['id']}: {repo.rel(moved)} does not exist")
    return repo.rel(moved)


def _move_batch(
    repo: Repo,
    batch: Path,
    target: Path,
    plain: list[tuple[Path, Path]],
    renames: list[tuple[Path, Path]],
) -> None:
    """The batch folder becomes `4-batch`: its files, its CRs by status, its record repointed."""
    data = read_batch_json(batch / "batch.json")
    where = _where(repo, batch, data, target)
    moves = _move_files(repo, batch, target, where, renames)
    for state in STATE_FOLDERS:
        (target / state).mkdir(parents=True, exist_ok=True)
    with RenderedBatch(repo, data["id"], actor="cli") as b:
        for cr in b.data["crs"]:
            if cr.get("path"):
                cr["path"] = _new_path(repo, cr, where)
        b.log(
            "tree",
            None,
            moves=moves
            + [[f".agents/changes/{a.name}", f".agents/changes/{z.name}"] for a, z in plain],
        )


def _clean_old(old: Path, batch: Path | None) -> None:
    """The older index and the batch's old folder, once nothing of the batch is left in them."""
    for name in ("STATUS.md", "STATUS.json"):
        with contextlib.suppress(OSError):
            (old / name).unlink()
    if batch:
        with contextlib.suppress(OSError):
            (batch / ".lock").unlink()
        with contextlib.suppress(OSError):
            batch.rmdir()
    with contextlib.suppress(OSError):
        old.rmdir()


def _old_batch(old: Path) -> Path | None:
    """The one batch folder of the older tree, if any."""
    batches = (
        sorted(d for d in old.iterdir() if d.is_dir() and (d / "batch.json").is_file())
        if old.is_dir()
        else []
    )
    if len(batches) > 1:
        raise ChantierError(
            "cannot convert the tree: more than one batch folder in "
            f"{old} ({', '.join(d.name for d in batches)}); one batch at a time. "
            "Nothing was moved.",
            EXIT_PRECONDITION,
        )
    return batches[0] if batches else None


def _convert(repo: Repo) -> list[str]:
    base, old = repo.changes, repo.changes / "3-requests"
    batch = _old_batch(old)
    plain = [("4-archives", "5-archives"), ("5-trash", "6-trash")]
    plain = [(base / a, base / b) for a, b in plain if (base / a).is_dir()]
    clear = [_free_target(a, b) for a, b in plain]
    target = base / "4-batch"
    clear_batch = _free_target(batch, target) if batch else False
    renames: list[tuple[Path, Path]] = []
    parts: list[str] = []
    lock = original = None
    try:
        if batch:
            lock, original = _lock_batch(batch)
        for (a, b), empty in zip(plain, clear, strict=False):
            if empty:
                shutil.rmtree(b)
            _rename(renames, a, b)
            parts.append(f"{a.name} -> {b.name}")
        if batch:
            if clear_batch:
                shutil.rmtree(target)
            _move_batch(repo, batch, target, plain, renames)
            parts.insert(0, "3-requests -> 4-batch")
    except BaseException as e:
        _undo(renames, batch, original, lock)
        if isinstance(e, OSError):
            raise ChantierError(
                f"cannot convert the tree: {e}. Nothing was changed.", EXIT_EXTERNAL
            ) from e
        raise
    if lock:
        with contextlib.suppress(Exception):
            unlock(lock)
        lock.close()
    _clean_old(old, batch)
    if not batch:  # a batch writes the index through `Batch`
        write_dashboard_after_rename(repo)
    return parts


def _rel(repo: Repo, path: Path) -> str:
    return repo.rel(path)


def _undo(
    renames: list[tuple[Path, Path]], batch: Path | None, original: bytes | None, lock
) -> None:
    """Put every rename back, last first, and the batch's record as it was."""
    stuck = []
    for src, dst in reversed(renames):
        try:
            retry(dst.rename, src)
        except OSError:
            stuck.append(f"{dst} -> {src}")
    if (
        batch is not None
        and original is not None
        and (batch / "batch.json").is_file()
        and not stuck
    ):
        write_file(batch / "batch.json", original.decode("utf-8-sig"))
    if lock is not None:
        with contextlib.suppress(Exception):
            unlock(lock)
        lock.close()
    if stuck:
        raise ChantierError(
            "cannot roll back the conversion of the tree; preserve both paths and "
            "resolve manually: " + "; ".join(stuck),
            EXIT_EXTERNAL,
        )


def write_dashboard_after_rename(repo: Repo) -> None:
    """Archives and trash moved without a batch: the index at the root is written anew."""
    with contextlib.suppress(OSError):  # a file that cannot be written; any other error shows
        write_dashboard(repo, stage_layout(repo))


def open_repo(cwd: Path | None = None, project: str | None = None) -> Repo:
    """The repository, with the tree of the old layout converted once, before anything else.

    The first command run after an update converts it; `init` finds the repository with
    `Repo.find` and converts after its own checks."""
    repo = Repo.find(cwd, project=project)
    convert_old_tree(repo)
    backfill_history(repo)
    return repo
