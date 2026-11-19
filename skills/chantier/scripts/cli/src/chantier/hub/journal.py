"""The event journal of a project: `forge-journal.jsonl` at the planning folder's root, one JSON
line per event (the name is historical: the file holds every event of the project, the forge's
and the board's). It is local (ignored by git) and append-only; chantier never truncates it.
`append` is its one writer path (the forge hub, `source: "hub"`; the board, `"board"`: its PRs
page, its backlog writes and its Configuration page; `"cli"` is room for a command); `read` its
one reader, for `chantier status` and `chantier watch`. `source` says who wrote a line, never
what it is: every reader dispatches on `kind`. Nothing here records anything in a batch: a line
is a signal for whom it is addressed.

A version 1 line carries, in this order, `v` (1), `seq` (1 for the first line, then the highest
readable `seq` plus one), `t`, `kind`, `source`, `audience` (a list of `project`, `role:<name>`,
`cr:<id>`, `session:<key>` or `user`; every writer of today writes `["project"]`), then the
payload of its kind:

- `merged`: `batch`, `cr`, `pr`, `into`, `into_cr`, `merged_at`, and once the base landed
  `landed_with` and `landed_at`. Written once per batch, CR and landed-or-not: a PR merged into
  another CR's branch is first read not landed, and one second line follows, once, when a later
  read finds it landed with its base.
- `checks-red`: `batch`, `cr`, `pr`, `head` (the PR head's commit SHA). Written once per batch,
  CR and head: a new red head after a fix gives a new line, the same head read again none.
- `config`: `key` (a dotted path into the configuration: `batch.slots`, `specifying.parallel`,
  or `hosts.<host>.roles.<role>.<agent|model|escalation>`), `old` and `new` (the effective values
  before and after the save, all layers included) and `batch` (the batch running or paused at the
  save, or null). Written by the board's Configuration page, once per key whose effective value a
  save changed. It wakes a watcher as a merge does.
- `board`: `action` (the board journal's kind: `new`, `move`, `edit`, `label`, `group`,
  `ungroup`, `next-batch`), `items`, `text` (those of the `board-journal.jsonl` line written in
  the same call) and `wakes` (true for `new`, `move` and `edit`). Written by the board's backlog
  writes. A line that wakes does as a merge does; one that does not rides along with the next.

A line with no `v` is version 0 (`by` where version 1 has `source`, no `audience`): `read` gives it
the source `by` and the audience `project`, and never rewrites it. A line of a newer version
counts for `seq` and wakes no one. A `board` or `config` line is never a duplicate: two identical
moves, or two saves of the same value, are two lines.

Every append runs under the project's lifecycle lock, reads the file, assigns `seq` and skips a
line already there, whoever wrote the first. An unreadable line is skipped, never rewritten."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from chantier.core import clock
from chantier.core.files import read_text
from chantier.core.repo import Repo
from chantier.lifecycle.stages import changes_lock

FILE = "forge-journal.jsonl"
VERSION = 1
KINDS = ("merged", "checks-red", "config", "board")
SOURCES = ("hub", "board", "cli")
PROJECT = "project"
SHA_SHOWN = 7
WAKING_ACTIONS = ("new", "move", "edit")
LIMITS = ("batch.slots", "specifying.parallel")
AUDIENCE_FORM = re.compile(r"project|user|(role|cr|session):[A-Za-z0-9-]+")
AUDIENCE_FORMS = "project, role:<name>, cr:<id>, session:<key>, user"


def audience_ok(value: Any) -> bool:
    """Whether `value` has the form of an audience value (never whether it names anything)."""
    return isinstance(value, str) and AUDIENCE_FORM.fullmatch(value) is not None


def newer(e: dict[str, Any]) -> bool:
    """Whether a line is of a version this chantier does not know."""
    return type(e.get("v")) is int and e["v"] > VERSION


def _effective(entry: dict[str, Any]) -> dict[str, Any]:
    """The line with its `source` and `audience` filled: a version 0 line's source is its `by`
    and its audience the project; a line of a newer version is for no one."""
    if newer(entry):
        return {**entry, "audience": []}
    audience = entry.get("audience")
    if not isinstance(audience, list) or not audience:
        audience = [PROJECT]
    source = entry.get("source", entry.get("by"))
    return {**entry, "source": source, "audience": audience}


def read(changes: Path) -> tuple[list[dict[str, Any]], list[int], list[tuple[int, int]]]:
    """The lines that are JSON objects, each with its effective `source` and `audience`; the
    numbers (from 1) of the lines that are not; and `(number, version)` of the lines of a newer
    version, which are among the first."""
    path = changes / FILE
    if not path.is_file():
        return [], [], []
    found: list[dict[str, Any]] = []
    bad: list[int] = []
    later: list[tuple[int, int]] = []
    for n, line in enumerate(read_text(path, "replace").splitlines(), 1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            entry = None
        if isinstance(entry, dict):
            found.append(_effective(entry))
            if newer(entry):
                later.append((n, entry["v"]))
        else:
            bad.append(n)
    return found, bad, later


def for_subscription(e: dict[str, Any], subscription: list[str]) -> bool:
    """Whether a line is for a watcher: its audience holds a value of the subscription."""
    return any(a in subscription for a in e.get("audience") or [])


def last_seq(entries: list[dict[str, Any]]) -> int:
    """The highest readable `seq`, 0 for none."""
    return max((e["seq"] for e in entries if type(e.get("seq")) is int), default=0)


def _key(e: dict[str, Any]) -> tuple[Any, ...]:
    """What makes two lines the same event."""
    kind = e.get("kind")
    if newer(e):
        return ("newer", e.get("seq"))
    if kind == "checks-red":
        return ("checks-red", e.get("batch"), e.get("cr"), e.get("head"))
    if kind == "merged":
        return ("merged", e.get("batch"), e.get("cr"), bool(e.get("landed_with")))
    return (kind, e.get("seq"))  # `board`, `config`: each line is its own event


def merged_events(batch: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The `merged` events of the rows the forge shows merged and the record does not."""
    out: list[dict[str, Any]] = []
    for r in rows:
        if r.get("why") != "merged":
            continue
        landed = r.get("landed_with") or {}
        into = r["merged_into"] or {}
        entry: dict[str, Any] = {
            "kind": "merged",
            "batch": batch,
            "cr": r["cr"],
            "pr": r["pr"],
            "into": into.get("branch"),
            "into_cr": into.get("cr"),
            "merged_at": r["merged_at"],
        }
        if landed:
            entry["landed_with"], entry["landed_at"] = landed["cr"], landed["at"]
        out.append(entry)
    return out


