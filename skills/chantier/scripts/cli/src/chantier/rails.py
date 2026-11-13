"""The refusals: what a command checks before it changes the record."""

from __future__ import annotations

import contextlib
import hashlib
from pathlib import Path

from chantier.core.batch import Batch
from chantier.core.errors import EXIT_BUDGET, EXIT_PRECONDITION, ChantierError
from chantier.core.git import git
from chantier.core.records import LIVE, chief_sessions, round_limit
from chantier.core.repo import Repo
from chantier.costs.sessions import idle_seconds

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


QUIET_SECONDS = 300  # a session record written more recently than this: something still runs


def running(repo: Repo, d: dict) -> list[str]:
    """What shows a batch still runs, from its record and from its sessions' files; empty when
    nothing does. A long tool call writes nothing, so the recorded state is the first proof and
    the files only the second. The Foreman's session tree is all the CLI knows: a Driver run
    from another session of the user's is not in it. The Chief of Staff's own session is not
    counted: it is the one that closes, and on a direct batch it is also the steering session,
    so its own file is skipped and its subagents (the Drivers) are checked."""
    causes = [
        f"{c['id']} is {c['status']}, not merged or cancelled"
        for c in d["crs"]
        if c["status"] not in ENDED
    ]
    causes += [
        f"order {o['id']} ({o['kind']}) is open" for o in d.get("orders", []) if not o["done"]
    ]
    if d.get("stack_agent"):
        causes.append(f"stack agent {d['stack_agent']} is recorded")
    sessions = [s for s in (d.get("foreman_transcripts") or [d.get("foreman_transcript")]) if s]
    for label, age in idle_seconds(repo.session_root, d["host"], sessions, chief_sessions(d)):
        if age is None:
            causes.append(f"{label}: not measured")
        elif age < QUIET_SECONDS:
            causes.append(f"{label} was written {age:.0f} s ago (under {QUIET_SECONDS // 60} min)")
    return causes


def check_idle(repo: Repo, d: dict) -> None:
    causes = running(repo, d)
    if causes:
        raise ChantierError(
            f"cannot close {d['id']}, something still runs: "
            + "; ".join(causes)
            + ". Nothing was deleted.",
            EXIT_PRECONDITION,
        )


def live(b: Batch) -> list[dict]:
    return [c for c in b.data["crs"] if c["status"] in LIVE]


def qa_open(b: Batch) -> list[dict]:
    """The QA orders not done: each is a QA driver, and holds a slot from the order on."""
    return [o for o in b.data.get("orders", []) if o["kind"] == "qa" and not o["done"]]


def held(b: Batch) -> list[str]:
    """What holds a slot: a CR in `working` and an open QA order, never a ready or blocked CR."""
    return [x["id"] + " working" for x in live(b)] + [f"{o['id']} qa" for o in qa_open(b)]


def slot_free(b) -> bool:
    """A slot is free by the rule `take` applies. `b` is a Batch or anything with a `.data`."""
    return len(held(b)) < b.data["slots"]


def check_slot(b: Batch, what: str) -> None:
    if not slot_free(b):
        raise ChantierError(
            f"no free slot for {what}: {len(held(b))} of {b.data['slots']} held "
            f"({', '.join(held(b)) or 'slots 0'})"
        )


def is_release(c: dict) -> bool:
    return c.get("kind") == "release"


def alone(crs: list[dict], c: dict) -> bool:
    """A release alone in its batch: no other CR but fixes was ever in it, whatever its state."""
    return not any(x["id"] != c["id"] and x.get("kind") != "fix" for x in crs)


def series_predecessor(crs: list[dict], c: dict) -> dict | None:
    """In a series, the nearest CR before `c` in the order that is neither a release nor a fix
    CR and not cancelled; a merged one counts, it is met."""
    if c.get("kind") in {"release", "fix"}:
        return None
    before = [
        x
        for x in crs
        if x["order"] < c["order"]
        and x.get("kind") not in {"release", "fix"}
        and x["status"] != "cancelled"
    ]
    return max(before, key=lambda x: x["order"], default=None)


def waits_for(crs: list[dict], c: dict, mode: str = "parallel") -> list[str]:
    """The CRs not yet met: those of `after`, then, in a series, the predecessor. For a CR, met
    is ready or merged (a cancelled one stays unmet); for a release, ready, merged or cancelled
    in an ordered batch (stack or series: it is prepared on top of the others), merged or
    cancelled in a parallel one (no branch holds all the work until the others are merged)."""
    found = {x["id"]: x for x in crs}
    if is_release(c):
        met = ENDED | {"ready"} if mode in {"stack", "series"} else ENDED
    else:
        met = {"ready", "merged"}
    ids = list(c.get("after", []))
    pred = series_predecessor(crs, c) if mode == "series" else None
    if pred and pred["id"] not in ids:
        ids.append(pred["id"])
    return [
        f"{i} {found[i]['status']}" for i in ids if i in found and found[i]["status"] not in met
    ]


def waits_all(crs: list[dict], c: dict, mode: str = "parallel") -> list[str]:
    """What a queued CR waits for, as `status` shows it: its `after`, then a release's fixes
    not ended."""
    status = {x["id"]: x["status"] for x in crs}
    return waits_for(crs, c, mode) + [f"{i} {status[i]}" for i in pending_fixes(crs, c)]


def unmet(b: Batch, c: dict) -> list[str]:
    return waits_for(b.data["crs"], c, b.data["mode"])


def over_budget(b: Batch) -> bool:
    budget = b.data.get("budget_usd")
    return (
        bool(budget) and (b.data.get("spent_usd") or 0) >= budget
    )  # the priced part; no spend seen yet: 0


