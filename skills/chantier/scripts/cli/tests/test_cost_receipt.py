"""The receipt's figures (`cost_receipt`, `chief_outside`) on prepared rows, and the text lines
`cost_summary` prints from the same data."""

from __future__ import annotations

from typing import Any

import pytest

from chantier.commands.cost.breakdown import cost_summary
from chantier.commands.cost.receipt import cost_receipt
from chantier.commands.cost.sessions import _Chief, _Part, chief_outside
from chantier.core.records import BatchRecord


def row(agent: str, kind: str, usd: float, calls: int, **fields: Any) -> dict[str, Any]:
    base = {"agent": agent, "type": kind, "usd": usd, "calls": calls, "unpriced": {}}
    return {**base, **fields}


def main(usd: float = 15.99, **fields: Any) -> dict[str, Any]:
    wake = {"wakes": 4, "wake_context": 400, "peak_context": 900, "grill": None}
    return row("main", "chief-of-staff", usd, 10, **{**wake, **fields})


DRIVERS = [
    row("d1", "cr-driver", 10.01, 5, parent=None),
    row("d2", "cr-reviewer", 5.33, 2, parent=None),
    row("w1", "coder", 30.46, 9, parent="d1"),
]
BY_DRIVER = {"cr-driver": [14, 33.01, {}], "cr-reviewer": [2, 5.33, {}], "foreman": [10, 15.99, {}]}


def chief(*, steer: int = 3, inside: int = 0) -> _Chief:
    return _Chief(
        steer=_Part(steer, 2.5, {}),
        grill=_Part(93, 5.1, {}),
        inside_calls=inside,
        untimed=0,
    )


def record(steering: str) -> BatchRecord:
    return BatchRecord(id="batch-01", host="claude", steering=steering, budget_usd=100)


def total_cents(rows: list[dict[str, Any]]) -> int:
    total: float = sum(r["usd"] for r in rows)
    return round(total * 100)


@pytest.mark.parametrize("rows", [[main(), *DRIVERS], [main(15.994), *DRIVERS]])
def test_the_split_adds_up_in_cents_with_steering_wakes_and_drivers_by_cost(
    rows: list[dict[str, Any]],
) -> None:
    got = cost_receipt(record("direct"), rows, BY_DRIVER, chief())
    assert [p["part"] for p in got["split"]] == ["steering", "drivers", "workers"]
    assert sum(round(p["usd"] * 100) for p in got["split"]) == total_cents(rows)
    assert got["steering"]["wakes"] == 4 and got["steering"]["context_avg"] == 100  # noqa: PLR2004
    assert got["steering"]["label"] == "Chief of Staff, steering the batch"
    assert [d["type"] for d in got["drivers"]] == ["cr-driver", "cr-reviewer"]
    assert got["drivers"][0] == {"type": "cr-driver", "usd": 33.01, "calls": 14, "unpriced": {}}


def test_with_no_parent_link_no_driver_line_and_an_agents_part() -> None:
    agents = [main(), row("a1", "coder", 4.0, 3), row("a2", "cr-driver", 2.0, 1)]
    got = cost_receipt(record("direct"), agents, BY_DRIVER, chief())
    assert got["drivers"] == []
    assert [p["part"] for p in got["split"]] == ["steering", "drivers", "workers", "agents"]
    assert sum(round(p["usd"] * 100) for p in got["split"]) == total_cents(agents)


@pytest.mark.parametrize(
    ("steering", "read", "steering_part"),
    [
        ("direct", chief(inside=4, steer=0), None),
        ("foreman", chief(), {"usd": 2.5, "calls": 3, "unpriced": {}}),
        ("foreman", chief(inside=4), {"usd": 2.5, "calls": 3, "unpriced": {}}),
    ],
)
def test_the_steering_is_outside_the_budget_in_a_foreman_batch_only(
    steering: str, read: _Chief, steering_part: dict[str, Any] | None
) -> None:
    got = chief_outside(record(steering), read)
    assert got["outside"]["grill"] == {"usd": 5.1, "calls": 93, "unpriced": {}}
    assert got["outside"]["steering"] == steering_part
    assert "outside_unknown" not in got


def test_a_chief_of_staff_that_cannot_be_measured_is_null_with_its_cause_never_zero() -> None:
    got = cost_receipt(record("direct"), [main(), *DRIVERS], BY_DRIVER, "not measured on this host")
    assert got["outside"] is None and got["outside_unknown"] == "not measured on this host"
    assert "outside" not in str(got["steering"])


def test_the_text_lines_are_the_ones_printed_before_the_receipt() -> None:
    rows = [main(15.99), *DRIVERS]
    by_cr = {"CR-1": [16, 43.0, {}], "foreman": [10, 15.99, {}]}
    lines = cost_summary(record("foreman"), rows, by_cr, BY_DRIVER, ["a chief line"])
    assert lines == [
        "Total: $61.79 of a $100 budget",
        "Chief of Staff, steering the batch $15.99 (26%), Drivers $15.34 (25%), "
        "workers $30.46 (49%)",
        "Most: CR-1 $43.00",
        "Chief of Staff, steering the batch: 4 wakes, context 100 tokens on average, "
        "900 at its peak",
        "Driver cr-driver with its workers: $33.01 (14 calls)",
        "Driver cr-reviewer with its workers: $5.33 (2 calls)",
        "a chief line",
        "Not counted: compaction calls, which leave no record (about $0.12 each)",
    ]
