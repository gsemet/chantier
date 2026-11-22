"""The Dashboard's figures over the closed batch records, for the `dashboard.get` op. Pure: the
records are the project state's `history` (as `board/state.py:_history` returns it), nothing is
read or written here. One point per closed batch, oldest first; a figure a record lacks is
`None` at its place, never a zero. The client draws the answer and adds the words."""

from __future__ import annotations

from typing import Any

from chantier.board.dashboard_records import (
    closed_records,
    crs_of,
    kept_parts,
    merged_of,
    minutes,
    num,
    ordered,
    point_of,
)
from chantier.board.dashboard_spend import spending

RANGES = {"10": 10, "20": 20, "all": None}


def _covered(values: list[Any]) -> int:
    return sum(v is not None for v in values)


def _rounds_of(rec: dict[str, Any]) -> list[Any]:
    return [c["rounds"] for c in merged_of(rec) if num(c.get("rounds"))]


def _rounds(records: list[dict[str, Any]]) -> dict[str, Any]:
    each = [_rounds_of(r) for r in records]
    values = [sum(r) / len(r) if r else None for r in each]
    every = [n for r in each for n in r]
    mean = sum(every) / len(every) if every else None
    return {"values": values, "covered": _covered(values), "mean": mean}


def _held(rec: dict[str, Any]) -> dict[str, int] | None:
    crs = crs_of(rec)
    return None if crs is None else {"held": len(crs), "merged": len(merged_of(rec))}


def _crs(records: list[dict[str, Any]]) -> dict[str, Any]:
    values = [_held(r) for r in records]
    got = [v for v in values if v is not None]
    return {
        "values": values,
        "covered": len(got),
        "held": sum(v["held"] for v in got) if got else None,
        "merged": sum(v["merged"] for v in got) if got else None,
    }


def _median(got: list[int]) -> int | None:
    """The middle value; an even count: the mean of the two middle ones, a half rounding up."""
    if not got:
        return None
    mid = len(got) // 2
    return got[mid] if len(got) % 2 else (got[mid - 1] + got[mid] + 1) // 2


def _duration(records: list[dict[str, Any]]) -> dict[str, Any]:
    values = [minutes(r) for r in records]
    got = sorted(v for v in values if v is not None)
    return {"values": values, "covered": len(got), "median": _median(got)}


def _calls_of(rec: dict[str, Any]) -> dict[str, Any] | None:
    kept = kept_parts(rec)
    if kept is None or not all(num(p.get("calls")) for p in kept):
        return None
    out: dict[str, Any] = {}
    for p in kept:
        out[p["part"]] = out.get(p["part"], 0) + p["calls"]
    return out


def _calls(records: list[dict[str, Any]]) -> dict[str, Any]:
    values = [_calls_of(r) for r in records]
    got = [v for v in values if v is not None]
    drawn = {part for v in got for part in v}
    total = sum(n for v in got for n in v.values()) if got else None
    return {"parts": ordered(drawn), "values": values, "covered": len(got), "total": total}


def productivity(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "crs": _crs(records),
        "rounds": _rounds(records),
        "duration": _duration(records),
        "calls": _calls(records),
    }


def answer(history: list[Any], range_: str) -> dict[str, Any]:
    """The Dashboard's figures for the range (`"10"`, `"20"` or `"all"`) of closed records."""
    if range_ not in RANGES:
        raise ValueError(f"range {range_!r}: not one of {', '.join(RANGES)}")
    closed = closed_records(history)
    last = RANGES[range_]
    records = closed if last is None else closed[-last:]
    return {
        "range": range_,
        "closed_total": len(closed),
        "total": len(records),
        "points": [point_of(r) for r in records],
        "productivity": productivity(records),
        "spending": spending(records, closed),
    }
