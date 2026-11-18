"""The refusals: what a command checks before it changes the record."""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from chantier.core.errors import EXIT_BUDGET, EXIT_PRECONDITION, ChantierError
from chantier.core.git import git
from chantier.core.records import (
    LIVE,
    BatchRecord,
    CrEntry,
    EventRecord,
    OrderRecord,
    chief_sessions,
    round_limit,
)
from chantier.core.repo import Repo

if TYPE_CHECKING:
    from chantier.costs.sessions import Ending

ENDED = {"merged", "cancelled"}


def check_no_open_batch(repo: Repo) -> None:
    """One batch at a time, running or paused until `close`: new work joins it by `order add`."""
    ids = repo.batch_ids()
    if ids:
        raise ChantierError(
            f"{ids[0]} is not closed (a paused batch stays until `close`): "
            "`order add` joins new work to it",
            EXIT_PRECONDITION,
        )


COPILOT_QUIET_SECONDS = 300  # a Copilot session file written more recently: something still runs

STOPPED_HINT = (
    "an agent stopped without its hand-back (an app restart, the user's stop) passes only on the "
    "user's word: close --stopped <name> for each"
)


def held_agents(d: BatchRecord) -> dict[str, str]:
    """The agents the batch's record holds: recorded id -> the owner's label (a CR's slug
    or an order's id), for each CR's and each QA order's `agent` that `agents set` wrote and no
    `agents set <x> -` cleared. The recorded stack agent is not here: it is a record cause."""
    held = {c.agent: c.id for c in d.crs if c.agent}
    held.update({o.agent: o.id for o in d.orders if o.agent})
    return held


def running(repo: Repo, d: BatchRecord) -> tuple[list[str], list[Ending], list[Ending]]:
    """What shows a batch still runs: (the causes no flag passes, the state of each held agent's
    Claude transcript, the state of every other transcript). The causes come from the record (a CR
    not merged or cancelled, an open order, a recorded stack agent) and, on Copilot, from the
    session file (written in the last 5 minutes, or not measured). On Claude each transcript is
    read at its end, never by the file's age: an agent that handed back has ended, one that waits
    on a tool call or has a step under way runs, one whose file is missing or cut cannot be read.
    Only the agents the batch holds can block: the current Foreman (the last claim's session main
    transcript) and each id `agents set` recorded and did not clear, a held id with no transcript
    under the steering sessions being one that cannot be read. The other transcripts (other
    subagents, a held Driver's own, the replaced Foremans' main ones) are returned apart, never a
    cause. The Foreman's session tree is all the CLI knows: a Driver run from another session of
    the user's is not in it. The Chief of Staff's own session is not counted (its subagents are)."""
    causes = [
        f"{c.id} is {c.status}, not merged or cancelled" for c in d.crs if c.status not in ENDED
    ]
    causes += [f"order {o.id} ({o.kind}) is open" for o in d.orders if not o.done]
    if d.stack_agent:
        causes.append(f"stack agent {d.stack_agent} is recorded")
    from chantier.costs.endings import transcript_endings  # noqa: PLC0415 - slow
    from chantier.costs.sessions import idle_seconds  # noqa: PLC0415 - slow

    sessions = d.foreman_transcripts or ([d.foreman_transcript] if d.foreman_transcript else [])
    if d.host == "copilot":
        for label, age in idle_seconds(repo.session_root, d.host, sessions, chief_sessions(d)):
            if age is None:
                causes.append(f"{label}: not measured")
            elif age < COPILOT_QUIET_SECONDS:
                causes.append(
                    f"{label} was written {age:.0f} s ago (under {COPILOT_QUIET_SECONDS // 60} min)"
                )
        return causes, [], []
    stack = {d.stack_agent} if d.stack_agent else set()
    sessions = sorted(sessions, key=lambda s: [s] == [c.transcript for c in d.foreman_claims[-1:]])
    mine, others = transcript_endings(
        repo.session_root, sessions, chief_sessions(d), held_agents(d), stack
    )
    return causes, mine, others


