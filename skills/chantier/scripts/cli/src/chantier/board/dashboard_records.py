"""What the Dashboard reads of a closed batch record, one checked read per figure. Pure: no file,
no forge, no journal. A value of the wrong type or a key that is missing is `None` (or an empty
list), never an error and never a zero: a record whose shape changes shows less, not a wrong
number."""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any

AGENT_PARTS = ("steering", "drivers", "workers", "agents")


def num(value: Any) -> bool:
    """A number is an `int` or a `float` and not a `bool`."""
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def number_of(rec: dict[str, Any]) -> int:
    """The record's order: its `number` when an `int`, else the digits of its `batch`."""
    n = rec.get("number")
    if isinstance(n, int) and not isinstance(n, bool):
        return n
    found = re.search(r"(\d+)", rec["batch"]) if isinstance(rec.get("batch"), str) else None
    return int(found[1]) if found else 0


def closed_records(history: list[Any]) -> list[dict[str, Any]]:
    """The closed batch records (a running, paused or stale one is out), oldest first."""
    closed = [r for r in history if isinstance(r, dict) and r.get("state") == "closed"]
    return sorted(closed, key=number_of)


def unpriced(entry: Any, key: str = "cost_unpriced") -> bool:
    """True when the entry's `cost_unpriced` (or `key`) is a non-empty dict
    (`history.js:hasUnpriced`)."""
    flag = entry.get(key) if isinstance(entry, dict) else None
    return isinstance(flag, dict) and bool(flag)


def point_of(rec: dict[str, Any]) -> dict[str, Any]:
    closed = rec.get("closed")
    return {
        "batch": rec.get("batch") if isinstance(rec.get("batch"), str) else None,
        "n": number_of(rec),
        "closed": closed if isinstance(closed, str) else None,
        "unpriced": unpriced(rec),
    }


def crs_of(rec: dict[str, Any]) -> list[Any] | None:
    crs = rec.get("crs")
    return crs if isinstance(crs, list) else None


def merged_of(rec: dict[str, Any]) -> list[dict[str, Any]]:
    return [c for c in crs_of(rec) or [] if isinstance(c, dict) and c.get("result") == "merged"]


def receipt_of(rec: dict[str, Any]) -> dict[str, Any]:
    receipt = rec.get("cost_receipt")
    return receipt if isinstance(receipt, dict) else {}


def kept_parts(rec: dict[str, Any]) -> list[dict[str, Any]] | None:
    """The split's entries that are drawn: when the split has an `agents` part, it stands in
    place of `drivers` and `workers` (the Costs card's own rule). `None` when
    the split is not a non-empty list of dicts that each hold a str `part`."""
    split = receipt_of(rec).get("split")
    if not isinstance(split, list) or not split:
        return None
    if not all(isinstance(p, dict) and isinstance(p.get("part"), str) for p in split):
        return None
    agents = any(p["part"] == "agents" for p in split)
    return [p for p in split if not agents or p["part"] not in ("drivers", "workers")]


def ordered(keys: set[str]) -> list[str]:
    """The parts in the fixed order, any other part after them."""
    first = [k for k in AGENT_PARTS if k in keys]
    return first + sorted(keys - set(first))


def minutes(rec: dict[str, Any]) -> int | None:
    """The whole minutes from `opened` to `closed`, as `receipt.js:minutesOf`
    (`Math.max(0, Math.round(span / 60000))`): a half minute rounds up, as `Math.round` does
    and Python's `round` does not."""
    opened, closed = rec.get("opened"), rec.get("closed")
    if not isinstance(opened, str) or not isinstance(closed, str):
        return None
    try:
        seconds = (datetime.fromisoformat(closed) - datetime.fromisoformat(opened)).total_seconds()
    except (ValueError, TypeError):
        return None
    return max(0, math.floor(seconds / 60 + 0.5))
