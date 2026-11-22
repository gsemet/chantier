"""The stage folders of a CR and the moves between them."""

from __future__ import annotations

import re
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from chantier.core.batch import Batch, move_directory
from chantier.core.clock import now, stamp
from chantier.core.errors import EXIT_CONFLICT, EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.files import markdown_title, rel_in, subject
from chantier.core.records import CrEntry, read_batch_json
from chantier.core.repo import Repo
from chantier.store import PlanStore

PRIORITIES = ("P1", "P2", "P3", "P4")


def cr_slug(folder_name: str) -> str:
    """A CR folder's name without its date and its number: how `depends.json` names it."""
    name = re.sub(r"^(?:\d{6}-\d{4}-)+", "", folder_name)
    return re.sub(r"^(?:CR-)?\d+-", "", name, flags=re.I)


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


def _stage_folders(paths: dict[str, Path], include_archives: bool) -> list[Path]:
    """The folders that hold CR folders, in the lifecycle's order."""
    stages = [
        paths["inbox"],
        *(paths["backlog"] / p for p in PRIORITIES),
        paths["ready"],
        paths["pending"],
        paths["actives"],
        paths["done"],
    ]
    return [*stages, paths["archives"]] if include_archives else stages


def cr_folders(
    store: PlanStore, paths: dict[str, Path], include_archives: bool = False
) -> list[Path]:
    """Every CR folder of the planning folder, stage by stage in the lifecycle's order, each stage
    sorted by name. `6-trash` is left out; `5-archives` too unless asked."""
    found: list[Path] = []
    for stage in _stage_folders(paths, include_archives):
        rel = rel_in(store.root, stage)
        if store.is_dir(rel):
            found.extend(
                stage / name for name in store.listdir(rel) if store.is_dir(f"{rel}/{name}")
            )
    return found


def cr_stage(paths: dict[str, Path], folder: Path) -> str | None:
    """The stage key (`inbox`, `backlog`, `ready`, `pending`, `actives`, `done`, `archives`,
    `trash`) of a folder that is directly one stage's CR folder, else None."""
    parent = folder.parent
    if parent.parent == paths["backlog"] and parent.name in PRIORITIES:
        return "backlog"
    keys = ("inbox", "ready", "pending", "actives", "done", "archives", "trash")
    return next((k for k in keys if paths[k] == parent), None)


def changes_lock(repo: Repo) -> AbstractContextManager[None]:
    """The planning folder's lifecycle lock: the store's."""
    return repo.store.lock()


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
    store = repo.store
    if store.is_file(rel_in(store.root, supplied)):
        directory, specification = supplied.parent, supplied
    elif store.is_dir(rel_in(store.root, supplied)):
        directory, specification = supplied, supplied / "03-change-spec.md"
    else:
        raise ChantierError(f"prepared CR not found: {supplied}", EXIT_USAGE)
    in_ready = _check_place(directory, paths)
    specification = _specification(store, specification, directory, supplied, in_ready)
    text = _spec_text(store, specification)
    title = subject(markdown_title(text)) or directory.name
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


def _specification(
    store: PlanStore, specification: Path, directory: Path, supplied: Path, in_ready: bool
) -> Path:
    def is_file(path: Path) -> bool:
        return store.is_file(rel_in(store.root, path))

    if not is_file(specification) and directory.name.startswith("qa-"):
        raise ChantierError(
            f"{directory} is a QA report: an item to triage and split into CRs, not to open",
            EXIT_PRECONDITION,
        )
    if (
        not is_file(specification)
        and in_ready
        and store.is_dir(rel_in(store.root, supplied))
        and is_file(directory / "intake" / "request.md")
    ):
        specification = directory / "intake" / "request.md"  # automatable: the request as received
    if not is_file(specification):
        raise ChantierError(
            f"missing Change Specification: {specification}; grill the CR first", EXIT_PRECONDITION
        )
    return specification


def _spec_text(store: PlanStore, specification: Path) -> str:
    try:
        text = store.read_text(rel_in(store.root, specification))
    except UnicodeDecodeError as e:
        raise ChantierError(
            f"{specification} is not UTF-8: save it as UTF-8 ({e})", EXIT_PRECONDITION
        ) from e
    if not text.strip():
        raise ChantierError(f"empty Change Specification: {specification}", EXIT_PRECONDITION)
    return text


def ensure_unclaimed(repo: Repo, directory: Path) -> None:
    for batch_dir in repo.batch_folders():
        batch = read_batch_json(repo.store, batch_dir / "batch.json")
        for cr in batch.crs:
            if cr.status in {"cancelled", "merged"} or not cr.path:
                continue
            claimed = repo.planning_path(cr.path, "recorded CR path")
            if claimed == directory:
                raise ChantierError(f"{directory} is already in batch {batch.id}", EXIT_CONFLICT)


def cr_directory(repo: Repo, cr: CrEntry) -> Path:
    if not cr.path:
        raise ChantierError(f"{cr.id} has no recorded CR folder", EXIT_PRECONDITION)
    return repo.planning_path(cr.path, "recorded CR path")


def relocate(batch: Batch, cr: CrEntry, target: Path) -> None:
    source = cr_directory(batch.repo, cr)
    batch.move(source, target)
    cr.path = batch.repo.rel(target)