def _declared(
    d: BatchRecord, endings: list[Ending], others: list[Ending], stopped: list[str]
) -> list[Ending]:
    """The held agents' transcripts the user's `--stopped` names, each one that reads as running;
    a name that matches none, an ended one or one that cannot be read is refused, as is a name of
    another transcript (a subagent the batch does not hold, a replaced Foreman) and of the
    recorded stack agent, which no flag passes (exit 2)."""
    chosen: list[Ending] = []
    for name in stopped:
        if d.stack_agent and d.stack_agent in {name, f"agent-{name}", name.removeprefix("agent-")}:
            raise ChantierError(
                f"close --stopped {name}: the stack agent is a record cause no flag passes; "
                "clear it: agents set stack - --epoch <n>. Nothing was deleted.",
                EXIT_PRECONDITION,
            )
        if any(name in {e.name, e.name.removeprefix("agent-")} for e in others) and not any(
            name in {e.name, e.name.removeprefix("agent-")} for e in endings
        ):
            raise ChantierError(
                f"close --stopped {name}: not an agent {d.id} holds; it does not block close, "
                "drop the flag. Nothing was deleted.",
                EXIT_PRECONDITION,
            )
        match = next((e for e in endings if name in {e.name, e.name.removeprefix("agent-")}), None)
        if match is None:
            names = [e.name for e in endings if e.state == "running"]
            raise ChantierError(
                f"close --stopped {name}: no transcript of {d.id} by that name; still running: "
                f"{', '.join(names) or 'none'}. Nothing was deleted.",
                EXIT_PRECONDITION,
            )
        if match.state == "ended":
            raise ChantierError(
                f"close --stopped {name}: its transcript shows it ended; drop the flag. "
                "Nothing was deleted.",
                EXIT_PRECONDITION,
            )
        if match.state == "unreadable":
            where = "no transcript found" if match.missing else str(match.path)
            raise ChantierError(
                f"close --stopped {name}: its transcript cannot be read ({where}), and the "
                "flag covers only an agent that reads as running. Nothing was deleted.",
                EXIT_PRECONDITION,
            )
        if match not in chosen:
            chosen.append(match)
    return chosen


def check_idle(
    repo: Repo, d: BatchRecord, stopped: list[str] | None = None
) -> tuple[list[Ending], list[Ending]]:
    """Refuse (exit 2) while anything the batch holds runs, with the causes and the files, and
    return (the agents the user declared stopped, the other transcripts that run or cannot be
    read, listed apart and never a cause). The rule: the transcript of a held agent (the current
    Foreman, each id `agents set` recorded and did not clear) that shows it still runs, or that
    cannot be read (a held id with no transcript included), refuses, whatever the file's age.
    `stopped` (`close --stopped`, on the user's word only): the names of held agents that read as
    running but ended with no hand-back; each drops out of the causes. Every other cause still
    refuses, and a name that is not a running held agent is refused."""
    causes, endings, others = running(repo, d)
    declared = _declared(d, endings, others, stopped or [])
    causes += [e.text() for e in endings if e.state != "ended" and e not in declared]
    if causes:
        hint = (
            f" {STOPPED_HINT}."
            if any(e.state == "running" and e not in declared for e in endings)
            else ""
        )
        raise ChantierError(
            f"cannot close {d.id}, something still runs: "
            + "; ".join(causes)
            + f". Nothing was deleted.{hint}",
            EXIT_PRECONDITION,
        )
    return declared, [e for e in others if e.state != "ended"]


def live(d: BatchRecord) -> list[CrEntry]:
    return [c for c in d.crs if c.status in LIVE]


def qa_open(d: BatchRecord) -> list[OrderRecord]:
    """The QA orders not done: each is a QA driver, and holds a slot from the order on."""
    return [o for o in d.orders if o.kind == "qa" and not o.done]


def held(d: BatchRecord) -> list[str]:
    """What holds a slot: a CR in `working` and an open QA order, never a ready or blocked CR."""
    return [x.id + " working" for x in live(d)] + [f"{o.id} qa" for o in qa_open(d)]


def slot_free(d: BatchRecord) -> bool:
    """A slot is free by the rule `take` applies."""
    return len(held(d)) < d.slots


def check_slot(d: BatchRecord, what: str) -> None:
    if not slot_free(d):
        raise ChantierError(
            f"no free slot for {what}: {len(held(d))} of {d.slots} held "
            f"({', '.join(held(d)) or 'slots 0'})"
        )


def is_release(c: CrEntry) -> bool:
    return c.kind == "release"


