"""The Dashboard's figures (`board/dashboard_page.py:answer`) on prepared records with batch-29's
shapes, and `dashboard.get` through the ops: a missing or wrong-typed figure is no value, never a
zero or an error; the range, the live batch, the model rank, the durations, the ranking."""

from __future__ import annotations

from typing import Any

import pytest
from dashboard_world import CLOSED, OPENED, batch29, cr, model, old, part, rec, side
from test_board_prs import Board
from test_server_api import BAD, NOT_FOUND, board, call  # noqa: F401 - the fixture

from chantier.board.dashboard_page import answer

NINE, CALLS, TOTAL, COVERED, OK = 9, 9318, 60.0, 5, 200
FORTY, TWO = 40.0, 2


def _spend(a: dict[str, Any]) -> dict[str, Any]:
    spend: dict[str, Any] = a["spending"]["spend"]
    return spend


def test_batch_29_s_own_record_gives_the_costs_figures() -> None:
    a = answer([batch29()], "all")
    assert (a["closed_total"], a["total"], a["range"]) == (1, 1, "all")
    assert a["points"] == [{"batch": "batch-29", "n": 29, "closed": "2026-11-21T03:43:34Z",
                            "unpriced": False}]  # fmt: skip
    prod, spending = a["productivity"], a["spending"]
    assert prod["crs"] == {"values": [{"held": 36, "merged": 34}], "covered": 1, "held": 36,
                           "merged": 34}  # fmt: skip
    assert prod["rounds"]["mean"] == pytest.approx(70 / 34)
    assert prod["rounds"]["values"] == [pytest.approx(70 / 34)]
    assert (prod["duration"]["values"], prod["duration"]["median"]) == ([1694], 1694)
    calls = prod["calls"]
    assert calls["parts"] == ["steering", "drivers", "workers"] and calls["total"] == CALLS
    assert calls["values"] == [{"steering": 983, "drivers": 3088, "workers": 5247}]
    assert spending["per_cr"]["ratio"] == pytest.approx(243.5351 / 34)
    assert (spending["per_cr"]["merged"], spending["per_cr"]["unpriced"]) == (34, False)
    spend = _spend(a)
    assert spend["total"] == pytest.approx(243.5351) and spend["covered"] == 1
    assert spend["role"]["series"] == ["steering", "drivers", "workers"]
    assert spend["role"]["values"] == [
        {"steering": 59.71, "drivers": 64.23, "workers": pytest.approx(119.6)}
    ]
    assert spend["model"]["series"] == [
        {"key": "m1", "models": ["claude-sonnet-5-5"]},
        {"key": "m2", "models": ["claude-opus-5-5"]},
    ]
    assert spend["model"]["values"] == [{"m1": 175.29, "m2": 68.25}] and not spend["unpriced"]
    assert spending["outside"]["usd"] == pytest.approx(101.4204 + 38.5735)
    assert spending["outside"]["covered"] == 1 and not spending["outside"]["unpriced"]
    rows = spending["top"]["rows"]
    assert [r["cr"] for r in rows[:3]] == ["CR-404", "CR-406", "CR-418"]
    assert (len(rows), rows[-1]["cr"], rows[-1]["cost_usd"]) == (10, "CR-420", 5.8077)
    assert spending["top"]["covered"] == 1 and rows[0]["batch"] == "batch-29"
    assert rows[0]["pr"].startswith("https://") and rows[0]["rounds"] is not None


def test_a_back_filled_record_is_a_point_in_the_crs_and_the_ranking_only() -> None:
    crs = [cr(1, rounds=2, cost=3.0), cr(2, "dropped", rounds=1, cost=4.0)]
    a = answer([old(3, crs)], "all")
    assert a["points"][0]["closed"] is None
    prod, spending = a["productivity"], a["spending"]
    assert prod["crs"]["values"] == [{"held": 2, "merged": 1}]
    assert prod["rounds"]["values"] == [2.0] and prod["rounds"]["covered"] == 1
    assert (prod["duration"]["values"], prod["duration"]["covered"]) == ([None], 0)
    assert prod["duration"]["median"] is None
    assert (prod["calls"]["values"], prod["calls"]["total"], prod["calls"]["parts"]) == (
        [None],
        None,
        [],
    )
    per_cr = spending["per_cr"]
    assert (per_cr["values"], per_cr["covered"], per_cr["ratio"]) == ([None], 0, None)
    spend = _spend(a)
    assert (spend["role"]["values"], spend["model"]["values"]) == ([None], [None])
    assert (spend["total"], spend["covered"], spend["role"]["series"]) == (None, 0, [])
    assert spending["outside"] == {"usd": None, "covered": 0, "unpriced": False}
    assert [r["cr"] for r in spending["top"]["rows"]] == ["CR-2", "CR-1"]  # dropped cost stays
    assert spending["top"]["covered"] == 1


