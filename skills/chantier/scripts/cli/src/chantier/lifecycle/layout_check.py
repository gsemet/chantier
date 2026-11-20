"""`validate`'s reading of the planning folder's layout: where a CR folder may stand (placement)
and what a live CR folder holds (shape). Read-only; it returns findings and repairs nothing."""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from chantier.core import waits
from chantier.core.repo import Repo
from chantier.lifecycle.stages import PRIORITIES, STATE_FOLDERS, cr_folders, stage_layout
from chantier.summaries.sources import INTAKE

Severity = Literal["error", "gap"]

STAGES = ("1-inbox", "2-backlog", "3-ready", "4-batch", "5-archives", "6-trash")
CR_LIKE = (INTAKE, "01-intent.md", "02-answers.md", "03-change-spec.md", "summary.json")

# A CR folder's tree: concepts.md ("Change Request") gives the folders and the Markdown files,
# `summary.json` and the STATUS files; `delivery.md` is an archive's (`stages.py`),
# `formerly.json` a CR taken out of a batch's, `waits.json` a backlog CR's open waits (in a batch
# they are the record's), `depends.json` a dependency's, `report.md` and
# `conversation.md` a release CR's sources (release-template.md).
CR_FOLDERS = ("intake", "evidence", "work", "prototypes", "experiments")
CR_FILES = (
    "01-intent.md",
    "02-answers.md",
    "03-change-spec.md",
    "summary.json",
    "STATUS.md",
    "STATUS.json",
    "delivery.md",
    "formerly.json",
    "waits.json",
    "depends.json",
    "report.md",
    "conversation.md",
)
LAYOUT_GAP = 'not in a CR folder\'s layout (concepts.md, "Change Request")'
LIVE_STAGES = ("inbox", "ready", "pending", "actives", "done")
OUTSIDE_CLAIM = re.compile(r"^(?:\d{6}(?:-\d{4})?-)?outside-")
OUTSIDE_NAME = re.compile(r"^\d{6}-\d{4}-outside-\d+-[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class Finding:
    """One thing `validate` reports: an `error` (chantier or the board misreads the folder) or a
    `gap` (to fix, nothing breaks), the path it is about and what is wrong."""

    severity: Severity
    path: str
    text: str

    def line(self) -> str:
        return f"{self.severity} {self.path}: {self.text}"


def _dirs(folder: Path) -> list[Path]:
    """The folders directly in `folder`, dot names left out, sorted."""
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_dir() and not p.name.startswith("."))


def _cr_like(folder: Path) -> bool:
    return any((folder / name).exists() for name in CR_LIKE)


def _holds_cr(folder: Path) -> bool:
    return any(_cr_like(child) for child in _dirs(folder))


def _misplaced_priority(paths: dict[str, Path], folder: Path) -> bool:
    """A folder named `P1`..`P4` outside `2-backlog/` that holds a CR."""
    inside = folder.parent == paths["backlog"] or folder.parent.parent == paths["backlog"]
    return folder.name in PRIORITIES and not inside and _holds_cr(folder)


def stage_crs(repo: Repo) -> tuple[list[Path], list[Path]]:
    """The CR folders of the live stages, and those of `5-archives` and `6-trash`; a misplaced
    priority folder is no CR."""
    paths = stage_layout(repo)
    live = [f for f in cr_folders(paths) if not f.name.startswith(".")]
    closed = [*_dirs(paths["archives"]), *_dirs(paths["trash"])]
    closed = [f for f in closed if f != paths["archives"] / "batches"]
    return (
        [f for f in live if not _misplaced_priority(paths, f)],
        [f for f in closed if not _misplaced_priority(paths, f)],
    )


def _nested(cr: Path) -> Iterator[Path]:
    """The CR-like folders under a CR folder, at any depth, the outermost of each."""
    for root, dirs, _ in os.walk(cr):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in list(dirs):
            if _cr_like(Path(root) / name):
                dirs.remove(name)
                yield Path(root) / name


def _top_level(repo: Repo) -> list[Finding]:
    return [
        Finding("error", repo.rel(folder), "a CR outside a stage folder")
        for folder in _dirs(repo.changes.resolve())
        if folder.name not in STAGES and (_cr_like(folder) or _holds_cr(folder))
    ]


def _backlog_and_batch(repo: Repo, paths: dict[str, Path]) -> list[Finding]:
    found: list[Finding] = []
    for folder in _dirs(paths["backlog"]):
        if folder.name in PRIORITIES:
            continue
        text = "not a priority folder (P1..P4)"
        if _cr_like(folder):
            text = (
                "in 2-backlog without a P1..P4 folder → move it into 2-backlog/P<n>/ "
                "(`triage` reads no such folder)"
            )
        found.append(Finding("error", repo.rel(folder), text))
    text = "not a batch state folder (1-pending, 2-actives, 3-done)"
    found += [
        Finding("error", repo.rel(folder), text)
        for folder in _dirs(paths["batches"])
        if folder.name not in STATE_FOLDERS
    ]
    return found


