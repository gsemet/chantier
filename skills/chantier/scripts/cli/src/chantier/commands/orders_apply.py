"""What each kind of `chantier order` does to the record: one small function per kind."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from chantier.commands.crs import filed_fix, grant_line
from chantier.commands.gate_run import stop_gate
from chantier.commands.gate_slots import slot_of
from chantier.commands.opening import add_cr, check_cycles, declare_dependencies
from chantier.commands.orders_release import (
    add_release,
    check_release_open,
    join_release,
    refused,
    release_cr,
)
from chantier.core.batch import Batch
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.records import LIVE, CrEntry, read_events
from chantier.lifecycle.stages import trash_cr
from chantier.rails import ENDED, is_release
from chantier.rails_release import (
    check_grant,
    check_granted_fix,
    merge_done,
    parse_grant,
    release_merged,
)

CR_ORDERS = {"after", "drop", "merged", "rounds", "approve", "grant", "confirm"}


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


def target(w: Word) -> CrEntry:
    """The CR the order is about: every kind that reaches for it names one."""
    if w.c is None:
        raise ChantierError(f"order {w.kind} names a CR", EXIT_USAGE)
    return w.c


def _need_note(w: Word, usage: str) -> str:
    if not w.note.strip():
        raise ChantierError(usage, EXIT_USAGE)
    return w.note.strip()


def _open_ids(b: Batch, cr_id: str) -> list[str]:
    """The CRs, other than this one and its fixes, neither merged nor cancelled."""
    return [
        x.id for x in b.record.crs if x.id != cr_id and x.kind != "fix" and x.status not in ENDED
    ]


def _add(w: Word) -> list[str]:
    b = w.b
    if w.fix_for:
        release_cr(b, "add --fix-for", w.fix_for)
        rel = b.cr(w.fix_for)
        if w.own:
            check_granted_fix(b, rel)
        fix = add_cr(b, filed_fix(b, rel, w.note), kind="fix")
        fix.fix_for = w.fix_for
        rel.append(
            "notes",
            f"fix: {fix.id} must merge first; then the procedure starts again from its first step",
        )
        b.touch(rel)
        return [f"added {fix.id} (fix for {w.fix_for}), queued"]
    if w.release:
        return add_release(b, w.note)
    check_release_open(b)
    added = add_cr(b, w.note)
    declare_dependencies(b, [added])
    join_release(b, added)
    waits = f", after {', '.join(added.after)}" if added.after else ""
    return [f"added {added.id}, queued{waits}"]


def _after_ids(w: Word) -> list[str]:
    """The CR ids `order after` names, checked: known, not the release CR, not itself."""
    b, cr_id, note = w.b, w.cr_id, w.note
    ids: list[str] = []
    for dep in [] if note.strip() == "-" else [s.strip() for s in note.split(",")]:
        if not any(x.id == dep for x in b.record.crs):
            raise ChantierError(f"order after: unknown CR {dep!r} in batch {b.id}")
        if is_release(b.cr(dep)):
            raise ChantierError(
                f"order after: {dep} is the release CR, which waits for every "
                f"other CR: {cr_id} waiting for it is a cycle"
            )
        if dep == cr_id:
            raise ChantierError(f"order after: {cr_id} cannot wait for itself")
        if b.cr(dep).status != "merged" and dep not in ids:  # merged: met, not recorded
            ids.append(dep)
    return ids


def _after(w: Word) -> list[str]:
    b, c, cr_id = w.b, target(w), w.cr_id
    _need_note(w, 'order after <cr> --note "<CR ids, comma separated, or - for none>"')
    if is_release(c):
        raise ChantierError(
            f"order after: {cr_id} is the release CR: the CLI keeps what it "
            "waits for (every other CR of the batch)"
        )
    if c.status != "queued":
        stack = "; in a stack, its place and base are set by `stack`"
        raise ChantierError(
            f"cannot change what {cr_id} waits for: it is {c.status}, not queued"
            + (stack if b.record.mode == "stack" else "")
        )
    ids = _after_ids(w)
    previous = c.after
    _set_after(c, ids)
    try:
        check_cycles(b)
    except ChantierError:
        _set_after(c, previous)
        raise
    b.touch(c)
    b.log("depends", cr_id, after=ids)
    return [f"{cr_id} now waits for {', '.join(ids)}" if ids else f"{cr_id} waits for nothing"]


def _set_after(c: CrEntry, ids: list[str]) -> None:
    if ids:
        c.after = ids
    else:
        c.unset("after")


def _drop(w: Word) -> list[str]:
    b, c, cr_id = w.b, target(w), w.cr_id
    if c.status == "merged":
        raise ChantierError(f"cannot drop {cr_id}: it is already merged")
    if c.status in LIVE:
        return [f"{cr_id} is live: the Foreman stops its Driver, then `chantier cancel {cr_id}`"]
    if c.status == "cancelled":
        raise ChantierError(f"{cr_id} is already dropped: {c.path}", EXIT_PRECONDITION)
    trash_cr(b, c)
    b.touch(c, status="cancelled")
    return [f"dropped {cr_id}: {c.path}"]


def _note(w: Word) -> list[str]:
    b, c, cr_id = w.b, w.c, w.cr_id
    _need_note(w, 'order note [<cr>] --note "<the user\'s word, in one line>"')
    if c and c.status == "cancelled":
        raise ChantierError(f"cannot note {cr_id}: it is cancelled", EXIT_PRECONDITION)
    if c:
        c.append("notes", w.note.strip())
        b.touch(c)
    out = [f"noted{' on ' + cr_id if c else ''}: the Foreman reads it in `status`"]
    if c and c.status in ("ready", "blocked"):
        out.append(
            f"{c.id} is {c.status}: no Driver works on it until the Foreman "
            f'takes it back (take {c.id} --note "<why>")'
        )
    return out


def _merged(w: Word) -> list[str]:
    b, c, cr_id = w.b, target(w), w.cr_id
    if c.status == "merged":
        return [f"{cr_id} already merged"]
    if c.status == "cancelled":
        raise ChantierError(f"cannot mark cancelled {cr_id} merged")
    open_ = _open_ids(b, cr_id) if c.kind == "release" else []
    if open_:
        raise ChantierError(
            f"order merged: {', '.join(open_)} not merged or cancelled: the release PR merges last"
        )
    # a merged head needs no gate: stop it first, while the CR's folder and its log are in place
    stopped = _stop_gate(b, cr_id)
    if c.kind != "release":
        lines = merge_done(b, c)
        return [lines[0], *stopped, *lines[1:]]
    release_merged(b, c)
    return [f"merged {cr_id}: the procedure goes on with a new Release driver", *stopped]


def _stop_gate(b: Batch, cr_id: str) -> list[str]:
    """Stop the long gate the slots name for this CR, as `gate <cr> --stop` does; its line."""
    v = slot_of(b.repo, cr_id)
    if v is None or v.holder is None:
        return []
    s = stop_gate(v.slot, v.holder, b, "")
    if not s.acted:
        return []
    return [f"stopped the long gate of {cr_id}" + (f" (pg{s.pg})" if s.pg is not None else "")]


def _rounds(w: Word) -> list[str]:
    if not w.note.isdigit() or int(w.note) < 1:
        raise refused("order rounds <cr> --note <n>", w.note, "a whole number of rounds, 1 or more")
    w.b.touch(target(w), rounds=int(w.note))
    return [f"{w.cr_id}: up to {w.note} rounds"]


def _slots(w: Word) -> list[str]:
    if not w.note.isdigit():
        raise ChantierError("order slots --note <n> (0 holds: no new Driver starts)", EXIT_USAGE)
    w.b.record.slots = int(w.note)
    return [f"slots {w.note}"]


def _budget(w: Word) -> list[str]:
    if not re.fullmatch(r"\d+(\.\d+)?", w.note) or float(w.note) <= 0:
        raise refused("order budget --note <usd>", w.note, "a positive amount in dollars")
    w.b.record.budget_usd = float(w.note)
    return [f"budget ${float(w.note):g}"]


def _approve(w: Word) -> list[str]:
    release_cr(w.b, w.kind, w.cr_id)
    note = _need_note(w, 'order approve <release-cr> --note "<the action the user approved>"')
    c = target(w)
    c.append("approvals", note)
    c.append("notes", f"approved: {note}")
    w.b.touch(c)
    return [f"approved: {note}"]


def _grant(w: Word) -> list[str]:
    b = w.b
    release = release_cr(b, w.kind, w.cr_id)
    grant = parse_grant(w.note)
    if "budget_usd" in grant:
        b.record.budget_usd = grant.pop("budget_usd")
    for key, value in grant.items():
        setattr(release, key, value)
    check_grant(release, b.record.budget_usd)
    c = target(w)
    c.append("notes", f"grant: {w.note.strip()}")
    b.touch(c)
    return [f"granted: {grant_line(release)}"]


def _confirm(w: Word) -> list[str]:
    b, c, cr_id = w.b, target(w), w.cr_id
    release_cr(b, w.kind, cr_id)
    note = _need_note(
        w,
        'order confirm <release-cr> --note "<the user\'s word to run the release procedure>"',
    )
    if c.status in ENDED:
        raise ChantierError(f"order confirm: {cr_id} is {c.status}")
    open_ = _open_ids(b, cr_id)
    if open_:
        raise ChantierError(
            f"order confirm: {', '.join(open_)} not merged yet: the word to "
            "run the release procedure comes once they are merged"
        )
    if c.pr:
        raise ChantierError(
            f"order confirm: the release PR {c.pr} is not merged: the "
            "word comes once it is merged (`order merged`), or for a "
            "procedure with no release PR"
        )
    c.procedure = note
    c.append("notes", f"procedure: {note}")
    b.touch(c)
    return [f"{cr_id}: the user's word to run the release procedure is recorded: {note}"]


MODES = ("parallel", "series", "stack")


def _ready_times(b: Batch) -> dict[str, int]:
    """When each CR was last handed back ready: the place of its last `handback ... ready` event
    in the batch's `events.jsonl`, which is in time order (a stamp has one-second resolution)."""
    when: dict[str, int] = {}
    for i, e in enumerate(read_events(b.dir)):
        if e.kind == "handback" and e.result == "ready" and e.cr:
            when[e.cr] = i
    return when


