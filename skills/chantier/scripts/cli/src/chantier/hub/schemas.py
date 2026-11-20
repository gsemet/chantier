"""The published types of the project's event journal (`journal.py`): one entry of `PUBLISHED` per
`name@N`, holding its model (the payload of a version 2 line, after `v`, `seq`, `t`, `type`,
`source` and `audience`), its wake rule, its text, its duplicate key and one valid example.

A published `name@N` never changes (its fields, their JSON types, which are required, its
patterns); a change is a new `name@N+1`, published beside it. The shipped `schemas.json` is the
record of each type's JSON Schema: `just journal-schemas` adds the entries it lacks and never
changes one, and `tests/test_event_types.py` fails when a model's normalized schema (`normalize`)
differs from its entry. The CLI validates with the models and never reads `schemas.json` at run
time. A later part adds a type by adding one entry here and running the recipe.

A model fixes each field's JSON type and only the formats that cannot change: a CR id
(`CR-<n>`), a commit SHA (40 or 64 hex characters). The open sets (`board@1.action`,
`config@1.key`, `issue@1.tracker` and `issue@1.event`) are plain strings."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError

LIMITS = ("batch.slots", "specifying.parallel")
SHA_SHOWN = 7
CR_ID = r"^CR-[0-9]+$"
SHA = r"^([0-9a-f]{40}|[0-9a-f]{64})$"

WAIT_ID = r"^w[0-9]+$"

CrId = Annotated[str, StringConstraints(pattern=CR_ID)]
WaitId = Annotated[str, StringConstraints(pattern=WAIT_ID)]
Sha = Annotated[str, StringConstraints(pattern=SHA)]


class _Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Merged1(_Payload):
    batch: str
    cr: CrId
    pr: str
    into: str | None
    into_cr: CrId | None
    merged_at: str | None
    landed_with: CrId | None = None
    landed_at: str | None = None


class ChecksRed1(_Payload):
    batch: str
    cr: CrId
    pr: str
    head: Sha


class Config1(_Payload):
    key: str
    old: str | int | None
    new: str | int | None
    batch: str | None


class Board1(_Payload):
    action: str
    items: list[str]
    text: str
    wakes: bool


class Issue1(_Payload):
    tracker: str
    ref: str
    event: str
    at: str
    text: str
    wakes: bool
    folders: list[str]


class WaitCleared1(_Payload):
    batch: str
    cr: CrId
    wait: WaitId
    wait_type: str
    ref: str
    seen_at: str


def merged_text(e: dict[str, Any]) -> str:
    """The line a `merged@1` event is told by, in `status` and at a watcher's end."""
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


def wait_cleared_text(e: dict[str, Any]) -> str:
    """The line a `wait-cleared@1` event is told by: the forge shows a wait met."""
    ref = str(e.get("ref"))
    if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", ref):
        ref = ref[:SHA_SHOWN]
    return (
        f"forge saw {e.get('wait_type')} met: {e.get('cr')} {e.get('wait')} ({ref}); "
        f"for the steering session: wait {e.get('cr')} clear {e.get('wait')} --epoch <n>, "
        "then take it back"
    )


