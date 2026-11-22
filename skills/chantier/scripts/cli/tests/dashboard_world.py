"""Prepared batch records for the Dashboard's figures, with batch-29's keys and types: `split` a
list of `{part, usd, calls, unpriced: {}}`, `models` a list of `{model, calls, usd, unpriced: 0}`,
`outside` a dict of `{grill, steering}` each `{usd, calls, unpriced: {}}`, instants with seconds
and a `Z`. `batch29()` is batch-29's own record, copied verbatim from the planning surface's
`5-archives/batches/batch-29.json` (`dashboard_batch29.json`)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

OPENED, CLOSED = "2026-11-18T10:00:00Z", "2026-11-18T11:00:00Z"


def batch29() -> dict[str, Any]:
    record: dict[str, Any] = json.loads(
        (Path(__file__).parent / "dashboard_batch29.json").read_text(encoding="utf-8")
    )
    return record


def cr(
    ident: int, result: str = "merged", rounds: Any = 1, cost: Any = 1.0, **more: Any
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "cr": f"CR-{ident}",
        "title": f"title {ident}",
        "result": result,
        "cost_usd": cost,
        "cost_unpriced": {},
        **more,
    }
    if rounds is not None:
        out["rounds"] = rounds
    return out


def part(name: str, usd: float, calls: int | None = 10) -> dict[str, Any]:
    out: dict[str, Any] = {"part": name, "usd": usd, "unpriced": {}}
    if calls is not None:
        out["calls"] = calls
    return out


def model(name: str, usd: float, calls: int = 5) -> dict[str, Any]:
    return {"model": name, "calls": calls, "usd": usd, "unpriced": 0}


def side(grill: float | None = None, steering: float | None = None) -> dict[str, Any]:
    return {
        k: {"usd": usd, "calls": 3, "unpriced": {}}
        for k, usd in (("grill", grill), ("steering", steering))
        if usd is not None
    }


def rec(  # noqa: PLR0913, PLR0917 - one record is one keyword list
    n: int,
    crs: Any = (),
    cost: Any = None,
    split: Any = None,
    models: Any = None,
    outside: Any = None,
    opened: Any = OPENED,
    closed: Any = CLOSED,
    state: str = "closed",
    **more: Any,
) -> dict[str, Any]:
    """A record; `split`, `models` and `outside` (each `None` for none) make its `cost_receipt`."""
    out: dict[str, Any] = {
        "schema": 1,
        "batch": f"batch-{n:02d}",
        "number": n,
        "state": state,
        "opened": opened,
        "closed": closed,
        "cost_usd": cost,
        "cost_unpriced": {},
        "crs": list(crs) if isinstance(crs, tuple | list) else crs,
        **more,
    }
    receipt = {
        k: v
        for k, v in (("split", split), ("models", models), ("outside", outside))
        if v is not None
    }
    if receipt:
        out["cost_receipt"] = receipt
    return out


def old(n: int, crs: Any) -> dict[str, Any]:
    """A back-filled record (batch-01 to batch-16): no `opened`, no `closed`, no batch cost."""
    out = rec(n, crs, opened=None, closed=None)
    del out["opened"]
    return out
