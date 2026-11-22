"""What needs the user: one list per project, built from the facts the board already reads (a batch
row's open waits, state and readiness, a backlog item's open waits, the seat), read-only. The web
board's Inbox page draws it; nothing here reads or writes a file."""

from __future__ import annotations

from typing import Any

KINDS = ("question", "approval", "merge", "blocked")
_FIELDS = ("pr", "text", "note", "session", "merge_place", "merge_total")


def _entry(
    kind: str, who: dict[str, Any], since: str | None, key: str, **more: Any
) -> dict[str, Any]:
    """One entry of `who`, a batch row or a backlog item; `key` names one occurrence of its fact."""
    out: dict[str, Any] = {
        "key": key,
        "kind": kind,
        "cr": who.get("cr"),
        "item": who.get("item"),
        "title": who["title"],
        "folder": who.get("folder"),
        "since": since,
    }
    return out | {f: more.get(f) for f in _FIELDS}


def _waits(
    who: dict[str, Any], owner: str, session: str | None, pr: str | None
) -> list[dict[str, Any]]:
    """The entries of the open `answer` and `approval` waits of a row or an item."""
    out: list[dict[str, Any]] = []
    for w in who.get("open_waits") or []:
        since = w.get("since")
        tail = f"{owner}:{w['id']}:{since or ''}"
        if w["type"] == "answer":
            more = {"text": w.get("ref"), "note": w.get("note"), "session": session}
            out.append(_entry("question", who, since, f"question:{tail}", **more))
        elif w["type"] == "approval":
            more = {"pr": w.get("link") or pr, "text": w.get("note") or None}
            out.append(_entry("approval", who, since, f"approval:{tail}", **more))
    return out


def _of_row(row: dict[str, Any], order: list[str], session: str | None) -> list[dict[str, Any]]:
    cr = row["cr"]
    out = _waits(row, cr, session, row.get("pr"))
    state_at = (row.get("times") or {}).get("state_at")
    if row.get("to_review"):  # never `updated`: any touch of the record moves it
        since = state_at or row.get("handed_back_at")
        place = order.index(cr) + 1 if cr in order else None
        out.append(
            _entry(
                "merge",
                row,
                since,
                f"merge:{cr}:{since or ''}",
                pr=row.get("pr"),
                merge_place=place,
                merge_total=len(order),
            )
        )
    if row.get("state") == "blocked":
        reason = row.get("blocked")
        out.append(_entry("blocked", row, state_at, f"blocked:{cr}:{state_at or ''}", text=reason))
    return out


def _order(e: dict[str, Any]) -> tuple[int, str, str]:
    """Newest `since` first (ISO times compare as text), an entry with none last, then by key."""
    since = e["since"]
    inverted = "".join(chr(0x10FFFF - ord(c)) for c in since) if since else ""
    return (0 if since else 1, inverted, e["key"])


def needs_you(state: dict[str, Any]) -> list[dict[str, Any]]:
    """The entries of what needs the user in a project's state, newest first."""
    seat = state.get("seat")
    session = seat["title"] if seat else None
    batch = state.get("batch") or {"crs": [], "merge_order": []}
    out: list[dict[str, Any]] = []
    for row in batch["crs"]:
        out += _of_row(row, batch["merge_order"], session)
    for items in (state.get("backlog") or {}).values():
        for item in items:
            out += _waits(item, f"i:{item['item']}", session, None)
    return sorted(out, key=_order)
