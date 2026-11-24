"""The base `handoff` prints for a CR of a stack batch is its place in the stack, as the record
orders it; the PR's own base on the forge follows after `; `."""

from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Any, cast

import pytest

from chantier.commands import forge_base
from chantier.commands.facts import _base_of, _landed_line, stack_lines
from chantier.core.records import BatchRecord, CrEntry
from chantier.core.repo import Repo

PR = "https://github.com/o/r/pull/"
REPO = cast(Repo, SimpleNamespace(config={"default_branch": "main", "remote": "origin"}))
NONE = frozenset[str]()


def cr(n: int, **kw: Any) -> CrEntry:
    fields: dict[str, Any] = {
        "status": "working",
        "pr": f"{PR}{n}",
        "order": n,
        "branch": f"b-{n}",
    }
    return CrEntry(id=f"CR-{n}", **{**fields, **kw})


def forge(monkeypatch: pytest.MonkeyPatch, base: str | None, why: str = "") -> list[str]:
    """What the forge reads for any PR: the base, or a failed read; the links asked."""
    asked: list[str] = []

    def read(link: str) -> tuple[str | None, str]:
        asked.append(link)
        return (base, "") if base else (None, forge_base.UNREAD.format(link=link, why=why))

    monkeypatch.setattr(forge_base, "read_base", read)
    return asked


def reordered() -> BatchRecord:
    """CR-2 was taken on CR-1's branch; `stack` then ordered CR-2 below CR-1."""
    crs = [cr(1, order=2), cr(2, order=1, start_on="b-1")]
    return BatchRecord(id="batch-01", mode="stack", crs=crs)


def test_a_taken_cr_whose_start_on_owner_now_sits_above_it_gets_its_places_base() -> None:
    d = reordered()
    d.crs[1].pr = None
    assert _base_of(d, d.crs[1], REPO, NONE) == "base origin/main"
    d.crs.insert(0, cr(0, status="ready", order=0))  # a ready CR with a PR is now below it
    assert _base_of(d, d.crs[2], REPO, NONE) == "base b-0"
    assert d.crs[2].start_on == "b-1"  # the record is not rewritten


@pytest.mark.parametrize(
    ("forge_base_", "tail"),
    [
        ("b-1", "; PR on b-1"),
        ("main", "; PR on origin/main"),
        ("b-2", ""),
        (None, "; PR base ? (not read from https://github.com/o/r/pull/3: boom)"),
    ],
    ids=["old base", "default branch", "equal to the place", "read failed"],
)
def test_the_forge_base_follows_the_place_and_is_added_only_when_it_differs(
    monkeypatch: pytest.MonkeyPatch, forge_base_: str | None, tail: str
) -> None:
    crs = [cr(1, stacked=True), cr(2, stacked=True), cr(3, stacked=True)]
    d = BatchRecord(id="batch-01", mode="stack", crs=crs)
    asked = forge(monkeypatch, forge_base_, "boom")
    line = _base_of(d, crs[2], REPO, NONE)
    assert line == f"base b-2{tail}" and "\n" not in line
    assert asked == [crs[2].pr]  # one read for the CR printed


def test_the_base_of_every_cr_equals_its_stack_row_and_the_landed_line_agrees(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forge(monkeypatch, "main")
    rel = cr(9, kind="release", status="queued", pr=None, order=9)
    d = BatchRecord(id="batch-01", mode="stack", crs=[*reordered().crs, cr(3, order=3), rel])
    rows = {r.split()[0]: r for r in stack_lines(REPO, "batch-01", d)[1:]}
    for c in stack_lines(REPO, "batch-01", d)[0].split(": ")[1].split(" → "):
        got = _base_of(d, next(x for x in d.crs if x.id == c), REPO, NONE).split(";")[0]
        assert re.search(rf" {got} PR ", rows[c]), (c, got, rows[c])
    ready = [cr(1, status="ready"), cr(2, status="ready"), cr(3, status="queued", pr=None)]
    e = BatchRecord(id="batch-01", mode="stack", crs=ready)
    line = _landed_line(e, ready[2], REPO, frozenset({"CR-2"}))
    assert [x.startswith("base: not CR-2's branch") for x in line] == [True]
    assert _base_of(e, ready[2], REPO, frozenset({"CR-2"})) == "base b-1"


def test_a_fix_cr_and_a_series_cr_keep_start_base(monkeypatch: pytest.MonkeyPatch) -> None:
    forge(monkeypatch, "b-9")
    fix = cr(5, kind="fix", after=["CR-1"], status="queued", pr=None)
    d = BatchRecord(id="batch-01", mode="stack", crs=[cr(1), fix])
    assert _base_of(d, fix, REPO, NONE) == "base origin/main"  # no place, no forge read
    series = BatchRecord(id="batch-01", mode="series", crs=[cr(1), cr(2)])
    assert _base_of(series, series.crs[1], REPO, NONE) == "base b-1"
