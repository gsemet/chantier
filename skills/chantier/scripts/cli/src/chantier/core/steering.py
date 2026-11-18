"""A batch no session ever steered: its steering cost is none, never $0.00."""

from __future__ import annotations

from chantier.core.records import BatchRecord

NO_SESSION = "none: no session steered it"


def never_steered(d: BatchRecord) -> bool:
    """A batch that held no CR and that no steering session ever claimed (no Foreman transcript
    recorded)."""
    return not d.crs and not (d.foreman_transcripts or d.foreman_transcript)
