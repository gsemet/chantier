"""CR folders, project-specific lifecycle paths, and safe stage transitions."""
from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass
from pathlib import Path

from .state import (EXIT_CONFLICT, EXIT_PRECONDITION, EXIT_USAGE, Batch, ChantierError, Repo,
                    _read_json, _try_lock, _unlock, move_directory, project_path, stamp)
PRIORITIES = ("P1", "P2", "P3", "P4")
STAGES = ("inbox", "backlog", "requests", "archives", "trash")


def stage_layout(repo: Repo) -> dict[str, Path]:
    """The five stage folders, always the same: `.agents/changes/1-inbox` and so on."""
    base = repo.changes.resolve()
    return {"inbox": base / "1-inbox", "backlog": base / "2-backlog",
            "requests": base / "3-requests", "archives": base / "4-archives",
            "trash": base / "5-trash"}


@contextlib.contextmanager
def changes_lock(repo: Repo):
    repo.changes.mkdir(parents=True, exist_ok=True)
    with open(repo.changes / ".lifecycle.lock", "a+") as lock:
        deadline = time.monotonic() + 30
        while not _try_lock(lock):
            if time.monotonic() > deadline:
                raise ChantierError("CR lifecycle is locked for over 30 s")
            time.sleep(0.05)
        try:
            yield
        finally:
            _unlock(lock)


@dataclass(frozen=True)
class PreparedCR:
    directory: Path
    specification: Path
    title: str
    priority: str | None


def prepared_cr(repo: Repo, item: str, paths: dict[str, Path]) -> PreparedCR:
    if not item.startswith("@") or len(item) == 1:
        raise ChantierError("open requires @<prepared-CR-folder> or @<specification-file>; "
                            "file and grill the CR first", EXIT_USAGE)
    supplied = project_path(repo.root, item[1:], "CR item")
    if supplied.is_file():
        directory, specification = supplied.parent, supplied
    elif supplied.is_dir():
        directory, specification = supplied, supplied / "03-change-spec.md"
    else:
        raise ChantierError(f"prepared CR not found: {supplied}", EXIT_USAGE)
    priority = None
    if directory.parent == paths["inbox"]:
        pass
    elif paths["requests"] in directory.parents:
        raise ChantierError(f"{directory} is already active; resume its existing batch instead",
                            EXIT_PRECONDITION)
    elif directory.parent.parent == paths["backlog"] and directory.parent.name in PRIORITIES:
        priority = directory.parent.name
    else:
        raise ChantierError(f"{directory} is not a CR in the configured inbox or priority backlog",
                            EXIT_USAGE)
    if not specification.is_file():
        raise ChantierError(f"missing Change Specification: {specification}; grill the CR first",
                            EXIT_PRECONDITION)
    try:
        text = specification.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise ChantierError(f"{specification} is not UTF-8: save it as UTF-8 ({e})",
                            EXIT_PRECONDITION) from e
    if not text.strip():
        raise ChantierError(f"empty Change Specification: {specification}", EXIT_PRECONDITION)
    title = next((line.lstrip("# ").strip() for line in text.splitlines() if line.strip()),
                 directory.name)
    return PreparedCR(directory, specification, title, priority)


def ensure_unclaimed(repo: Repo, directory: Path) -> None:
    for batch_dir in repo.batch_folders():
        batch = _read_json(batch_dir / "batch.json")
        if batch.get("status") == "landed":
            continue
        for cr in batch.get("crs", []):
            if cr.get("status") in {"cancelled", "merged", "landed"} or not cr.get("path"):
                continue
            claimed = project_path(repo.root, cr["path"], "recorded CR path")
            if claimed == directory:
                raise ChantierError(f"{directory} is already in batch {batch_dir.name}",
                                    EXIT_CONFLICT)


def cr_directory(repo: Repo, cr: dict) -> Path:
    if not cr.get("path"):
        raise ChantierError(f"{cr['id']} has no recorded CR folder", EXIT_PRECONDITION)
    return project_path(repo.root, cr["path"], "recorded CR path")


def _retire(batch: Batch, cr: dict, stage: str) -> None:
    """A CR leaves its batch for good: the folder's name starts with the date, its order."""
    if not cr.get("path"):
        return
    source = cr_directory(batch.repo, cr)
    if source.resolve().parent != batch.dir.resolve():  # it has already left
        return
    target = stage_layout(batch.repo)[stage] / f"{stamp()}-{source.name}"
    batch.move(source, target)
    cr["path"] = target.relative_to(batch.repo.root).as_posix()


def archive_cr(batch: Batch, cr: dict) -> None:
    _retire(batch, cr, "archives")


def trash_cr(batch: Batch, cr: dict) -> None:
    _retire(batch, cr, "trash")


def move_backlog_item(repo: Repo, item: str, priority: str, paths: dict[str, Path]) -> Path:
    if priority not in PRIORITIES:
        raise ChantierError(f"priority must be one of {', '.join(PRIORITIES)}", EXIT_USAGE)
    source = project_path(repo.root, item, "inbox CR")
    if source.parent != paths["inbox"]:
        raise ChantierError(f"{source} is not directly inside {paths['inbox']}", EXIT_USAGE)
    target = paths["backlog"] / priority / source.name
    move_directory(source, target)
    return target