def start_cr(batch: Batch, cr: CrEntry) -> None:
    """`take`: the CR's folder goes from `1-pending` to `2-actives`, before its Driver gets the
    facts. A CR already elsewhere (taken before) stays."""
    if not cr.path:
        return
    paths = stage_layout(batch.repo)
    source = cr_directory(batch.repo, cr)
    if source.parent == paths["pending"]:
        relocate(batch, cr, paths["actives"] / source.name)


def done_cr(batch: Batch, cr: CrEntry) -> None:
    """The CR is merged (a release CR: released): its folder goes to `3-done` and stays until
    `close`, with the merge time, which names its archive. A folder that already left stays."""
    if not cr.path:
        return
    paths = stage_layout(batch.repo)
    source = cr_directory(batch.repo, cr)
    moving = source.parent not in (paths["done"], paths["archives"], paths["trash"])
    where = paths["done"] / source.name if moving else source
    batch.repo.check_publish(
        [source, where, *([where / "delivery.md"] if batch.repo.external else [])]
    )
    if moving:
        relocate(batch, cr, where)
    cr.merged_at = cr.merged_at or now()
    folder = cr_directory(batch.repo, cr)
    if batch.repo.external and batch.repo.store.is_dir(rel_in(batch.repo.store.root, folder)):
        _delivery(batch.repo, cr, folder)


def _delivery(repo: Repo, cr: CrEntry, folder: Path) -> None:
    """`delivery.md`, written in the surface when the merge is recorded: it travels into the
    archive and says where the CR was delivered."""
    if not repo.archive_in_pr:
        mine = "no (project setting)"
    elif cr.archive_seen:
        name = Path(cr.path or "").name
        mine = f"yes, at .agents/changes/5-archives/{cr.archive_stamp or '?'}-{name}/"
    else:
        mine = "no (missing from the PR)"
    repo.store.write_text(
        repo.rel(folder / "delivery.md"),
        f"# Delivery\n\n- PR: {cr.shown_pr() or 'none'}\n"
        f"- Merged: {cr.merged_at}\n- Archive in the PR: {mine}\n",
    )


def trash_cr(batch: Batch, cr: CrEntry) -> None:
    """The CR is dropped: its folder goes to `6-trash` at once, the name starting with the date."""
    if not cr.path:
        return
    paths = stage_layout(batch.repo)
    source = cr_directory(batch.repo, cr)
    if source.parent not in (paths["done"], paths["archives"], paths["trash"]):  # not left yet
        relocate(batch, cr, paths["trash"] / f"{stamp()}-{source.name}")


def archive_name(cr: CrEntry, folder: Path) -> str:
    """`<YYMMDD-HHMM>-<number>-<slug>`: the merge time (UTC), so the archives keep the merge
    order; a CR with no recorded merge time takes the time of the close."""
    when = cr.merged_at
    try:
        day = datetime.strptime(str(when), "%Y-%m-%dT%H:%M:%SZ").strftime("%y%m%d-%H%M")
    except (TypeError, ValueError):
        day = stamp()
    return f"{day}-{folder.name}"


TRIAGE_USAGE = "triage takes --priority P<n>, --ready, --inbox or --running-batch, one of them"


def _destination(paths: dict[str, Path], source: Path, to: str) -> tuple[Path, str]:
    """The folder an item moves to and how it is named in a message; refused when it is there."""
    if to == "inbox":
        folder, where, said = paths["inbox"], "1-inbox", f"{source.name} is already in 1-inbox"
    elif to == "3-ready":
        folder, where, said = paths["ready"], "3-ready", f"{source.name} is already in 3-ready"
    else:
        folder, where, said = paths["backlog"] / to, to, f"{source.name} is already {to}"
    if source.parent == folder:
        raise ChantierError(said, EXIT_PRECONDITION)
    return folder / source.name, where


def move_backlog_item(repo: Repo, item: str, to: str, paths: dict[str, Path]) -> Path:
    """Triage: an item of the inbox, of a priority or of `3-ready` to `to`: `inbox`, a priority
    or `3-ready`. `3-ready` keeps no priority."""
    if to not in ("inbox", "3-ready", *PRIORITIES):
        raise ChantierError(TRIAGE_USAGE, EXIT_USAGE)
    source = repo.planning_path(item, "CR folder")
    held = source.parent.parent == paths["backlog"] and source.parent.name in PRIORITIES
    if source.parent not in (paths["inbox"], paths["ready"]) and not held:
        raise ChantierError(
            "triage expects a CR folder: 1-inbox/<item>, 2-backlog/P<n>/<item> or "
            f"3-ready/<item>; got {source}",
            EXIT_USAGE,
        )
    target, where = _destination(paths, source, to)
    if repo.store.exists(rel_in(repo.store.root, target)):
        raise ChantierError(
            f"{where} already holds {source.name}: nothing moved", EXIT_PRECONDITION
        )
    move_directory(repo, source, target)
    return target


def specifying_markers(repo: Repo) -> list[str]:
    """The CR folders with a `work/specifying` marker in the project's planning folder: the
    inbox, `2-backlog/P1`..`P4` and `3-ready`, in that order, each stage by folder name."""
    paths = stage_layout(repo)
    stages = [paths["inbox"], *(paths["backlog"] / p for p in PRIORITIES), paths["ready"]]
    store = repo.store
    found: list[str] = []
    for stage in stages:
        rel = rel_in(store.root, stage)
        if store.is_dir(rel):
            found += [n for n in store.listdir(rel) if store.exists(f"{rel}/{n}/work/specifying")]
    return found
