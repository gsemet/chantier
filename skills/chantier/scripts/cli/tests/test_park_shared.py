"""The definition `park` and `order hold` share (`out_of_order`, `apart_owner`, the base rule), and
the series cases of a parked CR, on prepared records."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from chantier.core.records import BatchRecord, CrEntry
from chantier.core.repo import Repo
from chantier.rails import apart_owner, out_of_order, series_predecessor, waits_for
from chantier.stack_apart import waits_with
from chantier.stack_words import ready_word
from chantier.stacks import next_merge, stack_base, start_base, start_on_for

REPO = cast(Repo, SimpleNamespace(config={"default_branch": "main", "remote": "origin"}))
PR = "https://github.com/o/r/pull/"
APART = {
    "parked": {"status": "blocked", "parked": "2026-11-21T10:00:00Z"},
    "held": {"status": "ready", "held": "O-1"},
}
NAMED = {"parked": "parked CR-2", "held": "held CR-2 (order O-1)"}
NAMED_7 = {"parked": "parked CR-7", "held": "held CR-7 (order O-1)"}


def cr(n: int, **kw: Any) -> CrEntry:
    fields: dict[str, Any] = {"status": "ready", "order": n, "branch": f"b-{n}", "pr": f"{PR}{n}"}
    return CrEntry(id=f"CR-{n}", **{**fields, **kw})


def shared(kind: str, after5: list[str], after6: list[str]) -> BatchRecord:
    """CR-1 in the stack; CR-2 apart; CR-3 after CR-2; CR-4 after CR-3; CR-5 and CR-6 after an
    in-stack CR and out-of-order ones; CR-7 a second apart CR, CR-8 after it, CR-9 after both."""
    return BatchRecord(
        id="batch-01",
        mode="stack",
        crs=[
            cr(1, stacked=True),
            cr(2, **APART[kind]),
            cr(3, after=["CR-2"]),
            cr(4, after=["CR-3"]),
            cr(5, after=after5),
            cr(6, after=after6),
            cr(7, **APART[kind]),
            cr(8, after=["CR-7"]),
            cr(9, after=["CR-3", "CR-8"]),
        ],
    )


@pytest.mark.parametrize("kind", ["parked", "held"])
@pytest.mark.parametrize(
    ("after5", "after6", "base5", "base6"),
    [
        (["CR-1", "CR-2"], ["CR-2", "CR-3"], "b-2", "b-3"),
        (["CR-2", "CR-1"], ["CR-3", "CR-2"], "b-2", "b-2"),
    ],
)
def test_a_dependent_is_out_of_order_and_its_base_is_the_last_out_of_order_dependency(
    kind: str, after5: list[str], after6: list[str], base5: str, base6: str
) -> None:
    d = shared(kind, after5, after6)
    one, two, *deps = d.crs
    assert not out_of_order(d.crs, one, "stack") and out_of_order(d.crs, two, "stack")
    for c in deps[:3]:  # CR-3, CR-4 (through CR-3), CR-5 (after an in-stack CR and CR-2)
        assert out_of_order(d.crs, c, "stack"), c.id
    owners = {c.id: apart_owner(d.crs, c, "stack").id for c in (two, *deps)}
    assert owners["CR-2"] == owners["CR-3"] == owners["CR-4"] == owners["CR-5"] == "CR-2"
    # the in-stack CR is never a base; with two out-of-order dependencies, the last one's branch
    for c, base in ((d.crs[4], base5), (d.crs[5], base6)):
        assert stack_base(d, c, REPO) == base and start_base(d, c, REPO) == base
    assert stack_base(d, d.crs[1], REPO) == "main"  # an apart CR's own base
    # two different apart owners: the last dependency's owner, the CR the base rule picks
    assert apart_owner(d.crs, d.crs[8], "stack").id == "CR-7"
    assert stack_base(d, d.crs[8], REPO) == "b-8"
    assert waits_with(d, d.crs[2]) == NAMED[kind] and waits_with(d, d.crs[8]) == NAMED_7[kind]


def series(*crs: CrEntry) -> BatchRecord:
    return BatchRecord(id="batch-01", mode="series", crs=list(crs))


def test_series_a_queued_third_starts_on_the_first_past_a_parked_second() -> None:
    d = series(
        cr(1, status="ready"),
        cr(2, **APART["parked"]),
        cr(3, status="queued", pr=None),
        cr(4, status="queued", pr=None),
    )
    third = d.crs[2]
    pred = series_predecessor(d.crs, third)
    assert pred is not None and pred.id == "CR-1"
    assert waits_for(d.crs, third, "series") == []  # accepted once the first is ready
    assert start_on_for(d, third) == "b-1"
    third.status, third.start_on, third.branch, third.pr = "working", "b-1", "b-3", f"{PR}3"
    assert not out_of_order(d.crs, third, "series") and start_base(d, third, REPO) == "b-1"
    fourth = d.crs[3]
    assert waits_for(d.crs, fourth, "series") == ["CR-3 working"]
    d.crs[0].status = "merged"
    third.status = "ready"
    third.pr_draft = False
    nxt = next_merge(d)
    assert nxt is not None and nxt.id == "CR-3"  # the parked CR is not the next merge


def test_series_a_third_started_on_the_parked_second_is_a_dependent() -> None:
    d = series(
        cr(1, status="merged"),
        cr(2, **APART["parked"]),
        cr(3, status="ready", start_on="b-2", pr_draft=False),
        cr(4, status="queued", pr=None),
    )
    third = d.crs[2]
    assert out_of_order(d.crs, third, "series") and apart_owner(d.crs, third, "series").id == "CR-2"
    assert start_base(d, third, REPO) == "b-2" and third.start_on == "b-2"
    nxt = next_merge(d)
    assert nxt is not None and nxt.id == "CR-4"  # never the dependent
    assert ready_word(d, third, REPO) == "PR in draft"
    pred = series_predecessor(d.crs, d.crs[3])
    assert pred is not None and pred.id == "CR-1"  # skips the parked CR and its dependent