def _outside_names(repo: Repo, paths: dict[str, Path]) -> list[Finding]:
    """A folder of `5-archives` that claims the outside form (`outside-` at its start or after a
    date or stamp) must be named `<YYMMDD-HHMM>-outside-<number>-<slug>`; other names are free."""
    text = "not an outside archive's name (<YYMMDD-HHMM>-outside-<number>-<slug>) → rename it"
    return [
        Finding("error", repo.rel(folder), text)
        for folder in _dirs(paths["archives"])
        if folder.name != "batches"
        and OUTSIDE_CLAIM.match(folder.name)
        and not OUTSIDE_NAME.match(folder.name)
    ]


def placement(repo: Repo) -> list[Finding]:
    """Where a CR folder may stand, in every stage: errors."""
    paths = stage_layout(repo)
    found = _top_level(repo) + _backlog_and_batch(repo, paths) + _outside_names(repo, paths)
    for stage in (*LIVE_STAGES, "archives", "trash"):
        found += [
            Finding("error", repo.rel(folder), "a priority folder outside 2-backlog")
            for folder in _dirs(paths[stage])
            if _misplaced_priority(paths, folder)
        ]
    live, closed = stage_crs(repo)
    for cr in [*live, *closed]:
        found += [
            Finding("error", repo.rel(inner), f"a CR inside the CR {repo.rel(cr)}")
            for inner in _nested(cr)
        ]
    return found


def _waits_finding(repo: Repo, cr: Path, entry: Path) -> Finding | None:
    """`waits.json` belongs to the backlog (inbox, backlog, 3-ready): in a batch it is unknown
    (the join consumes it), and anywhere else it must be of the form chantier writes."""
    path = f"{repo.rel(cr)}/{entry.name}"
    if stage_layout(repo)["batches"] in cr.parents:
        return Finding("gap", path, LAYOUT_GAP)
    try:
        waits.read_file(cr)
    except waits.WaitsInvalid as e:
        return Finding("error", path, f"waits.json is not valid: {e}")
    return None


def _entry(repo: Repo, cr: Path, entry: Path) -> Finding | None:
    name, path = entry.name, f"{repo.rel(cr)}/{entry.name}"
    if name == waits.FILE and entry.is_file():
        return _waits_finding(repo, cr, entry)
    if name in CR_FOLDERS and not entry.is_dir():
        return Finding("error", path, "a file where chantier reads a folder")
    if name in CR_FILES and entry.is_dir():
        return Finding("error", path, "a folder where chantier reads a file")
    if name not in (*CR_FOLDERS, *CR_FILES):
        return Finding("gap", path, 'not in a CR folder\'s layout (concepts.md, "Change Request")')
    return None


def _has_request(cr: Path) -> bool:
    intake = cr / INTAKE
    return (
        (intake.is_dir() and any(p.is_file() for p in intake.glob("*.md")))
        or (cr / "01-intent.md").is_file()
        or (cr / "03-change-spec.md").is_file()
    )


def _cr_shape(repo: Repo, cr: Path) -> list[Finding]:
    found = [
        f
        for entry in sorted(cr.iterdir())
        if not entry.name.startswith(".") and (f := _entry(repo, cr, entry))
    ]
    if not _has_request(cr):
        found.append(
            Finding(
                "gap",
                repo.rel(cr),
                "no request (no intake/*.md, 01-intent.md or 03-change-spec.md) → "
                "write its request or move the folder out",
            )
        )
    return found


def shape(repo: Repo) -> list[Finding]:
    """What the live stages hold: a file in a stage folder, a CR folder with no request, an entry
    outside the CR's tree, an entry of the wrong kind."""
    paths = stage_layout(repo)
    found: list[Finding] = []
    stages = [*(paths[k] for k in LIVE_STAGES), *(paths["backlog"] / p for p in PRIORITIES)]
    for stage in stages:
        found += [
            Finding(
                "gap",
                repo.rel(item),
                "a file in a stage folder, not a CR → move it into a CR folder or out of the "
                "planning folder",
            )
            for item in (sorted(stage.iterdir()) if stage.is_dir() else [])
            if item.is_file() and not item.name.startswith(".")
        ]
    for cr in stage_crs(repo)[0]:
        found += _cr_shape(repo, cr)
    return found
