"""What each kind of `chantier order` does to the record: one small function per kind."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from chantier.commands.crs import filed_fix, grant_line
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
from chantier.core.records import LIVE
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
    c: Any
    note: str
    fix_for: str | None = None
    own: bool = False
    release: bool = False


def _need_note(w: Word, usage: str) -> str:
    if not w.note.strip():
        raise ChantierError(usage, EXIT_USAGE)
    return w.note.strip()


def _open_ids(b: Batch, cr_id: str) -> list[str]:
    """The CRs, other than this one and its fixes, neither merged nor cancelled."""
    return [
        x["id"]
        for x in b.data["crs"]
        if x["id"] != cr_id and x.get("kind") != "fix" and x["status"] not in ENDED
    ]


def _add(w: Word) -> list[str]:
    b = w.b
    if w.fix_for:
        release_cr(b, "add --fix-for", w.fix_for)
        rel = b.cr(w.fix_for)
        if w.own:
            check_granted_fix(b, rel)
        fix = add_cr(b, filed_fix(b, rel, w.note), kind="fix")
        fix["fix_for"] = w.fix_for
        rel.setdefault("notes", []).append(
            f"fix: {fix['id']} must merge first; then the procedure starts again from its first "
            "step"
        )
        b.touch(rel)
        return [f"added {fix['id']} (fix for {w.fix_for}), queued"]
    if w.release:
        return add_release(b, w.note)
    check_release_open(b)
    added = add_cr(b, w.note)
    declare_dependencies(b, [added])
    join_release(b, added)
    waits = f", after {', '.join(added['after'])}" if added.get("after") else ""
    return [f"added {added['id']}, queued{waits}"]


def _after_ids(w: Word) -> list[str]:
    """The CR ids `order after` names, checked: known, not the release CR, not itself."""
    b, cr_id, note = w.b, w.cr_id, w.note
    ids: list[str] = []
    for dep in [] if note.strip() == "-" else [s.strip() for s in note.split(",")]:
        if not any(x["id"] == dep for x in b.data["crs"]):
            raise ChantierError(f"order after: unknown CR {dep!r} in batch {b.id}")
        if is_release(b.cr(dep)):
            raise ChantierError(
                f"order after: {dep} is the release CR, which waits for every "
                f"other CR: {cr_id} waiting for it is a cycle"
            )
        if dep == cr_id:
            raise ChantierError(f"order after: {cr_id} cannot wait for itself")
        if b.cr(dep)["status"] != "merged" and dep not in ids:  # merged: met, not recorded
            ids.append(dep)
    return ids


def _after(w: Word) -> list[str]:
    b, c, cr_id = w.b, w.c, w.cr_id
    _need_note(w, 'order after <cr> --note "<CR ids, comma separated, or - for none>"')
    if is_release(c):
        raise ChantierError(
            f"order after: {cr_id} is the release CR: the CLI keeps what it "
            "waits for (every other CR of the batch)"
        )
    if c["status"] != "queued":
        stack = "; in a stack, its place and base are set by `stack`"
        raise ChantierError(
            f"cannot change what {cr_id} waits for: it is {c['status']}, not queued"
            + (stack if b.data["mode"] == "stack" else "")
        )
    ids = _after_ids(w)
    previous = c.get("after", [])
    _set_after(c, ids)
    try:
        check_cycles(b)
    except ChantierError:
        _set_after(c, previous)
        raise
    b.touch(c)
    b.log("depends", cr_id, after=ids)
    return [f"{cr_id} now waits for {', '.join(ids)}" if ids else f"{cr_id} waits for nothing"]


def _set_after(c: dict[str, Any], ids: list[str]) -> None:
    if ids:
        c["after"] = ids
    else:
        c.pop("after", None)


def _drop(w: Word) -> list[str]:
    b, c, cr_id = w.b, w.c, w.cr_id
    if c["status"] == "merged":
        raise ChantierError(f"cannot drop {cr_id}: it is already merged")
    if c["status"] in LIVE:
        return [f"{cr_id} is live: the Foreman stops its Driver, then `chantier cancel {cr_id}`"]
    if c["status"] == "cancelled":
        raise ChantierError(f"{cr_id} is already dropped: {c['path']}", EXIT_PRECONDITION)
    trash_cr(b, c)
    b.touch(c, status="cancelled")
    return [f"dropped {cr_id}: {c['path']}"]


def _note(w: Word) -> list[str]:
    b, c, cr_id = w.b, w.c, w.cr_id
    _need_note(w, 'order note [<cr>] --note "<the user\'s word, in one line>"')
    if c and c["status"] == "cancelled":
        raise ChantierError(f"cannot note {cr_id}: it is cancelled", EXIT_PRECONDITION)
    if c:
        c.setdefault("notes", []).append(w.note.strip())
        b.touch(c)
    out = [f"noted{' on ' + cr_id if c else ''}: the Foreman reads it in `status`"]
    if c and c["status"] in ("ready", "blocked"):
        out.append(
            f"{c['id']} is {c['status']}: no Driver works on it until the Foreman "
            f'takes it back (take {c["id"]} --note "<why>")'
        )
    return out


def _merged(w: Word) -> list[str]:
    b, c, cr_id = w.b, w.c, w.cr_id
    if c["status"] == "merged":
        return [f"{cr_id} already merged"]
    if c["status"] == "cancelled":
        raise ChantierError(f"cannot mark cancelled {cr_id} merged")
    if c.get("kind") != "release":
        return merge_done(b, c)
    open_ = _open_ids(b, cr_id)
    if open_:
        raise ChantierError(
            f"order merged: {', '.join(open_)} not merged or cancelled: the release PR merges last"
        )
    release_merged(b, c)
    return [f"merged {cr_id}: the procedure goes on with a new Release driver"]


def _rounds(w: Word) -> list[str]:
    if not w.note.isdigit() or int(w.note) < 1:
        raise refused("order rounds <cr> --note <n>", w.note, "a whole number of rounds, 1 or more")
    w.b.touch(w.c, rounds=int(w.note))
    return [f"{w.cr_id}: up to {w.note} rounds"]


def _slots(w: Word) -> list[str]:
    if not w.note.isdigit():
        raise ChantierError("order slots --note <n> (0 holds: no new Driver starts)", EXIT_USAGE)
    w.b.data["slots"] = int(w.note)
    return [f"slots {w.note}"]


def _budget(w: Word) -> list[str]:
    if not re.fullmatch(r"\d+(\.\d+)?", w.note) or float(w.note) <= 0:
        raise refused("order budget --note <usd>", w.note, "a positive amount in dollars")
    w.b.data["budget_usd"] = float(w.note)
    return [f"budget ${float(w.note):g}"]


def _approve(w: Word) -> list[str]:
    release_cr(w.b, w.kind, w.cr_id)
    note = _need_note(w, 'order approve <release-cr> --note "<the action the user approved>"')
    w.c.setdefault("approvals", []).append(note)
    w.c.setdefault("notes", []).append(f"approved: {note}")
    w.b.touch(w.c)
    return [f"approved: {note}"]


def _grant(w: Word) -> list[str]:
    b = w.b
    release = release_cr(b, w.kind, w.cr_id)
    grant = parse_grant(w.note)
    if "budget_usd" in grant:
        b.data["budget_usd"] = grant.pop("budget_usd")
    release.update(grant)
    check_grant(release, b.data.get("budget_usd"))
    w.c.setdefault("notes", []).append(f"grant: {w.note.strip()}")
    b.touch(w.c)
    return [f"granted: {grant_line(release)}"]


def _confirm(w: Word) -> list[str]:
    b, c, cr_id = w.b, w.c, w.cr_id
    release_cr(b, w.kind, cr_id)
    note = _need_note(
        w,
        'order confirm <release-cr> --note "<the user\'s word to run the release procedure>"',
    )
    if c["status"] in ENDED:
        raise ChantierError(f"order confirm: {cr_id} is {c['status']}")
    open_ = _open_ids(b, cr_id)
    if open_:
        raise ChantierError(
            f"order confirm: {', '.join(open_)} not merged yet: the word to "
            "run the release procedure comes once they are merged"
        )
    if c.get("pr"):
        raise ChantierError(
            f"order confirm: the release PR {c['pr']} is not merged: the "
            "word comes once it is merged (`order merged`), or for a "
            "procedure with no release PR"
        )
    c["procedure"] = note
    c.setdefault("notes", []).append(f"procedure: {note}")
    b.touch(c)
    return [f"{cr_id}: the user's word to run the release procedure is recorded: {note}"]


def _mode(w: Word) -> list[str]:
    b = w.b
    if b.data["mode"] != "series" or w.note.strip() != "stack":
        raise ChantierError(
            "order mode: only a series batch switches, to a stack (`order mode --note stack`)"
        )
    b.data["mode"] = "stack"
    b.log("mode", None, mode="stack")
    return [
        f"{b.id} is a stack now: a queued CR waits only for its `after`; the stack "
        "driver stacks the PRs"
    ]


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
