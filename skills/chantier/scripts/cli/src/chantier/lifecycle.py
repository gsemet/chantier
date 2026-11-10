"""The CR folders: the stage folders under `.agents/changes/`, a prepared CR, and the moves
between stages, each refused rather than half done.

The tree, in `.agents/changes/`: `1-inbox`, `2-backlog/P1..P4`, `3-ready` (waiting for the next
batch), `4-batch` (the one current batch: its own files and the state folders `1-pending`,
`2-actives`, `3-done`), `5-archives` (merged, after `close`) and `6-trash` (dropped).

An older tree (`3-requests/batch-<n>/`, `4-archives/`, `5-trash/`) is converted in place by the
first command that runs after the update (`convert_old_tree`), the way `read_batch_json` reads the
older words of a record: once, under the locks, all or nothing.
"""
from __future__ import annotations

import contextlib
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .state import (EXIT_CONFLICT, EXIT_EXTERNAL, EXIT_PRECONDITION, EXIT_USAGE, LOCK_TIMEOUT_S, Batch,
                    ChantierError, Repo, read_batch_json, _retry, _try_lock, _unlock, move_directory,
                    now, project_path, stamp, write_file)
PRIORITIES = ("P1", "P2", "P3", "P4")
STATE_FOLDERS = ("1-pending", "2-actives", "3-done")  # the batch's, in `4-batch/`


def stage_layout(repo: Repo) -> dict[str, Path]:
    """The stage folders, always the same: `.agents/changes/1-inbox` and so on. `batches` is the
    parent of `pending`, `actives` and `done`, the states of the CRs inside the batch."""
    base = repo.changes.resolve()
    batches = base / "4-batch"
    return {"inbox": base / "1-inbox", "backlog": base / "2-backlog", "ready": base / "3-ready",
            "batches": batches, "pending": batches / "1-pending", "actives": batches / "2-actives",
            "done": batches / "3-done", "archives": base / "5-archives", "trash": base / "6-trash"}


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


def prepared_cr(repo: Repo, item: str, paths: dict[str, Path]) -> PreparedCR:
    """A CR folder in the inbox, the priority backlog or `3-ready`, with a specification. A CR in
    `3-ready` may have none (automatable): its request, as received, is then its specification."""
    if not item.strip():
        raise ChantierError("open requires <prepared-CR-folder> or <specification-file>; "
                            "file and grill the CR first", EXIT_USAGE)
    supplied = project_path(repo.root, item, "CR item")
    if supplied.is_file():
        directory, specification = supplied.parent, supplied
    elif supplied.is_dir():
        directory, specification = supplied, supplied / "03-change-spec.md"
    else:
        raise ChantierError(f"prepared CR not found: {supplied}", EXIT_USAGE)
    in_backlog = directory.parent.parent == paths["backlog"] and directory.parent.name in PRIORITIES
    in_ready = directory.parent == paths["ready"]
    if paths["batches"] in directory.parents:
        raise ChantierError(f"{directory} is already active; resume its existing batch instead",
                            EXIT_PRECONDITION)
    if directory.parent != paths["inbox"] and not in_backlog and not in_ready:
        raise ChantierError(f"{directory} is not a CR in the configured inbox, priority backlog or "
                            "3-ready", EXIT_USAGE)
    if not specification.is_file() and directory.name.startswith("qa-"):
        raise ChantierError(f"{directory} is a QA report: an item to triage and split into CRs, "
                            "not to open", EXIT_PRECONDITION)
    if not specification.is_file() and in_ready and supplied.is_dir() \
            and (directory / "intake" / "request.md").is_file():
        specification = directory / "intake" / "request.md"  # automatable: the request as received
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
    return PreparedCR(directory, specification, title)


def ensure_unclaimed(repo: Repo, directory: Path) -> None:
    for batch_dir in repo.batch_folders():
        batch = read_batch_json(batch_dir / "batch.json")
        if batch.get("status") == "paused":
            continue
        for cr in batch.get("crs", []):
            if cr.get("status") in {"cancelled", "merged"} or not cr.get("path"):
                continue
            claimed = project_path(repo.root, cr["path"], "recorded CR path")
            if claimed == directory:
                raise ChantierError(f"{directory} is already in batch {batch['id']}",
                                    EXIT_CONFLICT)


def cr_directory(repo: Repo, cr: dict) -> Path:
    if not cr.get("path"):
        raise ChantierError(f"{cr['id']} has no recorded CR folder", EXIT_PRECONDITION)
    return project_path(repo.root, cr["path"], "recorded CR path")


def _relocate(batch: Batch, cr: dict, target: Path) -> None:
    source = cr_directory(batch.repo, cr)
    batch.move(source, target)
    cr["path"] = target.relative_to(batch.repo.root).as_posix()
    old = batch.repo.changes / "3-requests"  # a working CR of a converted tree was its last tenant
    for folder in (source.parent, source.parent.parent):
        if old in (folder, *folder.parents) and folder.is_dir() and not any(folder.iterdir()):
            with contextlib.suppress(OSError):
                folder.rmdir()


