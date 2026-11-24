"""`dashboard.get` on All projects (`answer_all`): the figures summed per batch
number over the surface's projects, the ratios pooled, the model rank over every record."""

from __future__ import annotations

import json
from typing import Any

import pytest
from conftest import Surface
from dashboard_world import cr, model, part, rec
from test_board_overview import Served
from test_server_api import BAD

from chantier.board import history_page
from chantier.board.api import ops
from chantier.board.dashboard_page import answer

OK = 200
NINE, TWO, FORTY, TOTAL = 9, 2, 40.0, 60.0


def _spend(a: dict[str, Any]) -> dict[str, Any]:
    spend: dict[str, Any] = a["spending"]["spend"]
    return spend


# --- All projects: the same figures, summed per batch number over the surface's projects.

NEXT_DAY = "2026-11-19T10:00:00Z"  # a day after CLOSED
THREE_HOURS = "2026-11-18T12:00:00Z"
ALPHA_5, ALPHA_6 = 10.0, 5.0
BETA_5, BETA_7 = 20.0, 8.0


def _alpha() -> list[dict[str, Any]]:
    five = rec(
        5,
        [cr(1, rounds=1, cost=4.0), cr(2, rounds=3, cost=6.0)],
        cost=ALPHA_5,
        split=[part("steering", 4.0, 3), part("workers", 6.0, 7)],
        models=[model("a", 6.0), model("b", 4.0)],
    )
    six = rec(6, [cr(3, rounds=2, cost=5.0)], cost=ALPHA_6, closed="2026-11-18T10:30:00Z")
    return [five, six]


def _beta() -> list[dict[str, Any]]:
    five = rec(
        5,
        [cr(4, rounds=5, cost=20.0), cr(5, "dropped", rounds=9, cost=0.5)],
        cost=BETA_5,
        models=[model("c", 15.0)],
        closed=NEXT_DAY,
    )
    seven = rec(7, [cr(6, rounds=4, cost=BETA_7)], cost=BETA_7, closed=THREE_HOURS)
    return [five, seven]


def _write(world: Served, name: str, records: list[dict[str, Any]]) -> None:
    folder = world.forge.project(name) / "changes" / "5-archives" / "batches"
    folder.mkdir(parents=True, exist_ok=True)
    for r in records:
        (folder / f"batch-{r['number']}.json").write_text(json.dumps(r), encoding="utf-8")


def _get(world: Served, project: str, range_: str = "all") -> dict[str, Any]:
    got = ops.call(world.ctx, "dashboard.get", {"project": project, "range": range_})
    assert got.status == OK and got.data is not None, got.error
    return got.data


@pytest.fixture
def two(surface: Surface, monkeypatch: pytest.MonkeyPatch) -> Served:
    world = Served(surface, monkeypatch)
    _write(world, "alpha", _alpha())
    _write(world, "beta", _beta())
    return world


def test_all_projects_sums_a_shared_batch_number_and_keeps_a_lone_one(two: Served) -> None:
    a = _get(two, history_page.ALL)
    assert [(p["n"], p["projects"]) for p in a["points"]] == [(5, 2), (6, 1), (7, 1)]
    assert (a["closed_total"], a["total"]) == (3, 3)
    assert a["productivity"]["crs"]["values"] == [
        {"held": 4, "merged": 3},  # both projects' batch 5
        {"held": 1, "merged": 1},  # alpha's batch 6 alone
        {"held": 1, "merged": 1},
    ]
    assert a["productivity"]["calls"]["values"][0] == {"steering": 3, "workers": 7}
    spend = a["spending"]["spend"]
    assert spend["total"] == ALPHA_5 + ALPHA_6 + BETA_5 + BETA_7 and spend["covered"] == 3  # noqa: PLR2004
    assert spend["role"]["values"][0] == {"steering": 4.0, "workers": 6.0, "unsplit": BETA_5}
    alone = _get(two, "alpha")
    assert a["productivity"]["rounds"]["values"][1] == alone["productivity"]["rounds"]["values"][1]
    assert spend["role"]["values"][1] == _spend(alone)["role"]["values"][1]


def test_all_projects_pools_the_ratios_and_never_sums_or_averages_them(two: Served) -> None:
    a = _get(two, history_page.ALL)
    rounds = a["productivity"]["rounds"]
    assert rounds["values"][0] == pytest.approx(
        (1 + 3 + 5) / 3
    )  # not (2 + 5) / 2; a dropped CR's rounds are out
    assert rounds["mean"] == pytest.approx((1 + 3 + 5 + 2 + 4) / 5)
    per_cr = a["spending"]["per_cr"]
    assert per_cr["values"][0] == pytest.approx((ALPHA_5 + BETA_5) / 3)  # 2 + 1 merged CRs
    assert (per_cr["cost"], per_cr["merged"]) == (43.0, 5)
    assert per_cr["ratio"] == pytest.approx(43.0 / 5)


def test_all_projects_duration_is_a_mean_per_point_and_a_median_over_the_batches(
    two: Served,
) -> None:
    got = _get(two, history_page.ALL)["productivity"]["duration"]
    assert got["values"] == [(60 + 1440) // 2, 30, 120]  # batch 5: the two projects' mean
    assert got["median"] == (60 + 120 + 1) // 2  # of 30, 60, 120, 1440
    points = _get(two, history_page.ALL)["points"]
    assert [p["closed"] for p in points] == [None, "2026-11-18T10:30:00Z", THREE_HOURS]


def test_all_projects_ranks_the_models_over_both_projects_and_the_top_rows_name_theirs(
    two: Served,
) -> None:
    a = _get(two, history_page.ALL)
    series = [(s["key"], s["models"]) for s in _spend(a)["model"]["series"]]
    assert series == [("m1", ["c"]), ("m2", ["a"]), ("m3", ["b"]), ("unsplit", [])]
    rows = a["spending"]["top"]["rows"]
    assert [(r["project"], r["cr"]) for r in rows[:2]] == [("beta", "CR-4"), ("beta", "CR-6")]
    assert {r["project"] for r in rows} == {"alpha", "beta"} and a["spending"]["top"][
        "covered"
    ] == 3  # noqa: PLR2004
    alone = _spend(_get(two, "alpha"))["model"]["series"]
    assert [(s["key"], s["models"]) for s in alone[:2]] == [("m1", ["a"]), ("m2", ["b"])]


def test_a_projects_own_answer_is_unchanged_and_the_range_keeps_the_newest_numbers(
    two: Served,
) -> None:
    for name, records in (("alpha", _alpha()), ("beta", _beta())):
        got = _get(two, name)
        got.pop("now")
        assert got == answer(records, "all")
        assert all("projects" not in p for p in got["points"])
        assert all("project" not in r for r in got["spending"]["top"]["rows"])
    assert [p["n"] for p in _get(two, history_page.ALL, "10")["points"]] == [5, 6, 7]
    assert _get(two, history_page.ALL, "10")["range"] == "10"


def test_all_projects_refuses_an_unknown_range_and_reads_no_forge(two: Served) -> None:
    got = ops.call(two.ctx, "dashboard.get", {"project": history_page.ALL, "range": "15"})
    assert got.status == BAD and "range" in (got.error or "")
    for range_ in ("10", "20", "all"):
        _get(two, history_page.ALL, range_)
    assert two.forge.calls == []


def test_a_surface_with_no_closed_record_answers_an_empty_all_projects_page(
    surface: Surface, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = _get(Served(surface, monkeypatch), history_page.ALL)
    assert (a["closed_total"], a["total"], a["points"]) == (0, 0, [])
