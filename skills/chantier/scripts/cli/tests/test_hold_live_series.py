"""`order hold` of a working CR in a series batch, through the real commands: a queued successor
starts on the CR before the held one; a successor already started on it waits with it."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from batch_helpers import open_batch, record, write_record
from conftest import Chantier

from chantier.core.batch import read_batch, resolve_batch
from chantier.core.records import BatchRecord
from chantier.core.repo import Repo
from chantier.rails import apart_owner, out_of_order, series_predecessor
from chantier.stack_words import ready_word
from chantier.stacks import next_merge, start_base

PR = "https://github.com/o/r/pull/"


def batch_now() -> tuple[Repo, BatchRecord]:
    r = Repo.find()
    return r, read_batch(r, resolve_batch(r, None))


def series_of_four(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, third: str
) -> list[str]:
    """CR one ready with a PR, two working, three `third` (queued, or working and started on the
    second), four queued."""
    ids = open_batch(repo, chantier, monkeypatch, "A", "B", "C", "D", args=("--mode", "series"))
    data = record(repo)
    rows: list[dict[str, Any]] = data["crs"]
    rows[0].update(status="ready", pr=f"{PR}1", pr_draft=False)
    rows[1].update(status="working", start_on=rows[0]["branch"])
    if third == "working":
        rows[2].update(status="working", pr=f"{PR}3", pr_draft=False, start_on=rows[1]["branch"])
    write_record(repo, data)
    return ids


def test_a_queued_third_starts_on_the_first_once_the_second_is_held(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b, c, _ = series_of_four(repo, chantier, monkeypatch, "queued")
    assert chantier("order", "hold", b)[0] == 0
    code, _, err = chantier("take", c, "--epoch", 1)  # the first is ready: it is met
    assert code == 0, err
    r, d = batch_now()
    third = d.crs[2]
    assert third.start_on == d.crs[0].branch
    assert not out_of_order(d.crs, third, d.mode)
    assert start_base(d, third, r) == d.crs[0].branch
    third.status, third.pr, third.pr_draft = "ready", f"{PR}3", False
    merge = next_merge(d)
    assert merge is not None and merge.id == a  # the first is the next merge
    d.crs[0].status = "merged"
    merge = next_merge(d)
    assert merge is not None and merge.id == c and ready_word(d, third, r) is not None


def test_a_third_started_on_the_second_waits_with_it_and_comes_back_above_it(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b, c, e = series_of_four(repo, chantier, monkeypatch, "working")
    assert chantier("order", "hold", b)[0] == 0
    r, d = batch_now()
    second, third, fourth = d.crs[1], d.crs[2], d.crs[3]
    assert third.start_on == second.branch  # a dependent keeps its start_on
    assert out_of_order(d.crs, third, "series")
    owner = apart_owner(d.crs, third, "series")
    assert owner is not None and owner.id == b
    third.status = "ready"  # handed back ready, still a draft
    assert next_merge(d) is d.crs[0]  # neither the held CR nor its dependent
    assert ready_word(d, third, r) == "PR in draft"
    assert start_base(d, third, r) == second.branch
    pred = series_predecessor(d.crs, fourth)
    assert pred is not None and pred.id == a  # skips the held CR and its dependent
    code, out, _ = chantier("status")
    assert any(x.startswith(f"held: {b} (order O-1), was working") and c in x for x in out), out
    code, out, err = chantier("order", "unhold", b)
    assert code == 0, err
    line = next(x for x in out if f"{b} unheld" in x)
    assert ": back in the series after its started CRs; " in line
    assert line.endswith(f"; its dependents above it: {c}")
    orders = {x["id"]: x["order"] for x in record(repo)["crs"]}
    assert orders[a] < orders[b] < orders[c] < orders[e]
    assert orders[c] == orders[b] + 1  # the third right above the second