def alone(crs: list[CrEntry], c: CrEntry) -> bool:
    """A release alone in its batch: no other CR but fixes was ever in it, whatever its state."""
    return not any(x.id != c.id and x.kind != "fix" for x in crs)


def series_predecessor(crs: list[CrEntry], c: CrEntry) -> CrEntry | None:
    """In a series, the nearest CR before `c` in the order that is neither a release nor a fix
    CR and not cancelled; a merged one counts, it is met."""
    if c.kind in {"release", "fix"}:
        return None
    before = [
        x
        for x in crs
        if x.order < c.order and x.kind not in {"release", "fix"} and x.status != "cancelled"
    ]
    return max(before, key=lambda x: x.order, default=None)


def waits_for(crs: list[CrEntry], c: CrEntry, mode: str | None = "parallel") -> list[str]:
    """The CRs not yet met: those of `after`, then, in a series, the predecessor. For a CR, met
    is ready or merged (a cancelled one stays unmet); for a release, ready, merged or cancelled
    in an ordered batch (stack or series: it is prepared on top of the others), merged or
    cancelled in a parallel one (no branch holds all the work until the others are merged)."""
    found = {x.id: x for x in crs}
    if is_release(c):
        met = ENDED | {"ready"} if mode in {"stack", "series"} else ENDED
    else:
        met = {"ready", "merged"}
    ids = list(c.after)
    pred = series_predecessor(crs, c) if mode == "series" else None
    if pred and pred.id not in ids:
        ids.append(pred.id)
    return [f"{i} {found[i].status}" for i in ids if i in found and found[i].status not in met]


def waits_all(crs: list[CrEntry], c: CrEntry, mode: str | None = "parallel") -> list[str]:
    """What a queued CR waits for, as `status` shows it: its `after`, then a release's fixes
    not ended."""
    status = {x.id: x.status for x in crs}
    return waits_for(crs, c, mode) + [f"{i} {status[i]}" for i in pending_fixes(crs, c)]


def unmet(d: BatchRecord, c: CrEntry) -> list[str]:
    return waits_for(d.crs, c, d.mode)


def over_budget(d: BatchRecord) -> bool:
    budget = d.budget_usd
    if not budget:
        return False
    return (d.spent_usd or 0) >= budget  # the priced part; no spend seen yet: 0


def spent_text(d: BatchRecord) -> str:
    """The spend as shown to a reader: `unknown` until a priced refresh, never a false $0.00, and
    `at least` while calls of a model with no price are left out of it."""
    spent = d.spent_usd
    if spent is None:
        return "unknown"
    return f"{'at least ' if d.unpriced else ''}${spent:.2f}"


def usd_text(amount: float, unpriced: dict[str, Any] | None, places: int = 2) -> str:
    """A priced amount; `at least` while calls of a model with no price are left out of it."""
    return f"{'at least ' if unpriced else ''}${amount:.{places}f}"


def not_priced(unpriced: dict[str, Any]) -> str:
    """`3 calls of <model> not priced`, one `N calls of <model>` per model."""
    return ", ".join(f"{n} calls of {m}" for m, n in unpriced.items()) + " not priced"


def all_merged(d: BatchRecord) -> bool:
    return all(c.status in ENDED for c in d.crs)


def check_budget(d: BatchRecord) -> None:
    """No Driver of any kind starts, and no Driver starts a new round, past the budget; the spend
    is the one the caller refreshed from the transcripts just before (`refresh_for_check`), or
    the last recorded one when they cannot be read. The gate, the verdict, the ship, the notes
    and the hand-back stay open, and so do the workers of a round already started."""
    if over_budget(d):
        raise ChantierError(
            f"budget spent: {spent_text(d)} of "
            f"${d.budget_usd}; only the user raises it (`order budget`)",
            EXIT_BUDGET,
        )


def pending_fixes(crs: list[CrEntry], c: CrEntry) -> list[str]:
    """The fix CRs of a release that have not ended: the release waits for them."""
    return [x.id for x in crs if x.fix_for == c.id and x.status not in ENDED]


