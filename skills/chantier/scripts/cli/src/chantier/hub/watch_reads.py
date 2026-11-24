"""What the watcher (`watch.py`) is told at its start (`Rules`) and reads of the planning folder:
its subscription, the seat, the open batch; and the pull path (`watch --once --after SEQ`), which
reads the journal and nothing else."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from chantier.core.errors import EXIT_USAGE, ChantierError
from chantier.core.files import rel_in
from chantier.core.records import read_batch_json
from chantier.core.repo import Repo
from chantier.core.seat import read_seat
from chantier.hub import arrival_mark, autostart, journal


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
