"""The event journal of a project: `forge-journal.jsonl` at the planning folder's root, one JSON
line per event (the name is historical: the file holds every event of the project, the forge's
and the board's). It is local (ignored by git) and append-only; chantier never truncates it.
`append` is its one writer path (the forge hub, `source: "hub"`; the board, `"board"`: its PRs
page, its backlog writes and its Configuration page; `"writer"`: the surface's writer, its
`sync-*` lines; an outside poller, `"poller"`, through `chantier journal add`; `"cli"` is
room for a command); `read` its
one reader, for `chantier status` and `chantier watch`. `source` says who wrote a line, never
what it is: every reader dispatches on the line's type. Nothing here records anything in a batch:
a line is a signal for whom it is addressed.

A version 2 line carries, in this order, `v` (2), `seq` (1 for the first line, then the highest
readable `seq` plus one), `t`, `type`, `source`, `audience` (a list of `project`, `role:<name>`,
`cr:<id>`, `session:<key>` or `user`; every writer of today writes `["project"]`), then the
payload of its type. The type is `name@N`: the name and the published version of the payload. The
published types and their payloads are `hub/schemas.py`'s `PUBLISHED` (`merged@1`,
`checks-red@1`, `wait-cleared@1`, `config@1`, `board@1`, `issue@1`, and the writer's
`sync-conflict@1`, `sync-blocked@1`, `sync-late@1`, `sync-resumed@1`), each with its model, wake
rule, text, duplicate key and example. A published `name@N` never changes; a change is a new
`name@N+1`, published beside it. Its JSON Schema is in `hub/schemas.json`, written by
`just journal-schemas`.

A line with no `v` is version 0 (`by` where later versions have `source`, no `audience`), and a
version 1 line has `kind` where version 2 has `type`: `read` gives each its effective type,
`<kind>@1`, and the source `by` and the audience `project` for version 0, and never rewrites it. A
version 2 line of a type not in `PUBLISHED` (a newer chantier wrote it) counts for `seq`, wakes no
one and is named with its type by `read`; one whose payload its model refuses counts for `seq`,
wakes no one and is listed as unreadable. A line of a newer version counts for `seq` and wakes no
one. A `board@1`, `config@1` or `sync-*@1` line is never a duplicate: two identical moves, two saves
of the same value, or two conflicts with the same shas in two episodes, are two lines.

Every append runs under the project's lifecycle lock, reads the file, assigns `seq` and skips a
line already there, whoever wrote the first. An unreadable line is skipped, never rewritten."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from chantier.board.crs import link_of
from chantier.core import clock
from chantier.core.files import rel_in
from chantier.core.records import BatchRecord
from chantier.core.repo import Repo
from chantier.hub import schemas
from chantier.hub.schemas import PUBLISHED, config_text, merged_text, wait_cleared_text
from chantier.lifecycle.stages import changes_lock

if TYPE_CHECKING:
    from chantier.store.base import PlanStore

FILE = "forge-journal.jsonl"
VERSION = 2
SOURCES = ("hub", "board", "cli", "poller", "writer")
PROJECT = "project"
WAKING_ACTIONS = ("new", "move", "edit", "running-batch", "grill")
HEADER = ("v", "seq", "t", "type", "source", "audience")
AUDIENCE_FORM = re.compile(r"project|user|(role|cr|session):[A-Za-z0-9-]+")
AUDIENCE_FORMS = "project, role:<name>, cr:<id>, session:<key>, user"


def audience_ok(value: Any) -> bool:
    """Whether `value` has the form of an audience value (never whether it names anything)."""
    return isinstance(value, str) and AUDIENCE_FORM.fullmatch(value) is not None


def newer(e: dict[str, Any]) -> bool:
    """Whether a line is of a version this chantier does not know."""
    return type(e.get("v")) is int and e["v"] > VERSION


def _payload(entry: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in entry.items() if k not in HEADER}


def _effective(entry: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """The line with its `source`, `audience` and `type` filled, and what it is: `ok`, `newer`
    (a version this chantier does not know), `unknown` (a version 2 line of a type not published)
    or `refused` (a published type whose model refuses the payload). A version 0 line's source is
    its `by` and its audience the project; its type, like a version 1 line's, is `<kind>@1`. A
    line that is not `ok` is for no one."""
    if newer(entry):
        return {**entry, "audience": []}, "newer"
    audience = entry.get("audience")
    if not isinstance(audience, list) or not audience:
        audience = [PROJECT]
    source = entry.get("source", entry.get("by"))
    if entry.get("v") == VERSION:
        type_ = entry.get("type")
        line = {**entry, "source": source, "audience": audience}
        if not isinstance(type_, str) or type_ not in PUBLISHED:
            return {**line, "audience": []}, "unknown"
        if schemas.check(type_, _payload(entry)):
            return {**line, "audience": []}, "refused"
        return line, "ok"
    kind = entry.get("kind")
    type_ = f"{kind}@1" if isinstance(kind, str) else None
    return {**entry, "type": type_, "source": source, "audience": audience}, "ok"


def read(
    store: PlanStore, changes: Path
) -> tuple[list[dict[str, Any]], list[int], list[tuple[int, int]], list[tuple[int, str]]]:
    """The lines that are JSON objects, each with its effective `type`, `source` and `audience`;
    the numbers (from 1) of the lines that are not, with those of a published type whose payload
    its model refuses; `(number, version)` of the lines of a newer version; and `(number, type)`
    of the version 2 lines of a type not published. Those lines are among the first, with an empty
    audience."""
    rel = rel_in(store.root, changes / FILE)
    if not store.is_file(rel):
        return [], [], [], []
    found: list[dict[str, Any]] = []
    bad: list[int] = []
    later: list[tuple[int, int]] = []
    unknown: list[tuple[int, str]] = []
    for n, line in enumerate(store.read_text(rel, "replace").splitlines(), 1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            entry = None
        if not isinstance(entry, dict):
            bad.append(n)
            continue
        effective, status = _effective(entry)
        found.append(effective)
        if status == "newer":
            later.append((n, entry["v"]))
        elif status == "refused":
            bad.append(n)
        elif status == "unknown":
            unknown.append((n, str(entry.get("type"))))
    return found, bad, later, unknown


def for_subscription(e: dict[str, Any], subscription: list[str]) -> bool:
    """Whether a line is for a watcher: its audience holds a value of the subscription."""
    return any(a in subscription for a in e.get("audience") or [])


def last_seq(entries: list[dict[str, Any]]) -> int:
    """The highest readable `seq`, 0 for none."""
    return max((e["seq"] for e in entries if type(e.get("seq")) is int), default=0)


def _key(e: dict[str, Any]) -> tuple[Any, ...]:
    """What makes two lines the same event: the duplicate key of the line's type. A line for no
    one (newer, of an unknown type, with a refused payload) and a type with no key are each their
    own event."""
    type_ = e.get("type")
    entry = PUBLISHED.get(type_) if isinstance(type_, str) else None
    if newer(e) or entry is None or entry.key is None or not e.get("audience"):
        return (type_, e.get("seq"))
    return entry.key(e)


def _listed(e: dict[str, Any]) -> bool:
    """Whether a line is of a known version and a published type, with a payload its model
    accepts: the lines `status` may tell."""
    return not newer(e) and e.get("type") in PUBLISHED and bool(e.get("audience", [PROJECT]))


def merged_events(batch: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The `merged@1` events of the rows the forge shows merged and the record does not."""
    out: list[dict[str, Any]] = []
    for r in rows:
        if r.get("why") != "merged":
            continue
        landed = r.get("landed_with") or {}
        into = r["merged_into"] or {}
        entry: dict[str, Any] = {
            "type": "merged@1",
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


def seen_merged(entries: list[dict[str, Any]], d: BatchRecord) -> frozenset[str]:
    """The ids of the CRs of `d` the forge hub saw merged: a listed `merged@1` line of this batch
    whose `cr` is the CR and whose `pr` is the CR's recorded PR link (an old line does not hit a
    CR that came back with a new PR). Any such line counts, `into_cr` or `landed_with` or not. Pure:
    the caller reads the journal."""
    link = {c.id: link_of(c.pr) for c in d.crs}
    return frozenset(
        str(e["cr"])
        for e in entries
        if _listed(e)
        and e.get("type") == "merged@1"
        and e.get("batch") == d.id
        and isinstance(e.get("cr"), str)
        and link.get(e["cr"]) is not None
        and e.get("pr") == link[e["cr"]]
    )


def red_event(batch: str, cr: str, pr: str, head: str) -> dict[str, Any]:
    """The `checks-red@1` event of a PR whose checks fail at `head`."""
    return {"type": "checks-red@1", "batch": batch, "cr": cr, "pr": pr, "head": head}


def board_event(action: str, items: list[str], text: str) -> dict[str, Any]:
    """The `board@1` event of one backlog write of the board."""
    return {
        "type": "board@1",
        "action": action,
        "items": items,
        "text": text,
        "wakes": action in WAKING_ACTIONS,
    }


def waking(e: dict[str, Any]) -> bool:
    """Whether a line starts or extends a watcher's wait: by its type's wake rule (a line of no
    published type, or with a refused payload, wakes no one)."""
    type_ = e.get("type")
    entry = PUBLISHED.get(type_) if isinstance(type_, str) else None
    if entry is None or not e.get("audience", [PROJECT]):  # for no one: wakes no one
        return False
    return e.get(entry.wakes) is True if isinstance(entry.wakes, str) else entry.wakes


def _refusal(event: dict[str, Any]) -> str | None:
    """Why an event's type or payload is refused (the message), else None."""
    return schemas.check(
        event.get("type"), {k: v for k, v in event.items() if k not in ("type", "audience")}
    )


def set_aside(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """The events whose type is published and whose payload its model accepts, and one message
    (`journal payload <type>: ...`) per event refused. For the callers that build events from what
    a forge returned or from a board write: they append the first and name the second, where
    `append` raises."""
    accepted: list[dict[str, Any]] = []
    refused: list[str] = []
    for event in events:
        why = _refusal(event)
        if why:
            refused.append(why)
        else:
            accepted.append(event)
    return accepted, refused


def skipped(refused: list[str]) -> str | None:
    """The error a caller shows for the events it set aside: `skipped: <messages>`, else None."""
    return f"skipped: {'; '.join(refused)}" if refused else None


def append(repo: Repo, events: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    """Append each event not yet in the journal as a version 2 line, under the lifecycle lock;
    the lines written. The one writer path. An event is `{"type": "name@N", "audience"?, ...}`
    with its payload; with no `audience` it is for the project. A `source`, a type not published,
    a payload its model refuses or an audience value of a wrong form is a code fault
    (`ValueError`), and nothing is written."""
    if source not in SOURCES:
        raise ValueError(f"journal source {source!r}: one of {', '.join(SOURCES)}")
    for event in events:
        why = _refusal(event)
        if why:
            raise ValueError(why)
        audience = event.get("audience", [PROJECT])
        if not isinstance(audience, list) or not audience or not all(map(audience_ok, audience)):
            raise ValueError(f"journal audience {audience!r}: values of {AUDIENCE_FORMS}")
    if not events:
        return []
    with changes_lock(repo):
        entries = read(repo.store, repo.changes)[0]
        seen = {_key(e) for e in entries}
        seq = last_seq(entries)
        written: list[dict[str, Any]] = []
        for event in events:
            payload = {k: v for k, v in event.items() if k not in ("type", "audience")}
            line = {
                "v": VERSION,
                "seq": seq + 1,
                "t": clock.now(),
                "type": event["type"],
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


def event_text(e: dict[str, Any]) -> str:
    """The line an event is told by: its type's text."""
    return PUBLISHED[e["type"]].text(e)


def _slots_line(entries: list[dict[str, Any]], batch: str, orders: list[Any]) -> list[str]:
    """The newest `batch.slots` line, when it is this batch's and no order of kind `slots` has a
    time strictly after its own; else none. A line of no published type or with a refused payload
    is not one. Stamps are whole seconds: an order of the same second does not hide the line (a
    line shown too long costs one `order slots`, a line hidden too soon is a lost signal)."""
    found = [
        e
        for e in entries
        if _listed(e) and e.get("type") == "config@1" and e.get("key") == "batch.slots"
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
    entries: list[dict[str, Any]],
    batch: str,
    open_crs: set[str],
    orders: list[Any],
    open_waits: frozenset[tuple[str, str]] = frozenset(),
) -> list[str]:
    """The `status` lines for the Chief of Staff, one per open CR of `batch`: the `merged@1`
    entry that says the PR landed wins, else the first. A `checks-red@1` entry is never listed. A
    line of no published type or with a refused payload is skipped. Then the newest `batch.slots`
    `config@1` line of the batch while no `order slots` is recorded after it; no line for the
    other limit or key. Before them, each `wait-cleared@1` line of the batch whose wait
    (`(cr, wait id)` of `open_waits`) is still open in the record."""
    chosen: dict[str, dict[str, Any]] = {}
    for e in entries:
        cr = e.get("cr")
        if (
            not _listed(e)
            or e.get("type") != "merged@1"
            or e.get("batch") != batch
            or cr not in open_crs
        ):
            continue
        if cr not in chosen or (e.get("landed_with") and not chosen[cr].get("landed_with")):
            chosen[cr] = e
    cleared = [
        wait_cleared_text(e)
        for e in entries
        if _listed(e)
        and e.get("type") == "wait-cleared@1"
        and e.get("batch") == batch
        and (e.get("cr"), e.get("wait")) in open_waits
    ]
    return [
        *(merged_text(e) for e in chosen.values()),
        *cleared,
        *_slots_line(entries, batch, orders),
    ]


# the writer's journal types, and the `writer` states in which each one's episode lasts
_EPISODES = {
    "sync-conflict@1": ("conflict",),
    "sync-blocked@1": ("blocked",),
    "sync-late@1": ("pending", "offline", "blocked", "conflict"),
}


def writer_lines(entries: list[dict[str, Any]], writer: dict[str, Any]) -> list[str]:
    """The newest line of each `sync-*@1` type whose episode lasts: the `writer` entry is still
    in a state of it, so a resolved conflict leaves no line. `sync-resumed@1` is never told."""
    found = []
    for kind, states in _EPISODES.items():
        if writer.get("state") not in states:
            continue
        mine = [e for e in entries if _listed(e) and e.get("type") == kind]
        if mine:
            found.append(max(mine, key=lambda e: (e.get("t") or "", e.get("seq") or 0)))
    return [event_text(e) for e in found]
