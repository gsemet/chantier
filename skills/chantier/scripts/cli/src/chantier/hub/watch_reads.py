"""What the watcher (`watch.py`) is told at its start (`Rules`) and reads of the planning folder:
its subscription, the seat, the open batch; and the pull path (`watch --once --after SEQ`), which
reads the journal and nothing else."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from typing import Any

from chantier.core.errors import EXIT_USAGE, ChantierError
from chantier.core.files import rel_in
from chantier.core.records import read_batch_json
from chantier.core.repo import Repo
from chantier.core.seat import read_seat
from chantier.hub import arrival_mark, autostart, journal
from chantier.hub.watch_lines import FOREMAN_CLOSED, FOREMAN_OTHER, FOREMAN_TYPES, Ended


@dataclass
class Rules:
    """What a watcher is told at its start: the `--for` values, `events.wake_every` in seconds
    (0 for none), the first configuration problem outside the `events` block, if any, and
    whether it streams (`--stream`: tell each block and run on)."""

    audiences: list[str] = field(default_factory=list)
    wake_every: float = 0.0
    note: str | None = None
    stream: bool = False


def seat_moved(repo: Repo, session: str) -> bool:
    """Whether `seat.json` records a transcript that is not this session's key. No seat, a seat
    with no transcript, an unreadable one or a session keyed `none`: nothing to compare."""
    if session == autostart.NONE:
        return False
    try:
        held = read_seat(repo)
    except ChantierError:
        return False
    kept = re.sub(r"[^A-Za-z0-9-]", "", (held.transcript if held else None) or "")
    return bool(kept) and kept != session


def foreman_lines(lines: list[dict[str, Any]], batch: str) -> list[dict[str, Any]]:
    """The Foreman's watcher reads only the lines of its batch that the Foreman acts on."""
    return [e for e in lines if e.get("type") in FOREMAN_TYPES and e.get("batch") == batch]


def foreman_end(repo: Repo, batch: str, session: str) -> Ended | None:
    """The line the Foreman's watcher ends with when `batch` is closed or no longer records
    `session` as its Foreman, else None. It never looks at the seat."""
    d = autostart.open_record(repo)
    if d is None or d.id != batch:
        return Ended(FOREMAN_CLOSED.format(batch=batch), 0)
    if not autostart.records_foreman(d, session):
        return Ended(FOREMAN_OTHER.format(batch=batch), 0)
    return None


def subscription(session: str, audiences: list[str] | tuple[str, ...] = ()) -> list[str]:
    """The audience values a watcher reads, each once: `project`, its own session (not with the
    key `none`), then the `--for` values in their order."""
    own = [] if session == autostart.NONE else [f"session:{session}"]
    return list(dict.fromkeys([journal.PROJECT, *own, *audiences]))


def open_batch(repo: Repo) -> str | None:
    """The id of the batch running or paused, None with none."""
    path = repo.batches / "batch.json"
    if not repo.store.is_file(rel_in(repo.store.root, path)):
        return None
    try:
        d = read_batch_json(repo.store, path)
    except (OSError, ValueError, ChantierError):
        return None
    return d.id if d.status in ("running", "paused") else None


def once(repo: Repo, after: int, audiences: list[str] | tuple[str, ...] = ()) -> list[str]:
    """The pull path: the lines past `after` that are for it, whether they wake or not, and the
    cursor of the last line read, whoever it was for, with the command for the next message."""
    subscribed = subscription(autostart.session_key(), audiences)
    entries = journal.read(repo.store, repo.changes)[0]
    last = journal.last_seq(entries)
    if after > last:
        raise ChantierError(
            f"watch: --after {after} is past the journal's end ({last})", EXIT_USAGE
        )
    new = sorted(
        (e for e in entries if type(e.get("seq")) is int and e["seq"] > after),
        key=lambda e: e["seq"],
    )
    mine = [e for e in new if journal.for_subscription(e, subscribed)]
    arrival_mark.tell_arrivals(repo, mine)
    return [
        *(journal.event_text(e) for e in mine),
        f"watch: cursor {last}; next, at the user's next message: "
        f"{autostart.pull_command(repo, last)}",
    ]


def checked(repo: Repo, args: argparse.Namespace) -> int:
    """The arguments of `watch`, refused in one line when they do not go together; the journal's
    last sequence number."""
    for value in args.audience or []:
        if not journal.audience_ok(value):
            raise ChantierError(
                f'watch: --for "{value}": one of {journal.AUDIENCE_FORMS}', EXIT_USAGE
            )
    if args.once and args.stream:
        raise ChantierError("watch: --stream and --once do not go together", EXIT_USAGE)
    if args.once and args.after is None:
        raise ChantierError("watch --once needs --after SEQ", EXIT_USAGE)
    last = journal.last_seq(journal.read(repo.store, repo.changes)[0])
    if args.after is not None and args.after > last:
        raise ChantierError(
            f"watch: --after {args.after} is past the journal's end ({last})", EXIT_USAGE
        )
    return last