@pytest.mark.parametrize(
    ("record", "calls", "role", "by_model"),
    [
        (rec(17, [cr(1)], cost=5.0), None, {"unsplit": 5.0}, {"unsplit": 5.0}),
        (
            rec(
                23,
                [cr(1)],
                cost=10.0,
                split=[part("steering", 4.0, None), part("drivers", 6.0, None)],
            ),
            None,
            {"steering": 4.0, "drivers": 6.0},
            {"unsplit": 10.0},
        ),
    ],
    ids=["no receipt (batch-17)", "split without calls, no models (batch-23)"],
)
def test_a_record_without_a_split_is_one_unsplit_segment_and_no_calls(
    record: dict[str, Any], calls: Any, role: dict[str, float], by_model: dict[str, float]
) -> None:
    a = answer([record], "all")
    assert a["productivity"]["calls"]["values"] == [calls]
    assert _spend(a)["role"]["values"] == [role]
    assert _spend(a)["model"]["values"] == [by_model]
    assert _spend(a)["model"]["series"] == [{"key": "unsplit", "models": []}]


def test_an_agents_part_stands_in_for_drivers_and_workers_and_the_bar_is_the_larger() -> None:
    both = [model("a", 12.0), model("b", 18.0)]
    first = rec(
        1,
        [cr(1)],
        cost=35.0,
        models=both,
        split=[
            part("steering", 10.0, 4),
            part("agents", 20.0, 8),
            part("drivers", 9, 99),
            part("workers", 9, 99),
        ],
    )
    second = rec(
        2,
        [cr(2)],
        cost=25.0,
        models=both,
        split=[part(p, 10.0) for p in ("steering", "drivers", "workers")],
    )
    a = answer([first, second], "all")
    assert a["productivity"]["calls"]["values"] == [
        {"steering": 4, "agents": 8},
        {"steering": 10, "drivers": 10, "workers": 10},
    ]
    assert a["productivity"]["calls"]["parts"] == ["steering", "drivers", "workers", "agents"]
    spend = _spend(a)
    assert spend["role"]["series"] == ["steering", "drivers", "workers", "agents", "unsplit"]
    assert spend["role"]["values"] == [
        {"steering": 10.0, "agents": 20.0, "unsplit": 5.0},  # 30 of 35: the rest is unsplit
        {"steering": 10.0, "drivers": 10.0, "workers": 10.0},  # 30 over 25: the bar is the sum
    ]
    assert spend["model"]["values"] == [
        {"m2": 12.0, "m1": 18.0, "unsplit": 5.0},
        {"m2": 12.0, "m1": 18.0},
    ]
    assert spend["total"] == TOTAL


def test_dropped_rounds_zero_missing_cost_and_unpriced_records() -> None:
    crs = [
        cr(1, rounds=0, cost=2.0),
        cr(2, rounds=None, cost=None),
        cr(3, "dropped", rounds=3, cost=4.0),
        cr(4, rounds=3, cost=1.0, cost_unpriced={"x": 1}),
    ]
    mixed = rec(30, crs, cost=10.0, cost_unpriced={"claude": 1})
    nothing = rec(31, [cr(5, "dropped")], cost=3.0)
    a = answer([mixed, nothing], "all")
    prod, spending = a["productivity"], a["spending"]
    assert prod["crs"]["values"] == [{"held": 4, "merged": 3}, {"held": 1, "merged": 0}]
    assert prod["rounds"]["values"] == [1.5, None]  # 0 counts, a missing `rounds` does not
    assert (prod["rounds"]["mean"], prod["rounds"]["covered"]) == (1.5, 1)
    assert [p["unpriced"] for p in a["points"]] == [True, False]
    per_cr = spending["per_cr"]
    assert per_cr["values"] == [pytest.approx(10 / 3), None] and per_cr["covered"] == 1
    assert (per_cr["cost"], per_cr["merged"], per_cr["unpriced"]) == (10.0, 3, True)
    spend = _spend(a)
    assert (spend["total"], spend["covered"], spend["unpriced"]) == (13.0, 2, True)
    top = spending["top"]
    assert [r["cr"] for r in top["rows"]] == ["CR-3", "CR-1", "CR-5", "CR-4"]  # CR-2: no cost
    assert [r["unpriced"] for r in top["rows"]] == [False, False, False, True]
    assert top["rows"][0]["pr"] is None and top["covered"] == TWO


