"""`sync-late@1`: the oldest change the writer has not pushed passed `late`."""

from __future__ import annotations

from typing import Any

from chantier.writer import times
from chantier.writer.surface import Surface


class Late(Surface):
    """A mixin of `Writer`, which sets these."""

    record: dict[str, Any]
    now: float
    pending_mono: float | None
    unpushed_mono: float | None
    late_told: bool

    def _late(self) -> None:
        """`sync-late@1`, once per episode: the oldest change not pushed passed `late`."""
        r = self.record
        if not r["pending"] and not r["ahead"]:
            self.late_told = False
            return
        olds = [
            (mono, stamp)
            for mono, stamp in (
                (self.pending_mono, r["pending_since"]),
                (self.unpushed_mono, r["unpushed_since"]),
            )
            if mono is not None
        ]
        if not olds or self.late_told:
            return
        mono, stamp = min(olds)
        if self.now - mono >= times.late_s():
            self.late_told = True
            self._tell(
                {
                    "type": "sync-late@1",
                    "since": stamp,
                    "paths": r["pending"],
                    "ahead": r["ahead"],
                }
            )
