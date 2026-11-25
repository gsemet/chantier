"""`status --since <seq>`: only what changed in the batch since an event sequence (the 1-based
line number of the batch's `events.jsonl`), merged and cancelled CRs as counts, and the sequence
to pass next time. Each row reads as in plain `status`; it records nothing (no arrival line, so
the told mark stays for plain `status` and the watcher)."""

from __future__ import annotations

from chantier.commands.batch_status_orders import order_lines
from chantier.commands.batch_status_rows import (
    _batch_line,
    _cr_row,
    _heartbeat_text,
    _seen_lines,
    _unpaused_line,
)
from chantier.core.errors import EXIT_USAGE, ChantierError
from chantier.core.records import BatchRecord, EventRecord
from chantier.core.repo import Repo
from chantier.hub.autostart import not_running_line
from chantier.hub.lines import watch_lines
from chantier.status.ready_line import batch_line, ready_line
from chantier.status.state_line import state_line

Numbered = tuple[list[tuple[int, EventRecord]], int]  # the events by line number, the last line
# the kinds with no CR that do not change the batch's head lines
QUIET = {
    "heartbeat",
    "heartbeat_stopped",
    "cost",
    "order",
    "order-done",
    "ask",
    "asks-read",
    "agent",
}


def check_since(since: int, batch: str, last: int) -> None:
    """The refusals of `--since`, before anything is printed or recorded."""
    if since < 0:
        raise ChantierError(
            f"status --since {since}: a sequence is 0 or more; `status --since 0` lists everything",
            EXIT_USAGE,
        )
    if since > last:
        raise ChantierError(
            f"status --since {since}: {batch}'s events stop at {last}; pass the sequence a "
            "`status --since` printed, or `status --since 0`",
            EXIT_USAGE,
        )


def _counts(d: BatchRecord, status: str, changed: set[str], since: int) -> str:
    total = [c.id for c in d.crs if c.status == status]
    return f"{status}: {len(total)} ({sum(1 for i in total if i in changed)} since {since})"


def since_lines(  # noqa: PLR0913, PLR0917 - the record, its events numbered, the sequence and the flags
    repo: Repo,
    d: BatchRecord,
    events: list[EventRecord],
    numbered: Numbered,
    since: int,
    notes: bool,
    stopped: set[str],
    *,
    extra: list[str] | None = None,
    prev: str | None = None,
) -> list[str]:
    """The `status --since` output, in its ten items' order; `extra` is the lines of `--refresh`
    or `--stop-heartbeat`, `prev` the heartbeat a wake overwrote."""
    numbers, last = numbered
    after = [e for n, e in numbers if n > since]
    crs = {e.cr for e in after if e.cr}
    orders = {str(e.order) for e in after if e.order}
    lines = [state_line(repo, d, events)]
    changes: list[str] = []
    if any(e.cr is None and e.kind not in QUIET for e in after):
        changes += [_batch_line(d, _heartbeat_text(d, prev)), batch_line(repo, d, events, stopped)]
    rows = sorted((c for c in d.crs if c.id in crs), key=lambda c: c.order)
    changes += [
        _cr_row(repo, d, c, notes, (events, stopped))
        for c in rows
        if c.status not in ("merged", "cancelled")
    ]
    changes += [ready_line(repo, d, c, events, stopped) for c in rows if c.status == "ready"]
    kept = [o for o in d.orders if o.id in orders and not o.done]
    changes += order_lines(d.model_copy(update={"orders": kept}), repo)
    lines += changes
    lines.append(_counts(d, "merged", crs, since))
    if any(c.status == "cancelled" for c in d.crs):
        lines.append(_counts(d, "cancelled", crs, since))
    if not changes:
        lines.append(f"no change since {since}")
    lines += _unpaused_line(d)
    lines += watch_lines(repo, d)
    lines += _seen_lines(repo, d)
    if unread := sum(1 for a in d.asks if not a.read):
        lines.append(f"{unread} asks unread: `chantier asks`")
    lines += not_running_line(repo)
    lines += extra or []
    lines.append(f"since {since}, now {last}: next time `status --since {last}`")
    return lines
