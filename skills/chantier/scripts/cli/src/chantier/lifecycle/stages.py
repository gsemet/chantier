"""The stage folders of a CR and the moves between them."""

from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from chantier.core.batch import Batch, move_directory
from chantier.core.clock import now, stamp
from chantier.core.errors import EXIT_CONFLICT, EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.files import read_text, try_lock, unlock, write_file
from chantier.core.records import read_batch_json
from chantier.core.repo import Repo

PRIORITIES = ("P1", "P2", "P3", "P4")


STATE_FOLDERS = ("1-pending", "2-actives", "3-done")  # the batch's, in `4-batch/`


def stage_layout(repo: Repo) -> dict[str, Path]:
    """The stage folders, always the same: `.agents/changes/1-inbox` and so on. `batches` is the
    parent of `pending`, `actives` and `done`, the states of the CRs inside the batch."""
    base = repo.changes.resolve()
    batches = base / "4-batch"
    return {
        "inbox": base / "1-inbox",
        "backlog": base / "2-backlog",
        "ready": base / "3-ready",
        "batches": batches,
        "pending": batches / "1-pending",
        "actives": batches / "2-actives",
        "done": batches / "3-done",
        "archives": base / "5-archives",
        "trash": base / "6-trash",
    }


@contextlib.contextmanager
def changes_lock(repo: Repo):
    repo.changes.mkdir(parents=True, exist_ok=True)
    repo.ensure_gitignore()
    with open(repo.changes / ".lifecycle.lock", "a+") as lock:
        deadline = time.monotonic() + 30
        while not try_lock(lock):
            if time.monotonic() > deadline:
                raise ChantierError("CR lifecycle is locked for over 30 s")
            time.sleep(0.05)
        try:
            yield
        finally:
            unlock(lock)


@dataclass(frozen=True)
class PreparedCR:
    directory: Path
    specification: Path
    title: str


def prepared_cr(repo: Repo, item: str, paths: dict[str, Path]) -> PreparedCR:
    """A CR folder in the inbox, the priority backlog or `3-ready`, with a specification. A CR in
    `3-ready` may have none (automatable): its request, as received, is then its specification."""
    if not item.strip():
        raise ChantierError(
            "open requires <prepared-CR-folder> or <specification-file>; "
            "file and grill the CR first",
            EXIT_USAGE,
        )
    supplied = repo.planning_path(item, "CR item")
    if supplied.is_file():
        directory, specification = supplied.parent, supplied
    elif supplied.is_dir():
        directory, specification = supplied, supplied / "03-change-spec.md"
    else:
        raise ChantierError(f"prepared CR not found: {supplied}", EXIT_USAGE)
    in_ready = _check_place(directory, paths)
    specification = _specification(specification, directory, supplied, in_ready)
    text = _spec_text(specification)
    title = next(
        (line.lstrip("# ").strip() for line in text.splitlines() if line.strip()), directory.name
    )
    return PreparedCR(directory, specification, title)


def _check_place(directory: Path, paths: dict[str, Path]) -> bool:
    """Refuse a folder that is not in the inbox, the priority backlog or `3-ready`; say if it is
    in `3-ready`."""
    in_backlog = directory.parent.parent == paths["backlog"] and directory.parent.name in PRIORITIES
    in_ready = directory.parent == paths["ready"]
    if paths["batches"] in directory.parents:
        raise ChantierError(
            f"{directory} is already active; resume its existing batch instead", EXIT_PRECONDITION
        )
    if directory.parent != paths["inbox"] and not in_backlog and not in_ready:
        raise ChantierError(
            f"{directory} is not a CR in the configured inbox, priority backlog or 3-ready",
            EXIT_USAGE,
        )
    return in_ready


def _specification(specification: Path, directory: Path, supplied: Path, in_ready: bool) -> Path:
    if not specification.is_file() and directory.name.startswith("qa-"):
        raise ChantierError(
            f"{directory} is a QA report: an item to triage and split into CRs, not to open",
            EXIT_PRECONDITION,
        )
    if (
        not specification.is_file()
        and in_ready
        and supplied.is_dir()
        and (directory / "intake" / "request.md").is_file()
    ):
        specification = directory / "intake" / "request.md"  # automatable: the request as received
    if not specification.is_file():
        raise ChantierError(
            f"missing Change Specification: {specification}; grill the CR first", EXIT_PRECONDITION
        )
    return specification


def _spec_text(specification: Path) -> str:
    try:
        text = read_text(specification)
    except UnicodeDecodeError as e:
        raise ChantierError(
            f"{specification} is not UTF-8: save it as UTF-8 ({e})", EXIT_PRECONDITION
        ) from e
    if not text.strip():
        raise ChantierError(f"empty Change Specification: {specification}", EXIT_PRECONDITION)
    return text


def ensure_unclaimed(repo: Repo, directory: Path) -> None:
    for batch_dir in repo.batch_folders():
        batch = read_batch_json(batch_dir / "batch.json")
        for cr in batch.get("crs", []):
            if cr.get("status") in {"cancelled", "merged"} or not cr.get("path"):
                continue
            claimed = repo.planning_path(cr["path"], "recorded CR path")
            if claimed == directory:
                raise ChantierError(f"{directory} is already in batch {batch['id']}", EXIT_CONFLICT)