def spent_text(data: dict) -> str:
    """The spend as shown to a reader: `unknown` until a priced refresh, never a false $0.00, and
    `at least` while calls of a model with no price are left out of it."""
    spent = data.get("spent_usd")
    if spent is None:
        return "unknown"
    return f"{'at least ' if data.get('unpriced') else ''}${spent:.2f}"


def usd_text(amount: float, unpriced: dict | None, places: int = 2) -> str:
    """A priced amount; `at least` while calls of a model with no price are left out of it."""
    return f"{'at least ' if unpriced else ''}${amount:.{places}f}"


def not_priced(unpriced: dict) -> str:
    """`3 calls of <model> not priced`, one `N calls of <model>` per model."""
    return ", ".join(f"{n} calls of {m}" for m, n in unpriced.items()) + " not priced"


def all_merged(b: Batch) -> bool:
    return all(c["status"] in ENDED for c in b.data["crs"])


def check_budget(b: Batch) -> None:
    """No Driver of any kind starts, and no Driver starts a new round, past the budget; the spend
    is the last recorded one. The gate, the verdict, the ship, the notes and the hand-back stay
    open, and so do the workers of a round already started."""
    if over_budget(b):
        raise ChantierError(
            f"budget spent: {spent_text(b.data)} of "
            f"${b.data['budget_usd']}; only the user raises it (`order budget`)",
            EXIT_BUDGET,
        )


def pending_fixes(crs: list[dict], c: dict) -> list[str]:
    """The fix CRs of a release that have not ended: the release waits for them."""
    return [x["id"] for x in crs if x.get("fix_for") == c["id"] and x["status"] not in ENDED]


def check_take(b: Batch, c: dict, note: str | None) -> None:
    """A Driver starts only in a free slot, within the budget, on a CR with no agent recorded. It
    takes a queued CR, resumes a working one (`--note`: a restart keeps the slot and counts no
    round), or takes a ready or blocked one when the Foreman says why (`--note`): an answer,
    a change, a merged fix, a rebase, a red check."""
    if c["status"] not in {"queued", "working", "ready", "blocked"}:
        raise ChantierError(f"{c['id']} is {c['status']}: nothing for a Driver to do")
    if c["status"] in {"ready", "blocked"} and not note:
        raise ChantierError(
            f"{c['id']} is {c['status']}: a Driver takes it back only with "
            "`--note` saying why (an answer, a change, a rebase, a red check)"
        )
    if c["status"] == "working" and not note:
        raise ChantierError(
            f"{c['id']} is working: a new Driver resumes it only with `--note` "
            "saying why (resume: <cause>)"
        )
    if c.get("agent"):  # one Driver per CR: the recorded one must have ended first
        raise ChantierError(
            f"{c['id']} still has an agent recorded ({c['agent']}): "
            f"`agents set {c['id']} -` first, once it ended"
        )
    check_budget(b)
    if c["status"] != "working":
        check_slot(b, c["id"])
    # a release taken back (ready, blocked) waits again for the stack under it, e.g. after a
    # change of content
    if unmet(b, c) and (
        c["status"] == "queued" or (is_release(c) and c["status"] in {"ready", "blocked"})
    ):
        ordered = b.data["mode"] in {"stack", "series"}
        ends = (
            ("ready or merged" if ordered else "merged or cancelled")
            if is_release(c)
            else "ready or merged"
        )
        raise ChantierError(
            f"{c['id']} waits for {', '.join(unmet(b, c))}: it starts once each is {ends}"
        )
    if is_release(c):
        fixes = pending_fixes(b.data["crs"], c)
        if fixes:
            raise ChantierError(
                f"{c['id']} waits for {', '.join(fixes)}: a fix of the release "
                "must be merged or cancelled first"
            )


def check_round(b: Batch, c: dict) -> int:
    """A round is counted before its Coder starts; past the budget, or past the limit, only the
    user grants more. The budget is checked first: when both are spent, more rounds alone would
    not let the Driver go on."""
    check_budget(b)
    limit = round_limit(b.data, c)
    if c.get("round", 0) >= limit:
        raise ChantierError(
            f"{c['id']}: round limit {limit} reached; hand back blocked, only the "
            "user grants more (`order rounds`)",
            EXIT_BUDGET,
        )
    return limit


def worktree_print(wt: Path | None) -> dict:
    """The worktree's head and a fingerprint of its uncommitted and untracked content, by read-only
    git commands and file reads. Empty when the worktree is not there."""
    if wt is None or not wt.is_dir():
        return {}
    head = git("rev-parse", "HEAD", cwd=wt, check=False)
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


def check_stray_round(events: list[dict], c: dict, now_print: dict) -> None:
    """A round on which nothing happened is refused (exit 2): the CR has a round, no event but a
    round was logged since the last one, and the worktree is the same as when it was counted."""
    last = next(
        (i for i in range(len(events) - 1, -1, -1) if events[i].get("kind") == "round"), None
    )
    if not c.get("round", 0) or last is None:
        return
    if any(e.get("kind") != "round" for e in events[last + 1 :]):
        return
    before = {k: events[last].get(k) for k in ("wt_head", "wt_state")}
    if before["wt_head"] and now_print and before != {k: now_print.get(k) for k in before}:
        return
    raise ChantierError(
        f"{c['id']}: round {c['round']} was counted and nothing happened since (no note, the "
        f"worktree unchanged): start that round's coder; to read the facts, `handoff {c['id']}`; "
        "if a new round is really needed, note why first",
        EXIT_PRECONDITION,
    )
