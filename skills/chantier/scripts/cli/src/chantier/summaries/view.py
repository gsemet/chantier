"""The read view of a CR's summary, for the board's server: one JSON read, a few small hashes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from chantier.core.records import Origin
from chantier.summaries import store as summaries_store
from chantier.summaries.gaps import gap_of

if TYPE_CHECKING:
    from chantier.store import PlanStore


@dataclass(frozen=True)
class SummaryView:
    """What the board shows of a CR's summary; `late` when its summary is behind the Markdown."""

    title: str
    summary: str
    origin: Origin | None
    labels: tuple[str, ...]
    group: str | None
    late: bool


def summary_view(store: PlanStore, folder: Path) -> SummaryView | None:
    """The CR's summary as the board reads it; None when the folder has no `summary.json`. An
    unreadable file is late with empty fields: the caller logs it, nothing is raised."""
    try:
        summary = summaries_store.read(store, folder)
    except summaries_store.UnreadableSummary:
        return SummaryView("", "", None, (), None, late=True)
    if summary is None:
        return None
    gap = gap_of(store, folder)
    return SummaryView(
        summary.title or "",
        summary.summary or "",
        summary.origin,
        tuple(summary.labels),
        summary.group,
        late=gap is not None and gap.kind == "late",
    )
