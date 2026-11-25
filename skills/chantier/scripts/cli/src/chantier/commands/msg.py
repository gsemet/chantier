"""`msg` and `inbox`: a Driver tells the batch's steering session (its Foreman, or the Chief of
Staff in direct mode) through the project's journal and that session's watcher, and the steering
session lists the batch's messages it has not marked read. `msg` appends one `msg@1` line through
the one append function, after the batch's record is saved (both take the planning folder's lock,
so the two steps are not nested); `inbox --read` keeps its marks in the batch's own
`events.jsonl`, since the journal is append-only. Neither writes in a CR's folder, messages a
session or reaches the server."""

from __future__ import annotations

import argparse
import re
from typing import Any

from chantier.board.projects import project_name
from chantier.core import leases
from chantier.core.batch import check_epoch, find_cr_batch, require_epoch, resolve_batch
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.ids import normalize_cr
from chantier.core.records import BatchRecord, read_events
from chantier.core.repo import Repo
from chantier.core.waits import hhmm
from chantier.hub import autostart, journal, lock, state
from chantier.lifecycle.session import RenderedBatch

TEXT_MAX = 300  # as `hub/journal_add.py`'s
WAKES = ("anomaly", "blocked")
NOT_DELIVERED = (
    "not delivered: no watcher subscribed; the steering session reads it with inbox; reach it by "
    "your host's means (chantier host) or hand back"
)


def _text(words: list[str]) -> str:
    """The message's text, one line of at most `TEXT_MAX` characters; exit 1 otherwise."""
    text = " ".join(words).strip()
    if not text:
        raise ChantierError("msg: the text is empty: msg steering <kind> <text>", EXIT_USAGE)
    if "\n" in text or "\r" in text:
        raise ChantierError("msg: text is one line: write it again on one line", EXIT_USAGE)
    if len(text) > TEXT_MAX:
        raise ChantierError(
            f"msg: text is at most {TEXT_MAX} characters (got {len(text)}): shorten it", EXIT_USAGE
        )
    return text


def steering_of(d: BatchRecord) -> tuple[str, str]:
    """The batch's steering word (`direct` or `foreman`) and its session's key ("" when no
    steering session recorded its transcript). In direct mode the Chief of Staff's transcript is
    the recorded Foreman transcript (`seat.py`), else its own."""
    if d.steering == "direct":
        return "direct", autostart.kept(d.foreman_transcript or d.chief_transcript)
    return "foreman", autostart.kept(d.foreman_transcript)


def delivered(repo: Repo, key: str) -> bool:
    """A watcher of that session holds its lock and a surface server runs, so its `events` topic
    carries the line. The server publishes no list of its subscriptions: this is the closest
    reading that changes no protocol."""
    return (
        bool(key)
        and key in lock.watchers(repo.git_dir, project_name(repo))
        and state.live_entry(repo.git_dir, state.SERVER) is not None
    )


def msg(args: argparse.Namespace) -> tuple[list[str], int] | list[str]:
    repo = Repo.find()
    text, kind = _text(args.text), args.kind
    unit = "stack" if args.cr == "stack" else normalize_cr(args.cr)
    if unit != "stack" and not re.fullmatch(r"CR-[0-9]+", unit):
        raise ChantierError(f"msg: --cr {args.cr}: a CR id or stack", EXIT_USAGE)
    name = resolve_batch(repo, args.batch) if unit == "stack" else None
    with RenderedBatch(repo, name or find_cr_batch(repo, unit, args.batch), actor="driver") as b:
        if b.record.status not in ("running", "paused"):
            raise ChantierError(
                f"msg: {b.id} is {b.record.status}: no steering session to message; hand back "
                "instead",
                EXIT_PRECONDITION,
            )
        leases.claim(b, unit, args.lease, what=f"msg {unit}", required=True)
        b.log("msg", unit, msg_kind=kind, note=text)
        word, key = steering_of(b.record)
        batch = b.id
    event: dict[str, Any] = {
        "type": "msg@1",
        "audience": [f"session:{key}" if key else "role:steering"],
        "batch": batch,
        "unit": unit,
        "kind": kind,
        "text": text,
        "wakes": kind in WAKES,
        "steering": word,
    }
    seq = journal.append(repo, [event], "cli")[0]["seq"]
    whom = "the Chief of Staff (direct)" if word == "direct" else f"the Foreman ({batch})"
    head = f"msg: seq {seq} {kind} from {unit} to {whom}"
    if not delivered(repo, key):
        return [head, NOT_DELIVERED], EXIT_PRECONDITION
    told = ", told at its next wake" if kind == "note" else ""
    return [f"{head}: delivered to its watcher{told}"]


def _read_word(word: str | None) -> int | str | None:
    if word is None or word == "all":
        return word
    if not word.isdigit():
        raise ChantierError(f"inbox --read <seq>|all, not {word!r}", EXIT_USAGE)
    return int(word)


def inbox(args: argparse.Namespace) -> list[str]:
    require_epoch(args.epoch, "inbox --epoch <n>")
    which = _read_word(args.read)
    repo = Repo.find()
    with RenderedBatch(repo, resolve_batch(repo, args.batch, paused=True), actor="foreman") as b:
        check_epoch(b, args.epoch)
        mine = [
            e
            for e in journal.read(repo.store, repo.changes)[0]
            if journal.listed(e) and e.get("type") == "msg@1" and e.get("batch") == b.id
        ]
        marked = {
            int(s)
            for e in read_events(repo.store, b.dir)
            if e.kind == "inbox-read"
            for s in e.seqs or []
        }
        unread = sorted((e for e in mine if e["seq"] not in marked), key=lambda e: e["seq"])
        n = args.epoch
        if which is None:
            if not unread:
                return ["inbox: nothing unread"]
            return [
                *(
                    f'#{e["seq"]} {hhmm(str(e.get("t")))} {e["unit"]} {e["kind"]}: "{e["text"]}"'
                    for e in unread
                ),
                f"inbox: {len(unread)} unread; once handled: inbox --read <seq>|all --epoch {n}",
            ]
        if which == "all":
            if unread:
                b.log("inbox-read", None, seqs=[e["seq"] for e in unread])
            return [f"inbox: {len(unread)} read; nothing unread"]
        if which not in {e["seq"] for e in mine}:
            raise ChantierError(
                f"inbox: #{which} is no message of {b.id}; inbox --epoch {n} lists them",
                EXIT_USAGE,
            )
        if which in marked:
            return [f"inbox: #{which} already read"]
        b.log("inbox-read", None, seqs=[which])
        return [f"inbox: #{which} read; {len(unread) - 1} unread"]