def cr_directory(repo: Repo, cr: dict[str, Any]) -> Path:
    if not cr.get("path"):
        raise ChantierError(f"{cr['id']} has no recorded CR folder", EXIT_PRECONDITION)
    return repo.planning_path(cr["path"], "recorded CR path")


def _relocate(batch: Batch, cr: dict[str, Any], target: Path) -> None:
    source = cr_directory(batch.repo, cr)
    batch.move(source, target)
    cr["path"] = batch.repo.rel(target)
    old = batch.repo.changes / "3-requests"  # a working CR of a converted tree was its last tenant
    for folder in (source.parent, source.parent.parent):
        if old in (folder, *folder.parents) and folder.is_dir() and not any(folder.iterdir()):
            with contextlib.suppress(OSError):
                folder.rmdir()


def start_cr(batch: Batch, cr: dict[str, Any]) -> None:
    """`take`: the CR's folder goes from `1-pending` to `2-actives`, before its Driver gets the
    facts. A CR already elsewhere (taken before, or still at the path of an older tree) stays."""
    if not cr.get("path"):
        return
    paths = stage_layout(batch.repo)
    source = cr_directory(batch.repo, cr)
    if source.parent == paths["pending"]:
        _relocate(batch, cr, paths["actives"] / source.name)


def done_cr(batch: Batch, cr: dict[str, Any]) -> None:
    """The CR is merged (a release CR: released): its folder goes to `3-done` and stays until
    `close`, with the merge time, which names its archive. A folder that already left stays."""
    if not cr.get("path"):
        return
    paths = stage_layout(batch.repo)
    source = cr_directory(batch.repo, cr)
    if source.parent not in (paths["done"], paths["archives"], paths["trash"]):
        _relocate(batch, cr, paths["done"] / source.name)
    cr["merged_at"] = cr.get("merged_at") or now()
    if batch.repo.external and cr_directory(batch.repo, cr).is_dir():
        _delivery(batch.repo, cr, cr_directory(batch.repo, cr))


def _delivery(repo: Repo, cr: dict[str, Any], folder: Path) -> None:
    """`delivery.md`, written in the surface when the merge is recorded: it travels into the
    archive and says where the CR was delivered."""
    if not repo.archive_in_pr:
        mine = "no (project setting)"
    elif cr.get("archive_seen"):
        name = Path(cr["path"]).name
        mine = f"yes, at .agents/changes/5-archives/{cr.get('archive_stamp') or '?'}-{name}/"
    else:
        mine = "no (missing from the PR)"
    write_file(
        folder / "delivery.md",
        f"# Delivery\n\n- PR: {cr.get('pr') or 'none'}\n"
        f"- Merged: {cr['merged_at']}\n- Archive in the PR: {mine}\n",
    )


def trash_cr(batch: Batch, cr: dict[str, Any]) -> None:
    """The CR is dropped: its folder goes to `6-trash` at once, the name starting with the date."""
    if not cr.get("path"):
        return
    paths = stage_layout(batch.repo)
    source = cr_directory(batch.repo, cr)
    if source.parent not in (paths["done"], paths["archives"], paths["trash"]):  # not left yet
        _relocate(batch, cr, paths["trash"] / f"{stamp()}-{source.name}")


def archive_name(cr: dict[str, Any], folder: Path) -> str:
    """`<YYMMDD-HHMM>-<number>-<slug>`: the merge time (UTC), so the archives keep the merge
    order; a CR with no recorded merge time takes the time of the close."""
    when = cr.get("merged_at")
    try:
        day = datetime.strptime(when, "%Y-%m-%dT%H:%M:%SZ").strftime("%y%m%d-%H%M")
    except (TypeError, ValueError):
        day = stamp()
    return f"{day}-{folder.name}"


def move_backlog_item(
    repo: Repo, item: str, priority: str | None, paths: dict[str, Path], ready: bool = False
) -> Path:
    """Triage: an inbox or backlog item to a priority, or to `3-ready`; an item of `3-ready`
    back to a priority. `3-ready` keeps no priority."""
    if (priority is None) == (not ready):
        raise ChantierError("triage takes --priority P<n> or --ready, one of them", EXIT_USAGE)
    if priority is not None and priority not in PRIORITIES:
        raise ChantierError(f"priority must be one of {', '.join(PRIORITIES)}", EXIT_USAGE)
    source = repo.planning_path(item, "CR folder")
    held = source.parent.parent == paths["backlog"] and source.parent.name in PRIORITIES
    waiting = source.parent == paths["ready"]
    if source.parent != paths["inbox"] and not held and not waiting:
        raise ChantierError(
            "triage expects a CR folder: 1-inbox/<item>, 2-backlog/P<n>/<item> or "
            f"3-ready/<item>; got {source}",
            EXIT_USAGE,
        )
    if ready:
        if waiting:
            raise ChantierError(f"{source.name} is already in 3-ready", EXIT_PRECONDITION)
        target = paths["ready"] / source.name
        where = "3-ready"
    else:
        if held and source.parent.name == priority:
            raise ChantierError(f"{source.name} is already {priority}", EXIT_PRECONDITION)
        target = paths["backlog"] / priority / source.name
        where = priority
    if target.exists():
        raise ChantierError(
            f"{where} already holds {source.name}: nothing moved", EXIT_PRECONDITION
        )
    move_directory(source, target)
    return target
