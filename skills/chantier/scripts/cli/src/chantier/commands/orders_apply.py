"""What each kind of `chantier order` does to the record: one small function per kind."""

from __future__ import annotations

import re
from collections.abc import Callable

from chantier.commands.crs import filed_fix, fix_folder, grant_line
from chantier.commands.gate_run import stop_gate, stopped_line
from chantier.commands.joining import add_cr, check_joins, join_cr, join_paths
from chantier.commands.opening import declare_dependencies
from chantier.commands.orders_after import after
from chantier.commands.orders_drop import drop
from chantier.commands.orders_hold import hold, unhold
from chantier.commands.orders_merged import (
    chain_above,
    check_merged,
    open_ids,
)
from chantier.commands.orders_release import (
    add_release,
    check_release_open,
    join_release,
    refused,
    release_cr,
)
from chantier.commands.orders_reorder import release_holds, reorder
from chantier.commands.orders_waive import USAGE, stack_waiver, waive_cr, waive_stack
from chantier.commands.orders_word import Word, target
from chantier.core.batch import Batch
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.gate_slots import slot_of
from chantier.rails import ENDED
from chantier.rails_release import (
    check_grant,
    check_granted_fix,
    merge_done,
    parse_grant,
    release_merged,
)
from chantier.status.due import restack_line

CR_ORDERS = {"after", "drop", "merged", "rounds", "approve", "grant", "confirm", "hold", "unhold"}


def _need_note(w: Word, usage: str) -> str:
    if not w.note.strip():
        raise ChantierError(usage, EXIT_USAGE)
    return w.note.strip()


def _add(w: Word) -> list[str]:
    b = w.b
    if w.fix_for:
        release_cr(b, "add --fix-for", w.fix_for)
        rel = b.cr(w.fix_for)
        if w.own:
            check_granted_fix(b, rel)
        if (folder := fix_folder(b, rel, w.note)) is None:
            check_joins(b.repo, [w.note])
        else:  # the filing and the join, before the first change
            made = [folder, folder / "intake" / "request.md", folder / "03-change-spec.md"]
            b.repo.check_publish([*made, *join_paths(b.repo, [folder])])
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
    check_joins(b.repo, [w.note])
    added, joined = join_cr(b, w.note)
    declare_dependencies(b, [added])
    join_release(b, added)
    waits = f", after {', '.join(added.after)}" if added.after else ""
    out = [f"added {added.id}, queued{waits}", *([joined] if joined else [])]
    standing = stack_waiver(b)
    if standing is not None and added.kind not in {"release", "fix"}:
        added.gate_waiver = standing.model_copy()
        out.append(f"{added.id} joins the stack waiver {standing.order}: the top's gate validates")
    return out


def _waive(w: Word) -> list[str]:
    """`order waive stack|<cr> --note <words> [--follow-up <folder>]`: the long gate waived, a
    fact on each CR it covers; `--note -` withdraws it."""
    note = _need_note(w, USAGE)
    if w.cr_id == "stack":
        return waive_stack(w.b, note, w.follow_up, w.order_id)
    return waive_cr(w.b, target(w), note, w.follow_up, w.order_id)


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
    if check_merged(b, c):
        return [f"{cr_id} already merged"]
    # a merged head needs no gate: it was stopped and waited for before the locks (`w.stopped`),
    # or a stale lock is stopped now, while the CR's folder and its log are in place
    stopped = w.stopped or _stop_gate(b, cr_id)
    if c.kind != "release":
        above = chain_above(b.record, c)  # read before the CR is marked merged
        c.unset("held")  # merged on the default branch: no longer held
        lines = merge_done(b, c)
        w.ended = True  # `end_of_batch` pauses the batch, or says what keeps it open
        return [lines[0], *restack_line(b.record, cr_id, above), *stopped]
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
    return [stopped_line(cr_id, s.pg)]


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
    open_ = open_ids(b, cr_id)
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
    freed: list[str] = []
    if now_ == "stack":
        freed = release_holds(b)
        for c in b.record.crs:
            c.stacked = False
    if to == "parallel":
        line = (
            f"{b.id} is parallel now: each open PR is rebased on the default branch, its long "
            "gate and CI run again, and it leaves draft once ready"
        )
    else:
        order = " → ".join(reorder(b))
        line = (
            f"{b.id} is a stack now (order: {order}): the stack driver stacks the open PRs, "
            "the CRs to come join on top"
            if to == "stack"
            else f"{b.id} is a series now (order: {order}): each open PR is rebased on the one "
            "below, the ones above the bottom go back to draft"
        )
    return [
        line,
        *freed,
        *(["run `forge-stack unstack` before any rebase"] if now_ == "stack" else []),
    ]


def _qa(w: Word) -> list[str]:
    return [
        f"QA folder: {w.cr_id}; the Foreman starts its QA driver, which holds a slot "
        "until `order done`"
    ]


HANDLERS: dict[str, Callable[[Word], list[str]]] = {
    "add": _add,
    "after": after,
    "drop": drop,
    "note": _note,
    "merged": _merged,
    "rounds": _rounds,
    "slots": _slots,
    "budget": _budget,
    "approve": _approve,
    "grant": _grant,
    "confirm": _confirm,
    "mode": _mode,
    "waive": _waive,
    "qa": _qa,
    "hold": hold,
    "unhold": unhold,
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
