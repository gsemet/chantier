"""The mark of a CR bound for the running batch (`work/running-batch`), role-free: `triage
<folder> --running-batch` and the board's lane write it, any other triage, `abandon` and the
CR's join (`order add`) clear it, and `status` names the marked CRs. It moves no folder and
touches no file under `4-batch/`."""

from __future__ import annotations

from pathlib import Path

from chantier.core.clock import now
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.files import rel_in
from chantier.core.repo import Repo
from chantier.lifecycle.stages import PRIORITIES, changes_lock, cr_folder_arg, stage_layout
from chantier.status.write import write_dashboard
from chantier.store import PlanStore

MARK = "running-batch"  # in the CR's `work/` folder: one line, the time and the batch's id
SPECIFYING = "specifying"
SPECIFICATION = "03-change-spec.md"


def mark_path(folder: Path) -> Path:
    return folder / "work" / MARK


def open_batch_id(repo: Repo) -> str | None:
    """The open batch's id: the batch of `4-batch/`, paused or running; None once closed."""
    ids = repo.batch_ids()
    return ids[0] if ids else None


def _rel(store: PlanStore, path: Path) -> str:
    return rel_in(store.root, path)


def marked_for(store: PlanStore, folder: Path) -> str | None:
    """The batch id a folder's mark names; None with no mark."""
    rel = _rel(store, mark_path(folder))
    if not store.is_file(rel):
        return None
    words = store.read_text(rel).split()
    return words[-1] if words else ""


def grilled(store: PlanStore, folder: Path) -> bool:
    return store.exists(_rel(store, folder / "work" / SPECIFYING)) or store.is_file(
        _rel(store, folder / SPECIFICATION)
    )


def mark_running_batch(repo: Repo, item: str) -> list[str]:
    """`triage <folder> --running-batch`: a grilled inbox or backlog CR is marked for the open
    batch; it joins once its specification is final, by `order add`."""
    paths = stage_layout(repo)
    source = cr_folder_arg(repo, item)
    slug, folder = source.name, repo.rel(source)
    if source.parent == paths["ready"]:
        raise ChantierError(
            f"{slug} is in 3-ready: `order add --note {folder}` joins it now", EXIT_PRECONDITION
        )
    held = source.parent.parent == paths["backlog"] and source.parent.name in PRIORITIES
    if (source.parent != paths["inbox"] and not held) or not repo.store.is_dir(
        _rel(repo.store, source)
    ):
        raise ChantierError(
            "triage --running-batch expects a CR folder: 1-inbox/<item> or 2-backlog/P<n>/<item>; "
            f"got {source}",
            EXIT_USAGE,
        )
    batch = open_batch_id(repo)
    if batch is None:
        raise ChantierError(
            f"no open batch: {slug} goes to the next batch (`triage {folder} --ready`)",
            EXIT_PRECONDITION,
        )
    if not grilled(repo.store, source):
        raise ChantierError(f"{slug} is not grilled: grill it first", EXIT_PRECONDITION)
    mark = mark_path(source)
    repo.check_publish([mark])
    with changes_lock(repo):
        repo.store.write_text(repo.rel(mark), f"{now()} {batch}\n")
        write_dashboard(repo, paths)
    return [
        f"{slug} marked for the running batch {batch}: it joins once its specification is final "
        f"(`order add --note {folder}`)"
    ]


def clear_mark(repo: Repo, folder: Path) -> None:
    """The user changed the CR's destination (another triage, `abandon`): its mark goes. Called
    under `changes_lock`, after the folder's move was checked and done."""
    path = mark_path(folder)
    if repo.store.is_file(_rel(repo.store, path)):
        repo.store.remove(repo.rel(path))


def _state(store: PlanStore, folder: Path) -> str:
    if store.exists(_rel(store, folder / "work" / SPECIFYING)):
        return "specifying"
    written = store.is_file(_rel(store, folder / SPECIFICATION))
    return "written" if written else "no specification"


def _marked_folders(repo: Repo) -> list[Path]:
    paths = stage_layout(repo)
    places = (paths["inbox"], *(paths["backlog"] / p for p in PRIORITIES), paths["ready"])
    store = repo.store
    return [
        d
        for place in places
        if store.is_dir(_rel(store, place))
        for d in (place / n for n in store.listdir(_rel(store, place)))
        if store.is_file(_rel(store, mark_path(d)))
    ]


def running_batch_lines(repo: Repo, batch: str | None) -> list[str]:
    """`status`: the CRs marked for the open batch `batch` and not joined yet, then one line per
    stale mark (a batch that is not the open one, closed)."""
    marked: list[str] = []
    stale: list[str] = []
    written = False
    for d in _marked_folders(repo):
        folder, owner = repo.rel(d), marked_for(repo.store, d)
        if batch is not None and owner == batch:
            state = _state(repo.store, d)
            written = written or state == "written"
            marked.append(f"{folder} ({state})")
        else:
            stale.append(
                f"running batch: {folder} marked for {owner or 'no batch'}, which is closed: "
                f"`triage {folder} --ready`"
            )
    lines = []
    if marked:
        tail = (
            ": `order add --note <folder>` once no critic runs and no open question remains"
            if written
            else ""
        )
        lines.append(
            f"running batch: {len(marked)} CRs marked, not joined: {', '.join(marked)}{tail}"
        )
    return lines + stale