def start_cr(batch: Batch, cr: dict) -> None:
    """`take`: the CR's folder goes from `1-pending` to `2-actives`, before its Driver gets the
    facts. A CR already elsewhere (taken before, or still at the path of an older tree) stays."""
    if not cr.get("path"):
        return
    paths = stage_layout(batch.repo)
    source = cr_directory(batch.repo, cr)
    if source.parent == paths["pending"]:
        _relocate(batch, cr, paths["actives"] / source.name)


def done_cr(batch: Batch, cr: dict) -> None:
    """The CR is merged (a release CR: released): its folder goes to `3-done` and stays until
    `close`, with the merge time, which names its archive. A folder that already left stays."""
    if not cr.get("path"):
        return
    paths = stage_layout(batch.repo)
    source = cr_directory(batch.repo, cr)
    if source.parent not in (paths["done"], paths["archives"], paths["trash"]):
        _relocate(batch, cr, paths["done"] / source.name)
    cr["merged_at"] = cr.get("merged_at") or now()


def trash_cr(batch: Batch, cr: dict) -> None:
    """The CR is dropped: its folder goes to `6-trash` at once, the name starting with the date."""
    if not cr.get("path"):
        return
    paths = stage_layout(batch.repo)
    source = cr_directory(batch.repo, cr)
    if source.parent not in (paths["done"], paths["archives"], paths["trash"]):  # not left yet
        _relocate(batch, cr, paths["trash"] / f"{stamp()}-{source.name}")


def archive_name(cr: dict, folder: Path) -> str:
    """`<YYMMDD-HHMM>-<number>-<slug>`: the merge time (UTC), so the archives keep the merge
    order; a CR with no recorded merge time takes the time of the close."""
    when = cr.get("merged_at")
    try:
        day = datetime.strptime(when, "%Y-%m-%dT%H:%M:%SZ").strftime("%y%m%d-%H%M")
    except (TypeError, ValueError):
        day = stamp()
    return f"{day}-{folder.name}"


def move_backlog_item(repo: Repo, item: str, priority: str | None, paths: dict[str, Path],
                      ready: bool = False) -> Path:
    """Triage: an inbox or backlog item to a priority, or to `3-ready`; an item of `3-ready`
    back to a priority. `3-ready` keeps no priority."""
    if (priority is None) == (not ready):
        raise ChantierError("triage takes --priority P<n> or --ready, one of them", EXIT_USAGE)
    if priority is not None and priority not in PRIORITIES:
        raise ChantierError(f"priority must be one of {', '.join(PRIORITIES)}", EXIT_USAGE)
    source = project_path(repo.root, item, "CR folder")
    held = source.parent.parent == paths["backlog"] and source.parent.name in PRIORITIES
    waiting = source.parent == paths["ready"]
    if source.parent != paths["inbox"] and not held and not waiting:
        raise ChantierError("triage expects a CR folder: 1-inbox/<item>, 2-backlog/P<n>/<item> or "
                            f"3-ready/<item>; got {source}", EXIT_USAGE)
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
        raise ChantierError(f"{where} already holds {source.name}: nothing moved",
                            EXIT_PRECONDITION)
    move_directory(source, target)
    return target


# ---- the old tree, converted in place ---------------------------------------------------------

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
        (d / "batch.json").is_file() for d in old.iterdir() if d.is_dir())


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
    print("converted .agents/changes to the new tree" + (": " + ", ".join(parts) if parts else ""),
          file=sys.stderr)


def _free_target(old: Path, new: Path) -> bool:
    """Is `new` to be written? An existing one that holds no file (empty folders from an `init`)
    gives way; one that holds files is refused, naming both."""
    if not new.exists() and not new.is_symlink():
        return False
    if new.is_dir() and not _has_files(new):
        return True
    raise ChantierError(f"cannot convert the tree: both {old} and {new} exist; merge or remove "
                        "one of them. Nothing was moved.", EXIT_PRECONDITION)