def _nine() -> list[dict[str, Any]]:
    """Records 3 to 12 hold `mod-0` to `mod-7` (`mod-i` costs 10 (i + 1)); record 1 alone holds
    `big`, which costs more over all the records than any of them."""
    small = [model(f"mod-{i}", 10.0 * (i + 1)) for i in range(8)]
    records = [rec(n, [cr(n)], cost=360.0, models=small) for n in range(3, 13)]
    return [rec(1, [cr(1)], cost=1000.0, models=[model("big", 1000.0)]), *records]


def test_models_keep_their_series_key_by_their_cost_over_all_the_records() -> None:
    every = answer(_nine(), "all")
    ten = answer(_nine(), "10")
    keys = [(s["key"], s["models"]) for s in _spend(every)["model"]["series"]]
    assert keys == [
        ("m1", ["big"]),
        ("m2", ["mod-7"]),
        ("m3", ["mod-6"]),
        ("m4", ["mod-5"]),
        ("m5", ["mod-4"]),
        ("m6", ["mod-3"]),
        ("m7", ["mod-2"]),
        ("other", ["mod-1", "mod-0"]),
    ]
    drawn = [(s["key"], s["models"]) for s in _spend(ten)["model"]["series"]]
    assert drawn == keys[1:]  # `big` is out of the range, the others keep their key
    first = _spend(ten)["model"]["values"][0]
    assert first == {"m2": 80.0, "m3": 70.0, "m4": 60.0, "m5": 50.0, "m6": 40.0, "m7": 30.0,
                     "other": 30.0}  # fmt: skip


def test_eight_models_have_m1_to_m8_and_no_other() -> None:
    records = [
        rec(n, [cr(n)], cost=360.0, models=_nine()[2]["cost_receipt"]["models"]) for n in (1, 2)
    ]
    series = _spend(answer(records, "all"))["model"]["series"]
    assert [s["key"] for s in series] == [f"m{i}" for i in range(1, NINE)]
    assert series[-1]["models"] == ["mod-0"]


def test_the_live_the_stale_and_the_unreadable_records_are_out() -> None:
    history: list[Any] = [
        rec(30, [cr(9)], state="running", closed=None),
        rec(31, state="paused", closed=None),
        rec(20, [cr(8)], state="running", closed=None),  # batch-20.json, stale since long
        "junk",
        None,
        rec(2, [cr(2)]),
        rec(1, [cr(1)]),
    ]
    a = answer(history, "all")
    assert (a["closed_total"], a["total"]) == (2, 2)
    assert [p["batch"] for p in a["points"]] == ["batch-01", "batch-02"]
    assert a["productivity"]["crs"]["held"] == TWO


@pytest.mark.parametrize(
    ("range_", "first", "count"), [("10", 16, 10), ("20", 6, 20), ("all", 1, 25)]
)
def test_a_range_keeps_the_newest_closed_records_oldest_first(
    range_: str, first: int, count: int
) -> None:
    history = [rec(n, [cr(n)]) for n in range(25, 0, -1)]  # as the state holds them: newest first
    a = answer(history, range_)
    assert [p["n"] for p in a["points"]] == list(range(first, 26))
    assert (a["total"], a["closed_total"], len(a["productivity"]["crs"]["values"])) == (
        count,
        25,
        count,
    )


def test_a_wrong_typed_value_is_no_value_and_no_error() -> None:
    bad = [
        rec(1, "not a list", cost="12", opened=5, closed=["x"], split="s", models="m", outside="o"),
        rec(
            2,
            [cr(1, cost=True, rounds=True), "junk", {"result": "merged"}],
            cost=True,
            opened="x",
            closed=None,
            split=[{"part": 3, "usd": 1}],
            models=[7, {"model": "a", "usd": "x"}],
            outside={"grill": 4},
        ),
        rec(3, [cr(1, cost="9", rounds="2")], cost=2.0, cost_receipt="r", closed=12, number="b-3"),
    ]
    a = answer(bad, "all")
    prod, spending = a["productivity"], a["spending"]
    assert prod["crs"]["values"] == [None, {"held": 3, "merged": 2}, {"held": 1, "merged": 1}]
    assert prod["rounds"]["values"] == [None, None, None]
    assert (
        prod["duration"]["values"] == [None, None, None] and prod["calls"]["values"] == [None] * 3
    )
    assert spending["per_cr"]["values"] == [
        None,
        None,
        2.0,
    ]  # only rec 3 has a cost and a merged CR
    assert spending["top"] == {"rows": [], "covered": 0}
    assert spending["outside"]["usd"] is None
    values = _spend(a)["role"]["values"]
    assert values[0] is None and values[1] is None and values[2] == {"unsplit": 2.0}
    assert [p["closed"] for p in a["points"]] == [None, None, None]


