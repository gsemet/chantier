"""The rows and head lines of `status`, shared by plain `status` and `status --since`: the
batch's head line, a CR's row, the journal's open conditions, the unpaused line. They read
only."""

from __future__ import annotations

from chantier.commands import wait_view
from chantier.commands.activity import stopped_text
from chantier.commands.batch_status_orders import ended_unrecorded
from chantier.commands.writer_line import entry as writer_entry
from chantier.core import leases
from chantier.core.clock import age_minutes
from chantier.core.endblockers import end_blockers
from chantier.core.records import BatchRecord, CrEntry, EventRecord, round_limit
from chantier.core.repo import Repo
from chantier.hub import journal
from chantier.rails import all_merged, held, spent_text, waits_all
from chantier.stack_words import state_word
from chantier.status.gate import gate_view
from chantier.status.words import phase_text, shape_word, steering_word


def age_text(d: BatchRecord) -> str:
    """How old the spend figure is: `12 min old`, `age unknown` for a record from before
    `spent_at`, and nothing while the spend is unknown."""
    if d.spent_usd is None:
        return ""
    age = age_minutes(d.spent_at)
    return "age unknown" if age is None else f"{age:.0f} min old"


def _heartbeat_text(d: BatchRecord, prev: str | None) -> str:
    hb = age_minutes(d.heartbeat)
    if d.heartbeat_stopped:
        return "stopped"
    if hb is None:
        return "never"
    text = f"{hb:.0f} min"
    since = age_minutes(prev) if prev else None
    if since is not None:  # a wake's own line: the gap since the wake before
        text += f" ({since - hb:.0f} min since the last)"
    return text


def _working_tail(repo: Repo, d: BatchRecord, c: CrEntry, stopped: set[str]) -> str:
    """What the status adds to a working CR's row about its Driver and its lease."""
    tail = ""
    if not c.agent:
        tail = " | no Driver recorded"
    elif c.agent in stopped:
        tail = f" | {stopped_text(c.agent)}"
    elif ended_unrecorded(repo, d, c.agent):
        tail = f" | Driver {c.agent} ended, no hand-back recorded"
    if late := leases.not_confirmed(repo, c.id, c.lease):
        tail += f" | {late}"
    return tail


def _cr_row(
    repo: Repo, d: BatchRecord, c: CrEntry, notes: bool, seen: tuple[list[EventRecord], set[str]]
) -> str:
    events, stopped = seen
    row = f"{c.id} {state_word(d, c, repo)} r{c.round}/{round_limit(d, c)} {c.shown_pr() or '-'}"
    row += f" | long gate {gate_view(repo, d, c, events)['text']}"
    if c.kind == "release":
        row += f" release{' ' + c.released if c.released else ''}"
        row += "".join(f" | draft {p}" for p in c.drafts[-2:])
    elif c.kind == "fix":
        row += f" fix for {c.fix_for}"
    if (text := phase_text(c)) is not None:
        row += f" | step: {text}"
    waits = waits_all(d.crs, c, d.mode) if c.status == "queued" else []
    if waits:
        row += f" | waits for {', '.join(waits)}"
    row += wait_view.status_segment(repo, c)
    if c.status == "working":
        row += _working_tail(repo, d, c, stopped)
    if c.status == "blocked" and c.blocked_reason:
        row += f" | blocked: {c.blocked_reason[:70]}"
    elif c.notes and (notes or c.status == "queued"):
        row += f" | {c.notes[-1][:60]}"
    usd = c.cost_usd
    return f"{row} | {'-' if usd is None else f'${usd:.2f}'}"


def _seen_lines(repo: Repo, d: BatchRecord) -> list[str]:
    """What the forge saw merged that the record does not hold (the hub's and the board's
    journal): one line per open CR of this batch, then the `batch.slots` change saved on the board
    and not yet ordered, for the Chief of Staff. Nothing is written; an unreadable line is named."""
    entries, bad, later, unknown = journal.read(repo.store, repo.changes)
    lines = [f"{journal.FILE}: line {n} unreadable" for n in bad]
    lines += [
        f"{journal.FILE}: line {n} is version {v}, newer than this chantier: update it"
        for n, v in later
    ]
    lines += [
        f"{journal.FILE}: line {n} is of type {t}, unknown to this chantier: update it"
        for n, t in unknown
    ]
    open_crs = {c.id for c in d.crs if c.status not in ("merged", "cancelled")}
    lines += journal.lines(entries, d.id, open_crs, d.orders, wait_view.open_keys(d))
    if repo.external:
        lines += journal.writer_lines(entries, writer_entry(repo))
    return lines


def _batch_line(d: BatchRecord, hb_text: str) -> str:
    queued = sum(1 for c in d.crs if c.status == "queued")
    return (
        f"{d.id} {d.status} steering {steering_word(d.steering)} "
        f"shape {shape_word(d.mode)} "
        f"live {len(held(d))}/{d.slots} queued {queued} "
        f"foreman {d.foreman or 'none'} e{d.foreman_epoch} "
        f"heartbeat {hb_text} spent {spent_text(d)}"
        + (f" of ${d.budget_usd:g}" if d.budget_usd else "")
        + (f", {age_text(d)}" if age_text(d) else "")
        + (" (paused, cost to date)" if d.status == "paused" else "")
        + (", no CR yet" if d.status == "paused" and not d.crs else "")
    )


def _unpaused_line(d: BatchRecord) -> list[str]:
    """A running batch whose CRs are all merged or cancelled: the automatic pause was blocked."""
    if d.status != "running" or not d.crs or not all_merged(d):
        return []
    causes = end_blockers(d)
    return [
        "every CR is merged or cancelled, not paused: "
        f"{'; '.join(causes) or 'nothing'}; `chantier pause --epoch <n>`"
    ]
