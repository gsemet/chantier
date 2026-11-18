"""What is missing or late in a CR's summary."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from chantier.core.repo import Repo
from chantier.summaries import store
from chantier.summaries.sources import Change, checksums, diff

GapKind = Literal["unreadable", "no summary", "late"]


@dataclass(frozen=True)
class Gap:
    """One CR's gap: its kind, and the files that changed (late) or the error (unreadable)."""

    kind: GapKind
    folder: Path
    changes: tuple[Change, ...] = ()
    error: str = ""


def gap_of(folder: Path) -> Gap | None:
    """The first gap that applies to a CR folder, or None. A folder with no covered file is not a
    CR for this check."""
    current = checksums(folder)
    if not current:
        return None
    try:
        summary = store.read(folder)
    except store.UnreadableSummary as e:
        return Gap("unreadable", folder, error=e.why)
    if summary is None or not summary.title or not summary.summary:
        return Gap("no summary", folder)
    changes = diff(summary.sources, current)
    return Gap("late", folder, tuple(changes)) if changes else None


def gap_line(repo: Repo, gap: Gap) -> str:
    """The line `summary lint` prints for a gap, and the command that closes it."""
    path = repo.rel(gap.folder)  # the form `summary set` reads: relative to the planning folder
    if gap.kind == "no summary":
        return (
            f"{path}: no summary → summary set {path} "
            '--title "<title>" --summary "<the CR\'s state now>"'
        )
    if gap.kind == "unreadable":
        return (
            f"{path}: summary.json unreadable ({gap.error}) → repair or remove it, "
            f"then summary set {path} …"
        )
    files = ", ".join(f"{c.path} {c.how}" for c in gap.changes)
    return (
        f'{path}: summary late ({files}) → read them, then summary set {path} --summary "<…>" '
        "or --unchanged"
    )