@pytest.mark.parametrize(
    ("opened", "closed", "minutes"),
    [
        (OPENED, "2026-11-18T10:02:30Z", 3),  # a half minute rounds up, as `Math.round`
        (OPENED, "2026-11-18T10:01:30Z", 2),
        (OPENED, "2026-11-18T10:02:29Z", 2),
        (CLOSED, OPENED, 0),
        (OPENED, "not a date", None),
        (OPENED, None, None),
        (7, CLOSED, None),
    ],
)
def test_a_duration_is_whole_minutes_with_a_half_rounding_up(
    opened: Any, closed: Any, minutes: int | None
) -> None:
    got = answer([rec(1, opened=opened, closed=closed)], "all")["productivity"]["duration"]
    assert got["values"] == [minutes] and got["median"] == minutes


def test_the_median_of_an_even_count_rounds_a_half_up_and_an_odd_one_takes_the_middle() -> None:
    twenty_seven = rec(27, opened="2026-11-18T14:33:05Z", closed="2026-11-18T17:47:48Z")
    twenty_nine = rec(29, opened="2026-11-19T23:29:36Z", closed="2026-11-21T03:43:34Z")
    got = answer([twenty_seven, twenty_nine], "all")["productivity"]["duration"]
    assert (got["values"], got["median"], got["covered"]) == ([195, 1694], 945, 2)
    three = [rec(n, opened=OPENED, closed=f"2026-11-18T{10 + m // 60}:{m % 60:02d}:00Z")
             for n, m in ((1, 40), (2, 20), (3, 10))]  # fmt: skip
    odd = answer(three, "all")["productivity"]["duration"]
    assert (odd["values"], odd["median"]) == ([40, 20, 10], 20)


def test_the_ten_most_expensive_crs_tie_by_batch_then_cr_and_count_costed_records() -> None:
    fives = {5: [11, 12, 13, 14, 15, 16], 4: [5, 2], 3: [9, 1], 2: [50]}
    records = [rec(n, [cr(i, cost=5.0) for i in ids]) for n, ids in fives.items()]
    records.append(rec(1, [cr(100, cost=9.0), cr(101, cost=None)]))
    records.append(rec(6, [cr(7, cost=None)]))  # no costed CR: not counted
    top = answer(records, "all")["spending"]["top"]
    got = [(r["cr"], r["batch"]) for r in top["rows"]]
    assert got[:2] == [("CR-100", "batch-01"), ("CR-11", "batch-05")]
    assert [c for c, _ in got] == [
        "CR-100",
        *[f"CR-{i}" for i in (11, 12, 13, 14, 15, 16, 2, 5, 1)],
    ]
    assert top["covered"] == COVERED


def test_the_outside_line_sums_what_every_record_holds_and_is_not_in_the_total() -> None:
    unpriced = {"grill": {"usd": 1.0, "calls": 1, "unpriced": {"x": 1}}}
    history = [
        rec(1, cost=10.0, outside=side(grill=1.5, steering=2.5)),
        rec(2, cost=10.0, outside=side(grill=4.0)),
        rec(3, cost=10.0, outside={"grill": {"usd": "x", "calls": 1, "unpriced": {}}}),
        rec(4, cost=10.0),
    ]
    got = answer(history, "all")
    assert got["spending"]["outside"] == {"usd": 8.0, "covered": 2, "unpriced": False}
    assert _spend(got)["total"] == FORTY
    assert answer([rec(5, cost=1.0, outside=unpriced)], "all")["spending"]["outside"] == {
        "usd": 1.0,
        "covered": 1,
        "unpriced": True,
    }


def test_the_op_refuses_a_range_it_does_not_know_and_a_project_it_does_not_hold(
    board: Board,  # noqa: F811
) -> None:
    status, body = call(board, "dashboard.get", {"project": board.id, "range": "15"})
    assert status == BAD and "range" in body["error"]
    assert call(board, "dashboard.get", {"project": "nobody"})[0] == NOT_FOUND
    status, body = call(board, "dashboard.get", {"project": board.id, "range": "all"})
    assert status == OK and body["data"]["range"] == "all" and "now" in body["data"]