def check_take(d: BatchRecord, c: CrEntry, note: str | None) -> None:
    """A Driver starts only in a free slot, within the budget, on a CR with no agent recorded. It
    takes a queued CR, resumes a working one (`--note`: a restart keeps the slot and counts no
    round), or takes a ready or blocked one when the Foreman says why (`--note`): an answer,
    a change, a merged fix, a rebase, a red check."""
    if c.status not in {"queued", "working", "ready", "blocked"}:
        raise ChantierError(f"{c.id} is {c.status}: nothing for a Driver to do")
    if c.status in {"ready", "blocked"} and not note:
        raise ChantierError(
            f"{c.id} is {c.status}: a Driver takes it back only with "
            "`--note` saying why (an answer, a change, a rebase, a red check)"
        )
    if c.status == "working" and not note:
        raise ChantierError(
            f"{c.id} is working: a new Driver resumes it only with `--note` "
            "saying why (resume: <cause>)"
        )
    if c.agent:  # one Driver per CR: the recorded one must have ended first
        raise ChantierError(
            f"{c.id} still has an agent recorded ({c.agent}): "
            f"`agents set {c.id} - --epoch <n>` first, once it ended"
        )
    check_budget(d)
    if c.status != "working":
        check_slot(d, c.id)
    # a release taken back (ready, blocked) waits again for the stack under it, e.g. after a
    # change of content
    if unmet(d, c) and (
        c.status == "queued" or (is_release(c) and c.status in {"ready", "blocked"})
    ):
        ordered = d.mode in {"stack", "series"}
        ends = (
            ("handed back ready or merged" if ordered else "merged or cancelled")
            if is_release(c)
            else "handed back ready or merged"
        )
        raise ChantierError(
            f"{c.id} waits for {', '.join(unmet(d, c))}: it starts once each is {ends}"
        )
    if is_release(c):
        fixes = pending_fixes(d.crs, c)
        if fixes:
            raise ChantierError(
                f"{c.id} waits for {', '.join(fixes)}: a fix of the release "
                "must be merged or cancelled first"
            )


def check_round(d: BatchRecord, c: CrEntry) -> int:
    """A round is counted before its Coder starts; past the budget, or past the limit, only the
    user grants more. The budget is checked first: when both are spent, more rounds alone would
    not let the Driver go on."""
    check_budget(d)
    limit = round_limit(d, c)
    if c.round >= limit:
        raise ChantierError(
            f"{c.id}: round limit {limit} reached; hand back blocked, only the "
            "user grants more (`order rounds`)",
            EXIT_BUDGET,
        )
    return limit


def worktree_print(wt: Path | None) -> dict[str, Any]:
    """The worktree's head and a fingerprint of its uncommitted and untracked content, by read-only
    git commands and file reads. Empty when the worktree is not there."""
    if wt is None or not wt.is_dir():
        return {}
    head = git("rev-parse", "HEAD", cwd=wt, check=False)
    import hashlib  # noqa: PLC0415 - slow import

    h = hashlib.sha1()
    h.update(git("status", "--porcelain", "--untracked-files=normal", cwd=wt, check=False).encode())
    h.update(git("diff", "HEAD", cwd=wt, check=False).encode())
    for name in sorted(
        git("ls-files", "--others", "--exclude-standard", "-z", cwd=wt, check=False).split("\0")
    ):
        if not name:
            continue
        h.update(name.encode())
        with contextlib.suppress(OSError):
            h.update((wt / name).read_bytes())
    return {"wt_head": head, "wt_state": h.hexdigest()[:16]}


def check_stray_round(events: list[EventRecord], c: CrEntry, now_print: dict[str, Any]) -> None:
    """A round on which nothing happened is refused (exit 2): the CR has a round, no event but a
    round was logged since the last one, and the worktree is the same as when it was counted."""
    last = next((i for i in range(len(events) - 1, -1, -1) if events[i].kind == "round"), None)
    if not c.round or last is None:
        return
    if any(e.kind != "round" for e in events[last + 1 :]):
        return
    before = {k: getattr(events[last], k) for k in ("wt_head", "wt_state")}
    if before["wt_head"] and now_print and before != {k: now_print.get(k) for k in before}:
        return
    raise ChantierError(
        f"{c.id}: round {c.round} was counted and nothing happened since (no note, the "
        f"worktree unchanged): start that round's coder; to read the facts, `handoff {c.id}`; "
        "if a new round is really needed, note why first",
        EXIT_PRECONDITION,
    )
