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
    number_of,
    ordered,
    point_of,
)
from chantier.board.dashboard_spend import spending

RANGES = {"10": 10, "20": 20, "all": None}


def _covered(values: list[Any]) -> int:
    return sum(v is not None for v in values)


def _rounds_of(rec: dict[str, Any]) -> list[Any]:
    return [c["rounds"] for c in merged_of(rec) if num(c.get("rounds"))]


def _rounds(groups: list[list[dict[str, Any]]]) -> dict[str, Any]:
    """The mean of the merged CRs' rounds at each point, pooled over the point's records."""
    each = [[n for r in g for n in _rounds_of(r)] for g in groups]
    values = [sum(r) / len(r) if r else None for r in each]
    every = [n for r in each for n in r]
    mean = sum(every) / len(every) if every else None
    return {"values": values, "covered": _covered(values), "mean": mean}


def _held(rec: dict[str, Any]) -> dict[str, int] | None:
    crs = crs_of(rec)
    return None if crs is None else {"held": len(crs), "merged": len(merged_of(rec))}


def _held_of(group: list[dict[str, Any]]) -> dict[str, int] | None:
    got = [v for v in (_held(r) for r in group) if v is not None]
    if not got:
        return None
    return {"held": sum(v["held"] for v in got), "merged": sum(v["merged"] for v in got)}


def _crs(groups: list[list[dict[str, Any]]]) -> dict[str, Any]:
    values = [_held_of(g) for g in groups]
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


def _mean_of(group: list[dict[str, Any]]) -> int | None:
    """The mean of the point's durations, a half rounding up (a single one is itself)."""
    got = [m for m in (minutes(r) for r in group) if m is not None]
    return (2 * sum(got) + len(got)) // (2 * len(got)) if got else None


def _duration(groups: list[list[dict[str, Any]]]) -> dict[str, Any]:
    """A point is the mean of its records' durations; the headline is the median over all the
    records' durations of the range."""
    values = [_mean_of(g) for g in groups]
    every = sorted(m for g in groups for m in (minutes(r) for r in g) if m is not None)
    return {"values": values, "covered": _covered(values), "median": _median(every)}


def _calls_of(rec: dict[str, Any]) -> dict[str, Any] | None:
    kept = kept_parts(rec)
    if kept is None or not all(num(p.get("calls")) for p in kept):
        return None
    out: dict[str, Any] = {}
    for p in kept:
        out[p["part"]] = out.get(p["part"], 0) + p["calls"]
    return out


def _calls_at(group: list[dict[str, Any]]) -> dict[str, Any] | None:
    got = [v for v in (_calls_of(r) for r in group) if v is not None]
    if not got:
        return None
    out: dict[str, Any] = {}
    for v in got:
        for part, n in v.items():
            out[part] = out.get(part, 0) + n
    return out


def _calls(groups: list[list[dict[str, Any]]]) -> dict[str, Any]:
    values = [_calls_at(g) for g in groups]
    got = [v for v in values if v is not None]
    drawn = {part for v in got for part in v}
    total = sum(n for v in got for n in v.values()) if got else None
    return {"parts": ordered(drawn), "values": values, "covered": len(got), "total": total}


def productivity(groups: list[list[dict[str, Any]]]) -> dict[str, Any]:
    """The Productivity tab over the points: each is a group of the records of one batch number
    (one record for a project)."""
    return {
        "crs": _crs(groups),
        "rounds": _rounds(groups),
        "duration": _duration(groups),
        "calls": _calls(groups),
    }


def _point(group: list[dict[str, Any]]) -> dict[str, Any]:
    """A project's point is its record's; a point of several records names its batch, shows a day
    only when every record closed on that one day, and counts the projects it covers."""
    if len(group) == 1 and "_project" not in group[0]:
        return point_of(group[0])
    points = [point_of(r) for r in group]
    days = {p["closed"][:10] if p["closed"] else None for p in points}
    named = next((p["batch"] for p in points if p["batch"]), None)
    return {
        "batch": named,
        "n": points[0]["n"],
        "closed": points[0]["closed"] if len(days) == 1 and None not in days else None,
        "unpriced": any(p["unpriced"] for p in points),
        "projects": len({r.get("_project") for r in group}),
    }


def _answer(groups: list[list[dict[str, Any]]], range_: str) -> dict[str, Any]:
    last = RANGES[range_]
    shown = groups if last is None else groups[-last:]
    closed = [r for g in groups for r in g]
    return {
        "range": range_,
        "closed_total": len(groups),
        "total": len(shown),
        "points": [_point(g) for g in shown],
        "productivity": productivity(shown),
        "spending": spending(shown, closed),
    }


def _checked(range_: str) -> None:
    if range_ not in RANGES:
        raise ValueError(f"range {range_!r}: not one of {', '.join(RANGES)}")


def answer(history: list[Any], range_: str) -> dict[str, Any]:
    """The Dashboard's figures for the range (`"10"`, `"20"` or `"all"`) of closed records."""
    _checked(range_)
    return _answer([[r] for r in closed_records(history)], range_)


def answer_all(histories: dict[str, list[Any]], range_: str) -> dict[str, Any]:
    """The same figures for every project at once: a point is a batch number, summed over the
    projects' closed records of that number."""
    _checked(range_)
    by_number: dict[int, list[dict[str, Any]]] = {}
    for project, history in histories.items():
        for rec in closed_records(history):
            by_number.setdefault(number_of(rec), []).append({**rec, "_project": project})
    return _answer([by_number[n] for n in sorted(by_number)], range_)