def red_event(batch: str, cr: str, pr: str, head: str) -> dict[str, Any]:
    return {"kind": "checks-red", "batch": batch, "cr": cr, "pr": pr, "head": head}


def board_event(action: str, items: list[str], text: str) -> dict[str, Any]:
    """The `board` line of one backlog write of the board."""
    return {
        "kind": "board",
        "action": action,
        "items": items,
        "text": text,
        "wakes": action in WAKING_ACTIONS,
    }


def waking(e: dict[str, Any]) -> bool:
    """Whether a line starts or extends a watcher's wait: every line but a `board` line whose
    `wakes` is not true."""
    return e.get("kind") != "board" or e.get("wakes") is True


def append(repo: Repo, events: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    """Append each event not yet in the journal as a version 1 line, under the lifecycle lock;
    the lines written. The one writer path. An event with no `audience` is for the project. A
    `source`, a `kind` or an audience value of a wrong form is a code fault (`ValueError`)."""
    if source not in SOURCES:
        raise ValueError(f"journal source {source!r}: one of {', '.join(SOURCES)}")
    for event in events:
        if event.get("kind") not in KINDS:
            raise ValueError(f"journal kind {event.get('kind')!r}: one of {', '.join(KINDS)}")
        audience = event.get("audience", [PROJECT])
        if not isinstance(audience, list) or not audience or not all(map(audience_ok, audience)):
            raise ValueError(f"journal audience {audience!r}: values of {AUDIENCE_FORMS}")
    if not events:
        return []
    with changes_lock(repo):
        entries = read(repo.changes)[0]
        seen = {_key(e) for e in entries}
        seq = last_seq(entries)
        written: list[dict[str, Any]] = []
        for event in events:
            payload = {k: v for k, v in event.items() if k not in ("kind", "audience")}
            line = {
                "v": VERSION,
                "seq": seq + 1,
                "t": clock.now(),
                "kind": event["kind"],
                "source": source,
                "audience": event.get("audience", [PROJECT]),
                **payload,
            }
            if _key(line) in seen:
                continue
            seen.add(_key(line))
            seq += 1
            written.append(line)
        if written:
            text = "".join(
                json.dumps(e, ensure_ascii=False, separators=(",", ":")) + "\n" for e in written
            )
            with (repo.changes / FILE).open("ab") as f:
                f.write(text.encode("utf-8", errors="replace"))
        return written


def merged_text(e: dict[str, Any]) -> str:
    """The line a `merged` event is told by, in `status` and at a watcher's end."""
    head = f"forge saw merged: {e.get('cr')} {e.get('pr')}"
    at, cr = e.get("merged_at"), e.get("cr")
    if e.get("into_cr") and e.get("landed_with"):
        return (
            f"{head} into {e['into_cr']}'s branch at {at}, landed with {e['landed_with']} "
            f"at {e.get('landed_at')}; for the Chief of Staff: order merged {cr}"
        )
    if e.get("into_cr"):
        return (
            f"{head} into {e['into_cr']}'s branch at {at}; for the Chief of Staff: not "
            f"landed, tell the user, record nothing until {e['into_cr']} lands"
        )
    return f"{head} into {e.get('into')} at {at}; for the Chief of Staff: order merged {cr}"


def red_text(e: dict[str, Any]) -> str:
    return (
        f"forge saw checks red: {e.get('cr')} {e.get('pr')} at {str(e.get('head'))[:SHA_SHOWN]}, "
        "ready to merge in the record; for the Chief of Staff: tell the user, record nothing"
    )


def config_text(e: dict[str, Any]) -> str:
    """The line a `config` event is told by: the limit that changed on the board, and what
    happens to the batch."""
    key = e.get("key")
    old = "inherited" if e.get("old") is None else e.get("old")
    new = "inherited" if e.get("new") is None else e.get("new")
    if key not in LIMITS:
        return (
            f"config changed on the board: {key} {old} -> {new}; applies at the next batch; "
            "for the Chief of Staff: tell the user, act on nothing"
        )
    head = f"config changed on the board: {key} {e.get('old')} -> {e.get('new')}"
    if key != "batch.slots":
        return head
    if e.get("batch"):
        return f"{head}; {e['batch']} keeps {e.get('old')} until an order slots"
    return f"{head}; from the next open (no batch)"


def board_text(e: dict[str, Any]) -> str:
    return (
        f"board wrote ({e.get('action')}): {e.get('text')}; "
        "for the Chief of Staff: tell the user, act on nothing"
    )


def event_text(e: dict[str, Any]) -> str:
    kind = e.get("kind")
    if kind == "checks-red":
        return red_text(e)
    if kind == "config":
        return config_text(e)
    return board_text(e) if kind == "board" else merged_text(e)


def _slots_line(entries: list[dict[str, Any]], batch: str, orders: list[Any]) -> list[str]:
    """The newest `batch.slots` line, when it is this batch's and no order of kind `slots` has a
    time strictly after its own; else none. Stamps are whole seconds: an order of the same second
    does not hide the line (a line shown too long costs one `order slots`, a line hidden too soon
    is a lost signal)."""
    found = [
        e
        for e in entries
        if not newer(e) and e.get("kind") == "config" and e.get("key") == "batch.slots"
    ]
    if not found:
        return []
    newest = max(found, key=lambda e: (e.get("t") or "", e.get("seq") or 0))
    if newest.get("batch") != batch:
        return []
    if any(o.kind == "slots" and (o.sent or "") > (newest.get("t") or "") for o in orders):
        return []
    return [config_text(newest)]


def lines(
    entries: list[dict[str, Any]], batch: str, open_crs: set[str], orders: list[Any]
) -> list[str]:
    """The `status` lines for the Chief of Staff, one per open CR of `batch`: the `merged` entry
    that says the PR landed wins, else the first. A `checks-red` entry is never listed. Then the
    newest `batch.slots` `config` line of the batch while no `order slots` is recorded after it;
    no line for the other limit or key."""
    chosen: dict[str, dict[str, Any]] = {}
    for e in entries:
        cr = e.get("cr")
        if newer(e) or e.get("kind") != "merged" or e.get("batch") != batch or cr not in open_crs:
            continue
        if cr not in chosen or (e.get("landed_with") and not chosen[cr].get("landed_with")):
            chosen[cr] = e
    return [*(merged_text(e) for e in chosen.values()), *_slots_line(entries, batch, orders)]