def _chains_kept(seq: list[CrEntry]) -> list[CrEntry]:
    """A CR below one of its open `after` CRs moves just above the highest of them."""
    seq = list(seq)
    for _ in range(len(seq) * len(seq) + 1):
        ids = [x.id for x in seq]
        for c in seq:
            places = [ids.index(a) for a in c.after if a in ids]
            if places and max(places) > ids.index(c.id):
                seq.remove(c)
                seq.insert(max(places), c)  # the highest moved down one place by the removal
                break
        else:
            return seq
    return seq


def _reorder(b: Batch) -> list[str]:
    """MS-Q3: the open CRs (a fix and the release keep their place, merged and cancelled ones are
    never touched) take the places they hold, the ones handed back ready first, in the order they
    became ready, then the others in their order; the chains (`after`) kept."""
    open_ = sorted(
        (x for x in b.record.crs if x.status not in ENDED and x.kind not in {"fix", "release"}),
        key=lambda x: x.order,
    )
    when = _ready_times(b)
    ready = sorted((x for x in open_ if x.status == "ready"), key=lambda x: when.get(x.id, -1))
    seq = _chains_kept(ready + [x for x in open_ if x.status != "ready"])
    for place, c in zip([x.order for x in open_], seq, strict=True):
        if c.order != place:
            b.touch(c, order=place)
    return [x.id for x in seq]


