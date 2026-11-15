"""The budget is checked on the spend read from the transcripts, and the figure is dated."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from batch_helpers import record, write_record
from conftest import Chantier
from cost_world import CostWorld, build

from chantier.core.errors import EXIT_BUDGET

REAL = 1.0  # the fixture transcripts' priced spend, about $1.00
STORED = 0.01  # a figure recorded long ago


def args_of(w: CostWorld) -> dict[str, tuple[str, ...]]:
    one = w.ids[0]
    return {
        "take": ("take", one, "--note", "resume: test", "--epoch", "1"),
        "stack": ("take", "stack", "--epoch", "1"),
        "round": ("round", one, "--note", "round 1"),
        "qa": ("order", "qa", "--note", "check it"),
        "fix": ("order", "add", "--fix-for", one, "--note", "a fix", "--epoch", "1"),
        "release": ("release", "go", one, "--note", "publish"),
    }


@pytest.fixture
def world(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> CostWorld:
    return build(repo, chantier, monkeypatch, tmp_path)


def stage(w: CostWorld, which: str, budget: float | None) -> None:
    """The batch as a Driver finds it: a budget, and a stored spend far below the real one."""
    one = w.ids[0]
    assert w.chantier("agents", "set", one, "-", "--epoch", "1")[0] == 0
    d = record(w.repo)
    d = {**d, "budget_usd": budget, "spent_usd": STORED}
    d.pop("spent_at", None)
    if which == "stack":
        d["mode"] = "stack"
    if which in {"fix", "release"}:
        d["release"] = {"cr": one, "fixes": True, "autonomous": 0, "published": 0}
        d["crs"] = [{**c, "kind": "release"} if c["id"] == one else c for c in d["crs"]]
    write_record(w.repo, d)


@pytest.mark.parametrize("which", ["take", "stack", "round", "qa", "fix", "release"])
def test_a_budget_check_refreshes_the_spend_and_refuses_on_the_real_one(
    world: CostWorld, which: str
) -> None:
    stage(world, which, 0.5)
    code, out, err = world.chantier(*args_of(world)[which])
    assert code == EXIT_BUDGET and "budget" in err + "\n".join(out)
    d = record(world.repo)
    assert abs(d["spent_usd"] - REAL) < REAL / 10 and d["spent_at"]


@pytest.mark.parametrize("which", ["take", "stack", "round", "qa", "fix", "release"])
def test_a_budget_above_the_real_spend_passes_the_check_and_still_dates_the_spend(
    world: CostWorld, which: str
) -> None:
    stage(world, which, 50)
    code, out, err = world.chantier(*args_of(world)[which])
    said = (err + chr(10).join(out)).lower()
    assert code != EXIT_BUDGET and "budget spent" not in said and "budget is spent" not in said
    d = record(world.repo)
    assert abs(d["spent_usd"] - REAL) < REAL / 10 and d["spent_at"]


def test_no_budget_reads_no_transcript_and_leaves_the_spend_alone(world: CostWorld) -> None:
    stage(world, "round", None)
    world.main.unlink()  # a refresh would now fail: it must not even be tried
    code, out, err = world.chantier(*args_of(world)["round"])
    assert code == 0 and "spend not refreshed" not in "\n".join(out), err
    d = record(world.repo)
    assert d["spent_usd"] == STORED and "spent_at" not in d


@pytest.mark.parametrize(("budget", "refused"), [(0.005, True), (50, False)])
def test_an_unreadable_spend_checks_the_last_recorded_figure_and_says_so(
    world: CostWorld, budget: float, refused: bool
) -> None:
    stage(world, "take", budget)
    d = record(world.repo)
    write_record(world.repo, {**d, "foreman_transcript": None, "foreman_transcripts": []})
    code, out, err = world.chantier(*args_of(world)["take"])
    assert (code == EXIT_BUDGET) is refused, (code, out, err)
    if not refused:
        assert any(ln.startswith("spend not refreshed: ") and "age unknown" in ln for ln in out)
    assert record(world.repo)["spent_usd"] == STORED


def test_status_says_how_old_the_spend_is_and_status_json_carries_the_time(
    world: CostWorld,
) -> None:
    stage(world, "take", 0.5)
    first: Callable[[], str] = lambda: world.chantier("status")[1][0]  # noqa: E731
    assert ", age unknown" in first() and "spent $0.01 of $0.5" in first()
    world.chantier(*args_of(world)["take"])  # refused: the figure is refreshed all the same
    assert ", 0 min old" in first()
    view = json.loads((world.state.parent / "STATUS.json").read_text(encoding="utf-8"))
    assert view["spent_at"] == record(world.repo)["spent_at"]
    write_record(world.repo, {**record(world.repo), "spent_usd": None, "spent_at": None})
    assert "min old" not in first() and "age unknown" not in first()
    world.chantier("status", "--refresh")
    assert record(world.repo)["spent_at"]


def test_pause_dates_the_spend_it_records(world: CostWorld) -> None:
    d = record(world.repo)
    d["crs"] = [{**c, "status": "merged", "agent": None} for c in d["crs"]]
    d.pop("spent_at", None)
    write_record(world.repo, d)
    code, _, err = world.chantier("pause", "--epoch", "1")
    assert code == 0, err
    assert record(world.repo)["spent_at"]
