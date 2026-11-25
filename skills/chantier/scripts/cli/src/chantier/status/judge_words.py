"""The steering session's ask to the user for a CR handed back, worded from the record and the
events alone (`chantier judge`): the readiness word, the PR, the draft's wait, the gate's
exemption or waiver, every gap, the local gate clause, the open waits and the owed items. It
reads no forge and no git and writes nothing; it drops no gap and no owed item."""

from __future__ import annotations

from pathlib import Path

from chantier.commands.crs import carry_at
from chantier.core.heads import gate_passed, same_head
from chantier.core.records import BatchRecord, CrEntry, EventRecord
from chantier.core.repo import Repo
from chantier.core.waits import open_counted, what
from chantier.lifecycle.stages import cr_slug
from chantier.stack_shape import shape_blockers
from chantier.stack_words import PR_IN_DRAFT, draft_waits, pr_base_of, ready_word
from chantier.stacks import chain
from chantier.status.gate import gate_view
from chantier.status.ready_line import gaps, owed


def word_of(repo: Repo, d: BatchRecord, c: CrEntry) -> str:
    """The readiness word of an ask: the first word `readiness_key` knows."""
    return (ready_word(d, c, repo) or PR_IN_DRAFT).replace(" ", "-").lower()


def flat_gaps(events: list[EventRecord], c: CrEntry) -> str:
    """The CR's gaps, each run of whitespace one space; nothing else changes."""
    return " ".join(gaps(events, c).split())


def local_gate_clause(c: CrEntry, events: list[EventRecord]) -> str:
    """`local gate <cr> at <sha7>: passed|failed|not run`: the CR's own gate events at its head,
    apart from any waiver or exemption (a waiver does not waive a local run)."""
    if not c.head:
        return f"local gate {c.id}: not run (no head recorded)"
    mine = [e for e in events if e.cr == c.id]
    handed = [e for e in mine if e.kind == "handback" and e.result == "ready"]
    clause = f"local gate {c.id} at {c.head[:7]}: "
    if gate_passed(mine, c.head):
        return clause + "passed"
    carried = carry_at(mine, c.head, "gate_from") or (handed[-1] if handed else None)
    if carried is not None and carried.gate_from:
        return clause + f"passed (carried from {str(carried.gate_from)[:7]})"
    if any(e.kind == "gate" and same_head(e.head, c.head) for e in mine):
        return clause + "failed"
    return clause + "not run"


def stack_open(d: BatchRecord, c: CrEntry) -> list[CrEntry]:
    """The CRs that make `c`'s ready ask a stack matter (`asks` refuses it per CR), else []."""
    if d.mode != "stack" or c.id not in [x.id for x in chain(d)]:
        return []
    return shape_blockers(d, c.id)


def stack_pairs(d: BatchRecord, events: list[EventRecord]) -> str:
    """`<cr>=<link>[ gaps: <gaps>] …` for each ready CR of the chain with a PR, in chain order."""
    out = []
    for x in chain(d):
        if x.status != "ready" or not x.pr:
            continue
        found = flat_gaps(events, x)
        out.append(f"{x.id}={x.shown_pr()}" + (f" gaps: {found}" if found else ""))
    return " ".join(out)


def _gate_part(repo: Repo, d: BatchRecord, c: CrEntry, events: list[EventRecord]) -> str:
    g = gate_view(repo, d, c, events)
    if g["state"] == "exempt":
        return f"no long gate: {g['waiver']}"
    if g["state"] != "waived":
        return ""
    if g["validated_by"]:
        return f"long gate waived: validated by {g['validated_by']['cr']}"
    if g["follow_up"]:
        return f"long gate waived: follow-up {g['follow_up']}"
    return "long gate waived"


def ask_text(  # noqa: PLR0913, PLR0917 - the record, the events and the host's view
    repo: Repo,
    d: BatchRecord,
    c: CrEntry,
    events: list[EventRecord],
    stopped: set[str],
    local_gate: bool,
) -> str | None:
    """The one-line ask for a CR handed back ready; None for a blocked hand-back and for a CR of
    a stack that is not alone (the stack's ask goes up with the stack's)."""
    if c.status != "ready" or stack_open(d, c):
        return None
    word = word_of(repo, d, c)
    parts = [word, f"{c.id} {cr_slug(Path(c.path or '').name)}".rstrip(), c.shown_pr() or ""]
    if word == "pr-in-draft":
        parts.append(f"on {pr_base_of(d, c, repo)}: waits for {draft_waits(d, c, repo)}")
    parts.append(_gate_part(repo, d, c, events))
    if found := flat_gaps(events, c):
        parts.append(f"gaps: {found}")
    if local_gate:
        parts.append(local_gate_clause(c, events))
    if waits := open_counted(c):
        merge = "do not merge: " if any(w["type"] == "merge" for w in waits) else ""
        parts.append(f"{merge}open waits: {'; '.join(what(w) for w in waits)}")
    if items := owed(repo, d, c, events, stopped):
        parts.append(f"owed before the merge: {'; '.join(items)}")
    return " ".join(p for p in parts if p)
