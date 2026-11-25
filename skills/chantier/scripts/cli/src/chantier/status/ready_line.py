"""The two lines `status` adds for the steering session: one `handed back:` line for each CR
handed back ready, and the `batch:` line with the batch's state. Both are read from the record,
the events and the host's view of the Drivers; the agent copies them and judges nothing."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from chantier.commands.batch_status_orders import ended_unrecorded
from chantier.core.records import BatchRecord, BatchSettings, CrEntry, EventRecord
from chantier.core.repo import Repo
from chantier.lifecycle.stages import cr_slug
from chantier.plugin_files import skill_dir
from chantier.rails import held, spent_text
from chantier.stack_words import PR_IN_DRAFT, draft_waits, ready_word
from chantier.status.gate import gate_view
from chantier.status.words import READY_ICON, shape_word, steering_word

OPEN_GATE = ("none", "queued", "running", "failed")
GAPS = re.compile(r"\bgaps: (.*)$", re.S)
GRANT = "; under the grant: the release/fix PR (steering session)"


def _steering(d: BatchRecord) -> str:
    return "the Chief of Staff" if d.steering == "direct" else "the Foreman"


def _driver_live(repo: Repo, d: BatchRecord, c: CrEntry, stopped: set[str]) -> bool:
    """The CR's Driver is shown live: an agent is recorded, the host reports it neither stopped
    nor ended. Copilot cannot read either, so no Driver is shown live there."""
    if not c.agent or d.host == "copilot" or c.agent in stopped:
        return False
    return not ended_unrecorded(repo, d, c.agent)


def _gaps(events: list[EventRecord], c: CrEntry) -> str:
    """The text after `gaps: ` of the CR's last `handback ready` note, unchanged."""
    found = [e for e in events if e.cr == c.id and e.kind == "handback" and e.result == "ready"]
    m = GAPS.search(str(found[-1].note or "")) if found else None
    return m[1].strip() if m else ""


def _result(g: dict[str, Any]) -> str:
    state = g["state"]
    if state == "passed":
        return "passed"
    if state == "carried":
        return f"passed (carried from {g['head']})"
    if state == "failed":
        return "failed"
    if state == "exempt":
        return f"exempt: {g['waiver']}"
    if state == "waived":
        return str(g["text"])
    return "not run" + {"queued": " (queued)", "running": " (running)"}.get(state, "")


def gate_owed(
    repo: Repo, d: BatchRecord, c: CrEntry, events: list[EventRecord], stopped: set[str]
) -> str | None:
    """`<who>` of a ready CR whose long gate at its head is open, else None."""
    if c.status != "ready" or not c.head:
        return None
    if gate_view(repo, d, c, events)["state"] not in OPEN_GATE:
        return None
    return "its Driver" if _driver_live(repo, d, c, stopped) else _steering(d)


def _owed(
    repo: Repo, d: BatchRecord, c: CrEntry, events: list[EventRecord], stopped: set[str]
) -> list[str]:
    owed = []
    if (who := gate_owed(repo, d, c, events, stopped)) and c.head:
        owed.append(f"its long gate passes at {c.head[:7]} ({who})")
    owed += [
        f"{o.id} {o.kind} is applied ({_steering(d)})"
        for o in d.orders
        if o.cr == c.id and not o.done and not o.applied
    ]
    return owed


def _line(
    repo: Repo, d: BatchRecord, c: CrEntry, events: list[EventRecord], stopped: set[str]
) -> str:
    word = ready_word(d, c, repo) or PR_IN_DRAFT
    name = f"{c.id} {cr_slug(Path(c.path or '').name)}".rstrip()
    line = f"handed back: {READY_ICON.get(word, '🟤')} {word} {name} {c.shown_pr() or 'no PR yet'}"
    if word == PR_IN_DRAFT:
        line += f" | do not merge: waits for {draft_waits(d, c, repo)}"
    if gaps := _gaps(events, c):
        line += f" | gaps: {gaps}"
    if owed := _owed(repo, d, c, events, stopped):
        line += f" | owed before the merge: {'; '.join(owed)}"
    if c.head:
        line += f" | long gate {c.id} at {c.head[:7]}: {_result(gate_view(repo, d, c, events))}"
    return line + " | `help merge`"


def ready_line(
    repo: Repo, d: BatchRecord, c: CrEntry, events: list[EventRecord], stopped: set[str]
) -> str:
    """The `handed back:` line of one CR handed back ready (`status --since`)."""
    return _line(repo, d, c, events, stopped)


def ready_lines(
    repo: Repo, d: BatchRecord, events: list[EventRecord], stopped: set[str]
) -> list[str]:
    """One `handed back:` line for each CR whose record status is `ready`, in the rows' order."""
    ready = sorted((c for c in d.crs if c.status == "ready"), key=lambda c: c.order)
    return [_line(repo, d, c, events, stopped) for c in ready]


def batch_line(repo: Repo, d: BatchRecord, events: list[EventRecord], stopped: set[str]) -> str:
    """The `batch:` line: the shape, the slots, who steers, the limits, the budget, who owes the
    long gate and who merges."""
    crs = sorted(d.crs, key=lambda c: c.order)
    own = ", ".join(f"{c.id} {c.rounds}" for c in crs if c.rounds)
    rounds = f"rounds {(d.settings or BatchSettings()).max_rounds}" + (f" ({own})" if own else "")
    spent = spent_text(d)
    budget = (
        f"budget {spent} of ${d.budget_usd:g}" if d.budget_usd else f"budget none (spent {spent})"
    )
    owes = [f"{c.id} ({w})" for c in crs if (w := gate_owed(repo, d, c, events, stopped))]
    grant = d.release
    under = GRANT if grant and (grant.autonomous > 0 or grant.fixes) else ""
    return (
        f"batch: shape {shape_word(d.mode)}; slots {len(held(d))}/{d.slots}; "
        f"steering {steering_word(d.steering)}; {rounds}; {budget}; "
        f"long gate owed: {', '.join(owes) or 'none'}; merges: the user{under}"
        f"; rules: {skill_dir().as_posix()}/references/reload-rules.md (reread after a compaction)"
    )
