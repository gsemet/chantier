"""What is missing or late in a CR's summary."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

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