def _convert(repo: Repo) -> list[str]:
    base, old = repo.changes, repo.changes / "3-requests"
    batches = sorted(d for d in old.iterdir() if d.is_dir() and (d / "batch.json").is_file()) \
        if old.is_dir() else []
    if len(batches) > 1:
        raise ChantierError("cannot convert the tree: more than one batch folder in "
                            f"{old} ({', '.join(d.name for d in batches)}); one batch at a time. "
                            "Nothing was moved.", EXIT_PRECONDITION)
    plain = [("4-archives", "5-archives"), ("5-trash", "6-trash")]
    plain = [(base / a, base / b) for a, b in plain if (base / a).is_dir()]
    clear = [_free_target(a, b) for a, b in plain]
    batch = batches[0] if batches else None
    target = base / "4-batch"
    clear_batch = _free_target(batch, target) if batch else False
    renames: list[tuple[Path, Path]] = []
    parts: list[str] = []
    lock = original = None

    def rename(src: Path, dst: Path) -> None:
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            _retry(src.rename, dst)
        except OSError as e:
            raise ChantierError(f"cannot convert the tree: {src} is in use ({e}); close what "
                                "holds it and run any command again. Nothing was changed.",
                                EXIT_EXTERNAL) from e
        renames.append((src, dst))

    try:
        if batch:
            lock = open(batch / ".lock", "a+")  # the batch's own lock, held while its files move
            deadline = time.monotonic() + LOCK_TIMEOUT_S
            while not _try_lock(lock):
                if time.monotonic() > deadline:
                    raise ChantierError(f"batch {batch.name} is locked for over {LOCK_TIMEOUT_S} s")
                time.sleep(0.05)
            original = (batch / "batch.json").read_bytes()
        moves: list[list[str]] = []
        for (a, b), empty in zip(plain, clear):
            if empty:
                shutil.rmtree(b)
            rename(a, b)
            parts.append(f"{a.name} -> {b.name}")
        if batch:
            if clear_batch:
                shutil.rmtree(target)
            data = read_batch_json(batch / "batch.json")
            where = {}  # a CR folder of the batch -> the state folder its status gives
            for cr in data["crs"]:
                if not cr.get("path"):
                    continue
                folder = project_path(repo.root, cr["path"], "recorded CR path")
                if folder.parent == batch.resolve() and folder.is_dir():
                    state = {"queued": "1-pending", "ready": "2-actives",
                             "blocked": "2-actives"}.get(cr["status"])
                    if state:
                        where[folder] = target / state / folder.name
            for item in sorted(batch.iterdir()):
                # the batch's own files and its Demo folder move; its CRs go by status, and any
                # other folder stays where it is, never taken for the batch's
                if item.name != ".lock" and (item.is_file() or item.name == "demo"):
                    rename(item, target / item.name)
                    moves.append([_rel(repo, item), _rel(repo, target / item.name)])
            for folder, dest in where.items():
                rename(folder, dest)
                moves.append([_rel(repo, folder), _rel(repo, dest)])
            for state in STATE_FOLDERS:
                (target / state).mkdir(parents=True, exist_ok=True)
            with Batch(repo, data["id"], actor="cli") as b:
                for cr in b.data["crs"]:
                    path = cr.get("path")
                    if not path:
                        continue
                    moved = where.get(project_path(repo.root, path, "recorded CR path"))
                    cr["path"] = (_rel(repo, moved) if moved else
                                  path.replace(".agents/changes/4-archives/",
                                               ".agents/changes/5-archives/")
                                  .replace(".agents/changes/5-trash/", ".agents/changes/6-trash/"))
                    if moved and not moved.is_dir():
                        raise ChantierError(f"{cr['id']}: {cr['path']} does not exist")
                b.log("tree", None, moves=moves + [[f".agents/changes/{a.name}",
                                                    f".agents/changes/{z.name}"]
                                                   for a, z in plain])
            parts.insert(0, "3-requests -> 4-batch")
    except BaseException as e:
        _undo(renames, batch, original, lock)
        if isinstance(e, OSError):
            raise ChantierError(f"cannot convert the tree: {e}. Nothing was changed.",
                                EXIT_EXTERNAL) from e
        raise
    if lock:
        with contextlib.suppress(Exception):
            _unlock(lock)
        lock.close()
    # the older index and the batch's old folder, once nothing of the batch is left in them
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
    if not batch:  # a batch writes the index through `Batch`
        write_dashboard_after_rename(repo)
    return parts


def _rel(repo: Repo, path: Path) -> str:
    return path.relative_to(repo.root).as_posix()


def _undo(renames: list[tuple[Path, Path]], batch: Path | None, original: bytes | None, lock) -> None:
    """Put every rename back, last first, and the batch's record as it was."""
    stuck = []
    for src, dst in reversed(renames):
        try:
            _retry(dst.rename, src)
        except OSError:
            stuck.append(f"{dst} -> {src}")
    if batch is not None and original is not None and (batch / "batch.json").is_file() and not stuck:
        write_file(batch / "batch.json", original.decode("utf-8"))
    if lock is not None:
        with contextlib.suppress(Exception):
            _unlock(lock)
        lock.close()
    if stuck:
        raise ChantierError("cannot roll back the conversion of the tree; preserve both paths and "
                            "resolve manually: " + "; ".join(stuck), EXIT_EXTERNAL)


def write_dashboard_after_rename(repo: Repo) -> None:
    """Archives and trash moved without a batch: the index at the root is written anew."""
    from .status import write_dashboard  # avoid an import cycle
    with contextlib.suppress(OSError):  # a file that cannot be written; any other error shows
        write_dashboard(repo, stage_layout(repo))
