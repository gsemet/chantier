"""A CR's typed waits: what it waits for, as a fact the record keeps.

A wait is one JSON object (`make`): `id` (`w1`, `w2`, ...), `type` (one of `TYPES`), `ref`, `link`,
`since`, `note`, `cleared_at`, `cleared_by`. In a batch the waits are the CR entry's `waits`; in the
backlog they are the CR folder's `waits.json` (`{"schema": 1, "waits": [...]}`). A wait changes no
rule: it is a fact that `status`, `handoff`, the board and the forge hub read."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from chantier.core.clock import now
from chantier.core.files import rel_in

if TYPE_CHECKING:
    from chantier.store import PlanStore

TYPES = ("answer", "approval", "pipeline", "merge")
FORGE_TYPES = ("approval", "pipeline", "merge")  # the waits that name a PR or MR
FILE = "waits.json"
SCHEMA = 1
ID = re.compile(r"w([0-9]+)")
FULL_SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
PREFIX_SHA = re.compile(r"[0-9a-f]{7,64}")
FIELDS = ("id", "type", "ref", "link", "since", "note", "cleared_at", "cleared_by")
TEXTS = ("ref", "since", "note")
OPTIONAL_TEXTS = ("link", "cleared_at", "cleared_by")
# A CR the record holds merged, dropped or cancelled: no wait counts. A dropped CR is recorded
# `cancelled` (`order drop`, `cancel`), so these two statuses name all three.
ENDED = ("merged", "cancelled")


class WaitsInvalid(ValueError):
    """A `waits.json` that is not of the form chantier writes."""


def _wait_problem(where: str, w: object, seen: set[str]) -> str | None:
    """Why one wait of the list is not valid, else None; `seen` holds the ids met so far."""
    if not isinstance(w, dict):
        return f"{where} is not an object"
    if not isinstance(w.get("id"), str) or not ID.fullmatch(w["id"]):
        return f"{where}.id is not w<n>"
    if w["id"] in seen:
        return f"{where}.id {w['id']} is repeated"
    seen.add(w["id"])
    if w.get("type") not in TYPES:
        return f"{where}.type is not {', '.join(TYPES)}"
    bad = [n for n in TEXTS if not isinstance(w.get(n), str)]
    if bad:
        return f"{where}.{bad[0]} is not a string"
    bad = [n for n in OPTIONAL_TEXTS if not (w.get(n) is None or isinstance(w[n], str))]
    return f"{where}.{bad[0]} is not a string or null" if bad else None


def problem(data: object) -> str | None:
    """Why `data` is not a `waits.json`'s content, else None."""
    if not isinstance(data, dict):
        return "not a JSON object"
    if data.get("schema") != SCHEMA:
        return f"schema is not {SCHEMA}"
    found = data.get("waits")
    if not isinstance(found, list):
        return "waits is not a list"
    seen: set[str] = set()
    for i, w in enumerate(found):
        if why := _wait_problem(f"waits[{i}]", w, seen):
            return why
    return None


def read_file(store: PlanStore, folder: Path) -> list[dict[str, Any]] | None:
    """The waits of `<folder>/waits.json`; None when there is no file; `WaitsInvalid` when it is
    not valid."""
    rel = rel_in(store.root, folder / FILE)
    if not store.is_file(rel):
        return None
    try:
        data = json.loads(store.read_text(rel))
    except (OSError, ValueError) as e:
        raise WaitsInvalid(" ".join(str(e).split())) from e
    why = problem(data)
    if why:
        raise WaitsInvalid(why)
    return [dict(w) for w in data["waits"]]


def file_text(waits: list[dict[str, Any]]) -> str:
    """The content of a `waits.json`."""
    return json.dumps({"schema": SCHEMA, "waits": waits}, indent=2, ensure_ascii=False) + "\n"


def is_open(w: dict[str, Any]) -> bool:
    return w.get("cleared_at") is None


def open_of(waits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [w for w in waits if is_open(w)]


def counted(status: str) -> bool:
    """Whether the waits of a CR in this status count (a merged, dropped or cancelled CR's do
    not)."""
    return status not in ENDED


def next_id(*lists: list[dict[str, Any]]) -> str:
    """The id after the highest one of the lists."""
    highest = 0
    for waits in lists:
        for w in waits:
            m = ID.fullmatch(str(w.get("id")))
            highest = max(highest, int(m[1]) if m else 0)
    return f"w{highest + 1}"


def make(wait_id: str, type_: str, ref: str, link: str | None, note: str) -> dict[str, Any]:
    """A new open wait, since now."""
    return {
        "id": wait_id,
        "type": type_,
        "ref": ref,
        "link": link,
        "since": now(),
        "note": note,
        "cleared_at": None,
        "cleared_by": None,
    }


def carried(
    record: list[dict[str, Any]] | None, found: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """The waits of a CR that joins a batch from the backlog. A new entry (`record` None) takes
    the file's open waits; the held entry keeps its own list and takes the file's waits whose ids
    it lacks."""
    if record is None:
        return [w for w in found if is_open(w)]
    have = {w["id"] for w in record}
    return [*record, *(w for w in found if w["id"] not in have)]


def short(sha: str, width: int = 7) -> str:
    return sha[:width]


def hhmm(since: str) -> str:
    """`HH:MM` (UTC) of a record time (`2026-11-20T10:02:03Z`)."""
    return since[11:16]