def _mode(w: Word) -> list[str]:
    b = w.b
    to, now_ = w.note.strip(), b.record.mode or "parallel"
    if to not in MODES:
        raise ChantierError(
            "order mode --note parallel|series|stack (any mode to any other)", EXIT_USAGE
        )
    if b.record.closing:
        raise ChantierError(f"order mode: {b.id} is closing", EXIT_PRECONDITION)
    if to == now_:
        raise ChantierError(f"{b.id} is already a {to}")
    b.record.mode = to
    b.log("mode", None, mode=to, previous=now_)
    if now_ == "stack":
        for c in b.record.crs:
            c.stacked = False
    if to == "parallel":
        line = (
            f"{b.id} is parallel now: each open PR is rebased on the default branch, its long "
            "gate and CI run again, and it leaves draft once ready"
        )
    else:
        order = " → ".join(_reorder(b))
        line = (
            f"{b.id} is a stack now (order: {order}): the stack driver stacks the open PRs, "
            "the CRs to come join on top"
            if to == "stack"
            else f"{b.id} is a series now (order: {order}): each open PR is rebased on the one "
            "below, the ones above the bottom go back to draft"
        )
    return [line, *(["run `forge-stack unstack` before any rebase"] if now_ == "stack" else [])]


def _qa(w: Word) -> list[str]:
    return [
        f"QA folder: {w.cr_id}; the Foreman starts its QA driver, which holds a slot "
        "until `order done`"
    ]


HANDLERS: dict[str, Callable[[Word], list[str]]] = {
    "add": _add,
    "after": _after,
    "drop": _drop,
    "note": _note,
    "merged": _merged,
    "rounds": _rounds,
    "slots": _slots,
    "budget": _budget,
    "approve": _approve,
    "grant": _grant,
    "confirm": _confirm,
    "mode": _mode,
    "qa": _qa,
}


def apply_order(w: Word) -> list[str]:
    """The user's word, recorded at once: a folder moves, a number changes, a note is kept. Who
    takes a CR next, and when, is the Foreman's decision from `status`."""
    handler = HANDLERS.get(w.kind)
    if handler is None:
        raise ChantierError(
            f"order kind: one of {', '.join(sorted([*HANDLERS, 'done']))}", EXIT_USAGE
        )
    return handler(w)