def config_text(e: dict[str, Any]) -> str:
    """The line a `config@1` event is told by: the limit that changed on the board, and what
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


def issue_text(e: dict[str, Any]) -> str:
    """The line an `issue@1` event is told by: what an outside poller saw on an issue."""
    folders = ", ".join(e.get("folders") or [])
    return (
        f"tracker saw {e.get('event')} on {e.get('ref')} ({folders}): "
        f'"{e.get("text")}"; for the Chief of Staff: tell the user in one line, record nothing'
    )


@dataclass(frozen=True)
class Entry:
    """One published type. `wakes`: True, False, or the name of the payload field whose value
    `True` wakes a watcher. `key`: a function of a line giving what two lines of one event share,
    or None when each line is its own event."""

    model: type[BaseModel]
    wakes: bool | str
    text: Callable[[dict[str, Any]], str]
    key: Callable[[dict[str, Any]], tuple[Any, ...]] | None
    example: dict[str, Any]


PUBLISHED: dict[str, Entry] = {
    "merged@1": Entry(
        Merged1,
        True,
        merged_text,
        lambda e: ("merged", e.get("batch"), e.get("cr"), bool(e.get("landed_with"))),
        {
            "batch": "batch-29",
            "cr": "CR-12",
            "pr": "#88",
            "into": "main",
            "into_cr": None,
            "merged_at": "2026-11-18T10:01:40Z",
        },
    ),
    "checks-red@1": Entry(
        ChecksRed1,
        True,
        red_text,
        lambda e: ("checks-red", e.get("batch"), e.get("cr"), e.get("head")),
        {"batch": "batch-29", "cr": "CR-12", "pr": "#88", "head": "a" * 40},
    ),
    "wait-cleared@1": Entry(
        WaitCleared1,
        True,
        wait_cleared_text,
        lambda e: ("wait-cleared", e.get("batch"), e.get("cr"), e.get("wait")),
        {
            "batch": "batch-29",
            "cr": "CR-3",
            "wait": "w2",
            "wait_type": "pipeline",
            "ref": "3f1c9a0e5b7d2c4a6e8f0b1d3c5a7e9f1b3d5c7a",
            "seen_at": "2026-11-20T10:02:03Z",
        },
    ),
    "config@1": Entry(
        Config1,
        True,
        config_text,
        None,
        {"key": "batch.slots", "old": 3, "new": 4, "batch": "batch-29"},
    ),
    "board@1": Entry(
        Board1,
        "wakes",
        board_text,
        None,
        {"action": "new", "items": ["an-idea"], "text": "new: an idea", "wakes": True},
    ),
    "issue@1": Entry(
        Issue1,
        "wakes",
        issue_text,
        lambda e: ("issue", e.get("ref"), e.get("event"), e.get("at")),
        {
            "tracker": "jira",
            "ref": "https://acme.atlassian.net/browse/PAY-12",
            "event": "commented",
            "at": "2026-11-20T09:14:00Z",
            "text": "a comment asks to keep the old column order",
            "wakes": True,
            "folders": ["2-backlog/P2/export-columns"],
        },
    ),
}


def check(type_: Any, payload: dict[str, Any]) -> str | None:
    """Why the payload is not one of the type (the message, starting `journal `), else None."""
    entry = PUBLISHED.get(type_) if isinstance(type_, str) else None
    if entry is None:
        return f"journal type {type_!r}: one of {', '.join(PUBLISHED)}"
    try:
        entry.model.model_validate(payload)
    except ValidationError as e:
        first = e.errors()[0]
        where = ".".join(str(p) for p in first["loc"])
        return f"journal payload {type_}: {where + ': ' if where else ''}{first['msg']}"
    return None


def validate(type_: str, payload: dict[str, Any]) -> None:
    """Check a payload against its type's model; `ValueError` on a type not published or a
    payload its model refuses (an extra field, a missing required field, a wrong JSON type)."""
    why = check(type_, payload)
    if why:
        raise ValueError(why)


def _shape(schema: dict[str, Any]) -> dict[str, Any]:
    """The normalized form of one property: its JSON types (null included), its pattern when it
    has one, and for an array the same of its items."""
    types: set[str] = set()
    patterns: set[str] = set()
    items: dict[str, Any] | None = None
    for b in schema.get("anyOf", [schema]):
        types.add(b["type"])
        if "pattern" in b:
            patterns.add(b["pattern"])
        if "items" in b:
            items = _shape(b["items"])
    out: dict[str, Any] = {"types": sorted(types)}
    if patterns:
        out["pattern"] = sorted(patterns)
    if items is not None:
        out["items"] = items
    return out


def normalize(schema: dict[str, Any]) -> dict[str, Any]:
    """What the test and the recipe compare: for each property its JSON types, pattern and items,
    and the set of required properties. Titles, descriptions, `$defs`, the order of keys and of
    `anyOf` branches, and any other output of the generator are not part of it."""
    return {
        "properties": {k: _shape(v) for k, v in sorted(schema.get("properties", {}).items())},
        "required": sorted(schema.get("required", [])),
    }


def canonical(schemas: dict[str, Any]) -> str:
    """The text of `schemas.json`: keys sorted, UTF-8 (no escapes), LF, a final newline."""
    return json.dumps(schemas, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def merge(shipped: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """The recipe's merge: `shipped` (the file's entries) plus the schema of every published
    type it lacks; an existing entry is kept as it is. The merged entries and the messages: one
    `schemas.json: added <type>` per entry added, one `... differs from its model ...` per
    existing entry whose normalized form is not its model's."""
    merged = dict(shipped)
    said: list[str] = []
    for name, entry in PUBLISHED.items():
        schema = entry.model.model_json_schema()
        base, _, number = name.partition("@")
        if name not in merged:
            merged[name] = schema
            said.append(f"schemas.json: added {name}")
        elif normalize(merged[name]) != normalize(schema):
            said.append(
                f"schemas.json: {name} differs from its model: publish "
                f"{base}@{int(number) + 1} instead"
            )
    return merged, said
