"""CR folders, project-specific lifecycle paths, and safe stage transitions."""
from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass
from pathlib import Path

from .state import (EXIT_CONFLICT, EXIT_PRECONDITION, EXIT_USAGE, Batch, ChantierError, Repo,
                    _read_json, _try_lock, _unlock, move_directory, now, project_path)

PRIORITIES = ("P1", "P2", "P3", "P4")
STAGES = ("inbox", "backlog", "requests", "archives", "trash")


def stage_layout(repo: Repo, overrides: dict | None = None) -> dict[str, Path]:
    base = repo.changes / "backlog"
    defaults = {"inbox": base / "1-inbox", "backlog": base / "2-backlog",
                "requests": base / "3-requests", "archives": base / "4-archives",
                "trash": base / "5-trash"}
    values = repo.config.get("layout", {}) if overrides is None else overrides
    if not isinstance(values, dict) or set(values) - set(STAGES):
        raise ChantierError("invalid CR lifecycle paths in batch settings", EXIT_PRECONDITION)
    paths = {stage: project_path(repo.root, values.get(stage) or default, f"{stage} directory")
             for stage, default in defaults.items()}
    for stage, path in paths.items():
        for other, other_path in paths.items():
            if stage != other and (path == other_path or path in other_path.parents):
                raise ChantierError(f"CR lifecycle directories overlap: {stage} and {other}",
                                    EXIT_USAGE)
    return paths


def stored_layout(repo: Repo, paths: dict[str, Path]) -> dict[str, str]:
    return {stage: path.relative_to(repo.root).as_posix() for stage, path in paths.items()}


@contextlib.contextmanager
def changes_lock(repo: Repo):
    repo.changes.mkdir(parents=True, exist_ok=True)
    with open(repo.changes / ".chantier-lifecycle.lock", "a+") as lock:
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
    elif directory.parent == paths["requests"]:
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
    text = specification.read_text(encoding="utf-8")
    if not text.strip():
        raise ChantierError(f"empty Change Specification: {specification}", EXIT_PRECONDITION)
    title = next((line.lstrip("# ").strip() for line in text.splitlines() if line.strip()),
                 directory.name)
    return PreparedCR(directory, specification, title, priority)


def ensure_unclaimed(repo: Repo, directory: Path) -> None:
    if not repo.batches.exists():
        return
    for batch_dir in repo.batches.iterdir():
        state = batch_dir / "batch.json"
        if not state.is_file():
            continue
        batch = _read_json(state)
        if batch.get("status") == "landed":
            continue
        for cr in batch.get("crs", []):
            if cr.get("status") in {"cancelled", "merged", "landed"} or not cr.get("path"):
                continue
            claimed = project_path(repo.root, cr["path"], "recorded CR path")
            if claimed == directory:
                raise ChantierError(f"{directory} is already in batch {batch_dir.name}",
                                    EXIT_CONFLICT)


def cr_directory(repo: Repo, batch_id: str, cr: dict) -> Path:
    if cr.get("path"):
        return project_path(repo.root, cr["path"], "recorded CR path")
    return repo.batch_dir(batch_id) / "crs" / cr["id"]


def archive_cr(batch: Batch, cr: dict) -> None:
    if not cr.get("path"):
        return
    source = cr_directory(batch.repo, batch.id, cr)
    target = stage_layout(batch.repo)["archives"] / source.name
    batch.move(source, target)
    cr["path"] = target.relative_to(batch.repo.root).as_posix()
    report = target / "report.md"
    if not report.exists():
        with report.open("x", encoding="utf-8") as f:
            f.write(f"# {cr['id']}: {cr['title']}\n\n- Merged: {now()}\n"
                    f"- PR: {cr.get('pr') or 'not recorded'}\n- Rounds: {cr.get('round', 0)}\n")


def return_cr(batch: Batch, cr: dict) -> None:
    if not cr.get("path") or not cr.get("origin"):
        return
    source = cr_directory(batch.repo, batch.id, cr)
    target = project_path(batch.repo.root, cr["origin"], "original CR path")
    if source != target:
        batch.move(source, target)
        cr["path"] = target.relative_to(batch.repo.root).as_posix()


def move_backlog_item(repo: Repo, item: str, priority: str, paths: dict[str, Path]) -> Path:
    if priority not in PRIORITIES:
        raise ChantierError(f"priority must be one of {', '.join(PRIORITIES)}", EXIT_USAGE)
    source = project_path(repo.root, item, "inbox CR")
    if source.parent != paths["inbox"]:
        raise ChantierError(f"{source} is not directly inside {paths['inbox']}", EXIT_USAGE)
    target = paths["backlog"] / priority / source.name
    move_directory(source, target)
    return target
