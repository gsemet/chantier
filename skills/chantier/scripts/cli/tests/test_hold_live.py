"""`order hold` of a live CR in every batch mode: the shared definition of apart, dependent and
out of order, the hold and unhold of a working CR, its release refusal and its drop."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from batch_helpers import open_batch, record, write_record
from conftest import Chantier

from chantier.core.batch import read_batch, resolve_batch
from chantier.core.records import BatchRecord, CrEntry
from chantier.core.repo import Repo
from chantier.rails import (
    apart,
    apart_owner,
    is_held,
    out_of_order,
    series_predecessor,
)
from chantier.stack_apart import dependents
from chantier.stacks import start_base


def cr(n: int, **kw: Any) -> CrEntry:
    fields: dict[str, Any] = {"status": "working", "order": n, "branch": f"b/cr-{n}"}
    return CrEntry(id=f"CR-{n}", **{**fields, **kw})


def of(mode: str, *crs: CrEntry) -> BatchRecord:
    return BatchRecord(id="batch-01", mode=mode, crs=list(crs))


def test_apart_dependent_and_out_of_order_are_computed_from_the_record() -> None:
    held = cr(1, status="blocked", held="O-1")
    after = cr(2, after=["CR-1"])
    chained = cr(3, after=["CR-2"])  # waits with CR-2, which waits with CR-1
    free = cr(4)
    d = of("parallel", held, after, chained, free)
    assert is_held(held) and apart(held) and not apart(after)
    assert [x.id for x in dependents(d.crs, held, d.mode)] == ["CR-2", "CR-3"]
    assert [out_of_order(d.crs, x, d.mode) for x in d.crs] == [True, True, True, False]
    owner = apart_owner(d.crs, chained, d.mode)
    assert owner is not None and owner.id == "CR-1"
    held.status = "merged"  # a stale `held` on an ended CR is not held
    assert not out_of_order(d.crs, after, d.mode)


def test_in_a_series_a_cr_started_on_a_held_cr_is_a_dependent_until_it_is_back() -> None:
    first = cr(1, status="blocked", held="O-1")
    started = cr(2, start_on="b/cr-1")  # left `queued`: it stands on CR-1
    waiting = cr(3, status="queued")
    d = of("series", first, started, waiting)
    assert out_of_order(d.crs, started, "series")
    assert not out_of_order(d.crs, waiting, "series")  # queued: never waits through start_on
    assert series_predecessor(d.crs, waiting) is not first
    first.unset("held")
    assert not out_of_order(d.crs, started, "series")


@pytest.mark.parametrize("mode", ["stack", "parallel", "series"])
def test_a_working_cr_is_held_in_every_mode_and_comes_back_blocked(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    a, b, c = open_batch(repo, chantier, monkeypatch, "A", "B", "C", args=("--mode", mode))
    data = record(repo)
    for i, x in enumerate(data["crs"][:2]):
        x.update(status="working", branch=f"b/{i + 1}", agent="agent-x", start_on=None)
    data["crs"][1]["after"] = [a]
    write_record(repo, data)
    code, out, err = chantier("order", "hold", a)
    assert code == 0, err
    assert any(f"{a} held (order O-1): it was live" in x for x in out)
    held = record(repo)["crs"][0]
    assert held["status"] == "blocked" and held["held"] == "O-1" and held["agent"] == "agent-x"
    assert record(repo)["orders"][-1]["applied"] is False  # the Foreman ends it: `order done`
    code, out, err = chantier("status")
    assert any(x.startswith(f"held: {a} (order O-1), was working") for x in out), out
    code, out, err = chantier("order", "hold", a)
    assert code != 0 and "already held" in err
    code, out, err = chantier("order", "unhold", a)
    assert code == 0, err
    back = record(repo)["crs"][0]
    assert back["status"] == "blocked" and "held" not in back
    assert any(f"{a} unheld" in x and "unhold: O-" in x for x in out)
    assert b and c


def test_a_release_does_not_start_while_a_cr_is_held_and_names_it(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = open_batch(repo, chantier, monkeypatch, "A", "B", args=("--mode", "parallel"))
    data = record(repo)
    data["crs"][0].update(status="blocked", held="O-1")
    data["crs"][1].update(status="queued", kind="release")
    write_record(repo, data)
    code, _, err = chantier("take", ids[1], "--epoch", "1")
    assert code != 0
    assert f"waits for {ids[0]} held (order O-1)" in err and f"order unhold {ids[0]}" in err


@pytest.mark.parametrize(
    ("mode", "tail"),
    [
        ("stack", "take stack"),
        ("series", "their Drivers rebase to take its commits out"),
        ("parallel", "rebase: "),
    ],
)
def test_the_drop_of_a_held_cr_names_who_waited_with_it(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, mode: str, tail: str
) -> None:
    a, b, _ = open_batch(repo, chantier, monkeypatch, "A", "B", "C", args=("--mode", mode))
    data = record(repo)
    data["crs"][0].update(status="blocked", held="O-1")
    data["crs"][1].update(status="working", after=[a])
    write_record(repo, data)
    code, out, err = chantier("order", "drop", a, "--note", "trash")
    assert code == 0, err
    text = " ".join(out)
    assert f"{a} was held; waiting with it: {b}" in text and tail in text
    assert "no stack driver needed" not in text
    assert ("take stack --note" in text) is (mode == "stack")
    assert ("`rebase: " + a + " dropped`" in text) is (mode != "stack")
    assert "held" not in record(repo)["crs"][0] or record(repo)["crs"][0]["held"] is None
    r = Repo.find()
    d = read_batch(r, resolve_batch(r, None))
    assert not out_of_order(d.crs, d.crs[1], mode)  # no longer waiting with the dropped CR
    assert start_base(d, d.crs[1], r) != d.crs[0].branch  # its series, stack or default base


def test_the_drop_of_a_held_cr_with_no_dependent_needs_no_stack_driver(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = open_batch(repo, chantier, monkeypatch, "A", "B", args=("--mode", "parallel"))
    data = record(repo)
    data["crs"][0].update(status="blocked", held="O-1")
    write_record(repo, data)
    code, out, err = chantier("order", "drop", a, "--note", "trash")
    assert code == 0, err
    assert f"{a} was held: no stack driver needed" in out
    assert not any("waiting with it" in x for x in out)


@pytest.mark.parametrize("mode", ["series", "parallel"])
def test_stack_out_of_draft_refuses_a_batch_that_is_not_a_stack(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    a, _ = open_batch(repo, chantier, monkeypatch, "A", "B", args=("--mode", mode))
    code, _, err = chantier("stack", "--out-of-draft", a)
    assert code != 0 and "is not a stack" in err
