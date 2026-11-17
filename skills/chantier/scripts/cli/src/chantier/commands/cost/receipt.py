"""The figures of the web board's cost receipt, as data: what `cost_summary` and `chief_line`
print as text, from the same priced rows."""

from __future__ import annotations

from typing import Any

from chantier.commands.cost.breakdown import _steers, breakdown, split_parts, wake_figures
from chantier.commands.cost.pricing import sum_unpriced
from chantier.commands.cost.sessions import _Chief, chief_outside
from chantier.core.records import BatchRecord


def cost_receipt(
    d: BatchRecord,
    rows: list[dict[str, Any]],
    by_driver: dict[str, list[Any]],
    chief: _Chief | str,
) -> dict[str, Any]:
    """Steering, Drivers, the split and what is outside the budget. `split` adds up to the
    rows' total in cents. `drivers` is empty where a Driver cannot be told from a worker (no
    parent link). `chief` is `chief_read`'s: a string (the cause) when the Chief of Staff's
    session cannot be measured, then `outside` is `None` beside `outside_unknown`."""
    total = sum(r["usd"] for r in rows)
    un = sum_unpriced(rows)
    mains = [r for r in rows if r["agent"] == "main"]
    steer = _steers(mains)
    measured = all("parent" in r for r in rows if r["agent"] != "main")
    parts = split_parts(rows, steer, total, un)
    foreman = [e for e in breakdown(rows) if e["kind"] == "Foreman"]
    line = next((p for p in parts if p["part"] == "steering"), None)
    wakes = wake_figures(mains)
    return {
        "steering": {
            "label": steer,
            "usd": line["usd"] if line else 0.0,
            "calls": sum(e["calls"] for e in foreman),
            "unpriced": line["unpriced"] if line else {},
            "wakes": wakes["wakes"] if wakes else 0,
            "context_avg": wakes["context_avg"] if wakes else None,
        },
        "drivers": [
            {"type": k, "usd": round(v[1], 4), "calls": v[0], "unpriced": v[2]}
            for k, v in sorted(by_driver.items(), key=lambda kv: -kv[1][1])
            if k != "foreman" and measured
        ],
        "split": [{"part": p["part"], "usd": p["usd"], "unpriced": p["unpriced"]} for p in parts],
        **chief_outside(d, chief),
    }
