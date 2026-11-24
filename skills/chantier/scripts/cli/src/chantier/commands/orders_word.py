"""The order being applied: what each kind's function receives."""

from __future__ import annotations

from dataclasses import dataclass

from chantier.core.batch import Batch
from chantier.core.errors import EXIT_USAGE, ChantierError
from chantier.core.records import CrEntry


@dataclass
class Word:
    """One order to apply: `own` is the Foreman acting under the user's grant."""

    b: Batch
    kind: str
    cr_id: str
    c: CrEntry | None
    note: str
    fix_for: str | None = None
    own: bool = False
    release: bool = False
    follow_up: str | None = None
    order_id: str = ""
    stopped: list[str] | None = None  # `order merged`: the line of a gate stopped before the locks
    ended: bool = False  # set by the handler: this order ended the batch's last CR
    add: str = ""  # `order after --add`: the refs to add
    remove: str = ""  # `order after --remove`: the refs to take out
    recorded: str | None = None  # set by the handler: the note the order records (`after`'s ids)
    clause: str = ""  # set by the handler: what ends the order's line (`; close its PR <link>`)


def target(w: Word) -> CrEntry:
    """The CR the order is about: every kind that reaches for it names one."""
    if w.c is None:
        raise ChantierError(f"order {w.kind} names a CR", EXIT_USAGE)
    return w.c
