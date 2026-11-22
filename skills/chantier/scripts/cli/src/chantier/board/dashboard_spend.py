"""The Dashboard's Spending figures (cost per merged CR, spend per batch by part and by model, the
cost outside the batches, the most expensive CRs). Pure, over the records `dashboard_page`
selects; a figure a record lacks is `None`, never a zero."""

from __future__ import annotations

from typing import Any

from chantier.board.dashboard_records import (
    crs_of,
    kept_parts,
    merged_of,
    num,
    number_of,
    ordered,
    point_of,
    receipt_of,
    unpriced,
)

PALETTE, TOP, HALF_CENT = 8, 10, 0.005


def _entries(rec: dict[str, Any]) -> list[tuple[str, float]]:
    """The `(model id, usd)` of each entry of `cost_receipt.models` that holds both."""
    models = receipt_of(rec).get("models")
    if not isinstance(models, list):
        return []
    return [
        (m["model"], m["usd"])
        for m in models
        if isinstance(m, dict) and isinstance(m.get("model"), str) and num(m.get("usd"))
    ]


def rank(closed: list[dict[str, Any]]) -> list[tuple[str, list[str]]]:
    """The series keys, in rank order, with the model ids each holds: the models ranked by
    their summed cost over all the closed records of the project, then by id. With at most
    eight, `m1`...; with more, the first seven keep theirs and the rest fold into `other`."""
    sums: dict[str, float] = {}
    for rec in closed:
        for model, usd in _entries(rec):
            sums[model] = sums.get(model, 0) + usd
    ids = sorted(sums, key=lambda m: (-sums[m], m))
    if len(ids) <= PALETTE:
        return [(f"m{i}", [m]) for i, m in enumerate(ids, 1)]
    return [(f"m{i}", [m]) for i, m in enumerate(ids[: PALETTE - 1], 1)] + [
        ("other", ids[PALETTE - 1 :])
    ]


def _by_role(rec: dict[str, Any]) -> dict[str, float]:
    kept = kept_parts(rec)
    if kept is None or not all(num(p.get("usd")) for p in kept):
        return {}
    out: dict[str, float] = {}
    for p in kept:
        out[p["part"]] = out.get(p["part"], 0) + p["usd"]
    return out


def _by_model(rec: dict[str, Any], key_of: dict[str, str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for model, usd in _entries(rec):
        out[key_of[model]] = out.get(key_of[model], 0) + usd
    return out


def _segments(rec: dict[str, Any], segments: dict[str, float]) -> dict[str, float] | None:
    """The record's bar: its segments, the rest as `unsplit` (the whole cost when it has no
    split), and `None` with no number `cost_usd`."""
    if not num(rec.get("cost_usd")):
        return None
    cost: float = rec["cost_usd"]
    rest = cost - sum(segments.values())
    if not segments or rest >= HALF_CENT:
        return {**segments, "unsplit": rest if segments else cost}
    return segments


def _drawn(values: list[dict[str, float] | None]) -> set[str]:
    return {k for v in values if v is not None for k in v}


def _split(records: list[dict[str, Any]], rank_: list[tuple[str, list[str]]]) -> dict[str, Any]:
    key_of = {m: key for key, models in rank_ for m in models}
    role = [_segments(r, _by_role(r)) for r in records]
    model = [_segments(r, _by_model(r, key_of)) for r in records]
    drawn = _drawn(model)
    series = [{"key": k, "models": models} for k, models in rank_ if k in drawn]
    if "unsplit" in drawn:
        series.append({"key": "unsplit", "models": []})
    drawn_roles = _drawn(role) - {"unsplit"}
    keys = ordered(drawn_roles) + (["unsplit"] if "unsplit" in _drawn(role) else [])
    return {
        "role": {"series": keys, "values": role},
        "model": {"series": series, "values": model},
    }


def _spend(records: list[dict[str, Any]], rank_: list[tuple[str, list[str]]]) -> dict[str, Any]:
    got = [r for r in records if num(r.get("cost_usd"))]
    return {
        **_split(records, rank_),
        "total": sum(r["cost_usd"] for r in got) if got else None,
        "covered": len(got),
        "unpriced": any(unpriced(r) for r in got),
    }


def _per_cr(records: list[dict[str, Any]]) -> dict[str, Any]:
    values = [
        r["cost_usd"] / len(merged_of(r)) if num(r.get("cost_usd")) and merged_of(r) else None
        for r in records
    ]
    got = [r for r, v in zip(records, values, strict=True) if v is not None]
    cost = sum(r["cost_usd"] for r in got)
    merged = sum(len(merged_of(r)) for r in got)
    return {
        "values": values,
        "covered": len(got),
        "cost": cost if got else None,
        "merged": merged if got else None,
        "ratio": cost / merged if got else None,
        "unpriced": any(unpriced(r) for r in got),
    }


def _outside_of(rec: dict[str, Any]) -> list[dict[str, Any]] | None:
    """The grill's and the steering's parts outside the batch (`receipt.js:outsideOf`):
    `None` when the record holds none, or a part without a number `usd`."""
    out = receipt_of(rec).get("outside")
    if not isinstance(out, dict):
        return None
    parts = [out[k] for k in ("grill", "steering") if k in out and out[k] is not None]
    if not parts or not all(isinstance(p, dict) and num(p.get("usd")) for p in parts):
        return None
    return parts


def _outside(records: list[dict[str, Any]]) -> dict[str, Any]:
    got = [p for p in (_outside_of(r) for r in records) if p is not None]
    return {
        "usd": sum(part["usd"] for parts in got for part in parts) if got else None,
        "covered": len(got),
        "unpriced": any(unpriced(part, "unpriced") for parts in got for part in parts),
    }


def _row(rec: dict[str, Any], cr: dict[str, Any]) -> dict[str, Any]:
    title, rounds, pr = cr.get("title"), cr.get("rounds"), cr.get("pr")
    return {
        "cr": cr["cr"],
        "title": title if isinstance(title, str) else None,
        "batch": point_of(rec)["batch"],
        "rounds": rounds if num(rounds) else None,
        "cost_usd": cr["cost_usd"],
        "unpriced": unpriced(cr),
        "pr": pr if isinstance(pr, str) else None,
    }


def _costed(rec: dict[str, Any]) -> list[dict[str, Any]]:
    crs = crs_of(rec) or []
    return [
        c
        for c in crs
        if isinstance(c, dict) and isinstance(c.get("cr"), str) and num(c.get("cost_usd"))
    ]


def _top(records: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [(r, c) for r in records for c in _costed(r)]
    rows.sort(key=lambda rc: (-rc[1]["cost_usd"], -number_of(rc[0]), rc[1]["cr"]))
    return {
        "rows": [_row(r, c) for r, c in rows[:TOP]],
        "covered": sum(bool(_costed(r)) for r in records),
    }


def spending(records: list[dict[str, Any]], closed: list[dict[str, Any]]) -> dict[str, Any]:
    """The Spending tab over the range's `records`; the model rank is over all `closed`."""
    return {
        "per_cr": _per_cr(records),
        "spend": _spend(records, rank(closed)),
        "outside": _outside(records),
        "top": _top(records),
    }
