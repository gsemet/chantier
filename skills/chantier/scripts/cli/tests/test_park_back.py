"""A parked CR coming back (`take`, `access`, the orders, the slot) and `order drop` of a parked CR
that has dependents, in a stack, a series and a parallel batch."""

from __future__ import annotations

from pathlib import Path

import pytest
from batch_helpers import batch_of, open_batch, record, write_record
from conftest import Chantier
from test_park import WAITS
from test_park_stack import parked_stack
from test_stack_hold import REPO, stacked_batch

from chantier.rails import out_of_order
from chantier.stacks import start_base

NOTE = ("--note", "wait cleared: the answer", "--epoch", 1)


def test_take_of_a_parked_cr_waits_for_its_wait_then_puts_it_on_top_with_its_dependents(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = parked_stack(repo, chantier, monkeypatch)
    a, b, _, e = ids
    data = record(repo)
    data["crs"].append({**data["crs"][3], "id": "CR-9", "kind": "release", "order": 9})
    data["crs"][3]["order"] = 4
    write_record(repo, data)
    refusal = f"`wait {b} clear w1 --epoch <n>` first"
    code, _, err = chantier("take", b, *NOTE[:2], "--epoch", 1)
    assert code != 0 and refusal in err
    code, out, _ = chantier("access", "claim", b, "--epoch", 1)
    assert code == 0 and any("refused" in x and refusal in x for x in out), out
    assert chantier("wait", b, "clear", "w1", "--epoch", 1)[0] == 0
    _, out, _ = chantier("status")
    assert next(x for x in out if x.startswith("parked: ")).startswith(
        f"parked: {b} wait cleared: take it back before any queued CR"
    )
    before = {x["id"]: x["order"] for x in record(repo)["crs"]}
    round_before = record(repo)["crs"][1]["round"]
    code, out, err = chantier("take", b, *NOTE)
    assert code == 0 and f"; its dependents above it: {e}" in out[0], err
    crs = {x["id"]: x for x in record(repo)["crs"]}
    assert "parked" not in crs[b] and crs[b]["round"] == round_before
    others = [x["order"] for i, x in crs.items() if i not in {b, e, "CR-9"}]
    assert crs[b]["order"] > max(others) and crs[e]["order"] == crs[b]["order"] + 1
    assert crs["CR-9"]["order"] > crs[e]["order"] > before[a]  # the release stays above


def test_take_of_a_cleared_parked_cr_needs_a_free_slot(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, b, c, _ = parked_stack(repo, chantier, monkeypatch)
    assert chantier("wait", b, "clear", "w1", "--epoch", 1)[0] == 0
    data = record(repo)
    data["slots"] = 1
    data["crs"][2]["status"] = "working"
    write_record(repo, data)
    code, _, err = chantier("take", b, *NOTE)
    assert code != 0 and f"no free slot for {b}" in err and f"{c} working" in err
    assert record(repo)["crs"][1]["parked"]


def test_a_series_cr_comes_back_after_the_started_crs_with_its_started_successor_above_it(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b, c, d, e = open_batch(
        repo, chantier, monkeypatch, "A", "B", "C", "D", "E", args=("--mode", "series")
    )
    data = record(repo)
    for i, status in enumerate(("merged", "working", "working", "working", "queued")):
        data["crs"][i].update(status=status, branch=f"b/{i + 1}", order=i + 1)
    data["crs"][2]["start_on"] = "b/2"  # the third started on the second
    write_record(repo, data)
    assert chantier("park", b, *WAITS, "--epoch", 1)[0] == 0
    third = record(repo)["crs"][2]
    assert third["start_on"] == "b/2"  # right after the park: a dependent keeps its base
    assert out_of_order(batch_of(repo).crs, batch_of(repo).crs[2], "series")
    assert chantier("wait", b, "clear", "w1", "--epoch", 1)[0] == 0
    code, out, err = chantier("take", b, *NOTE)
    assert code == 0 and "back in the series after its started CRs" in out[0], err
    orders = {x["id"]: x["order"] for x in record(repo)["crs"]}
    assert orders[a] < orders[d] < orders[b] < orders[c] < orders[e]
    assert orders[c] == orders[b] + 1


@pytest.mark.parametrize("mode", ["stack", "series", "parallel"])
def test_dropping_a_parked_cr_frees_its_dependent_and_names_who_takes_the_commits_out(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    _, b, c = stacked_batch(repo, chantier, monkeypatch, mode)
    data = record(repo)
    data["crs"][1]["status"] = "working"
    data["crs"][2]["after"] = [b]
    write_record(repo, data)
    assert chantier("park", b, *WAITS, "--epoch", 1)[0] == 0
    code, out, err = chantier("order", "drop", b, "--note", "trash")
    assert code == 0, err
    line = next(x for x in out if "was parked" in x)
    assert line.startswith(f"{b} was parked; waiting with it: {c}: ")
    assert "no stack driver needed" not in line
    if mode == "stack":
        assert f'`take stack --note "drop: {b} to 6-trash"`' in line
    else:
        assert f"the Foreman's note `rebase: {b} dropped`" in line and "take stack" not in line
    d = batch_of(repo)
    assert "parked" not in record(repo)["crs"][1]
    assert not out_of_order(d.crs, d.crs[2], mode)
    assert (
        start_base(d, d.crs[2], REPO) == {"stack": "b/1", "series": "b/1", "parallel": "main"}[mode]
    )


def test_dropping_a_parked_cr_with_no_dependent_needs_no_stack_driver(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, b, _ = stacked_batch(repo, chantier, monkeypatch)
    data = record(repo)
    data["crs"][1]["status"] = "working"
    write_record(repo, data)
    assert chantier("park", b, *WAITS, "--epoch", 1)[0] == 0
    code, out, err = chantier("order", "drop", b, "--note", "trash")
    assert code == 0 and f"{b} was parked: no stack driver needed" in out, err
