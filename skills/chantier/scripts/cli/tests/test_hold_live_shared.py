"""The shared definition (apart, dependent, out of order, apart owner), the base rule and the
series rules, on prepared records: a CR held while it was live is the apart one."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from chantier.commands.delivery import _check_out_of_draft
from chantier.core.errors import ChantierError
from chantier.core.records import BatchRecord, CrEntry
from chantier.core.repo import Repo
from chantier.rails import apart_owner, out_of_order, series_predecessor
from chantier.stack_apart import waits_with
from chantier.stack_words import draft_waited, ready_word
from chantier.stacks import chain, next_merge, stack_base, start_base, start_on_for, top_cr

REPO = cast(Repo, SimpleNamespace(config={"default_branch": "main"}))
PR = "https://github.com/o/r/pull/"


def cr(n: int, **kw: Any) -> CrEntry:
    fields: dict[str, Any] = {
        "status": "ready",
        "pr": f"{PR}{n}",
        "order": n,
        "branch": f"b/cr-{n}",
        "pr_draft": False,
        "stacked": True,
    }
    return CrEntry(id=f"CR-{n}", **{**fields, **kw})


def held_cr(n: int, order: str = "O-1") -> CrEntry:
    return cr(n, status="blocked", held=order, stacked=False, pr_base="main")


def of(mode: str, *crs: CrEntry) -> BatchRecord:
    return BatchRecord(id="batch-01", mode=mode, crs=list(crs))


def test_three_dependents_of_a_held_cr_are_out_of_order_with_it_as_their_owner() -> None:
    d = of(
        "stack",
        held_cr(1),
        cr(2, after=["CR-1"]),
        cr(3, after=["CR-2"]),
        cr(4),  # in the stack
        cr(5, after=["CR-4", "CR-1"]),
    )
    assert [out_of_order(d.crs, x, d.mode) for x in d.crs] == [True, True, True, False, True]
    for dep in d.crs[1:3] + d.crs[4:]:
        owner = apart_owner(d.crs, dep, d.mode)
        assert owner is not None and owner.id == "CR-1"
        assert waits_with(d, dep) == "held CR-1 (order O-1)"


@pytest.mark.parametrize("after", [["CR-4", "CR-1"], ["CR-1", "CR-4"]])
def test_a_dependent_of_an_in_stack_cr_and_a_held_one_is_based_on_the_held_one(
    after: list[str],
) -> None:
    d = of("stack", held_cr(1), cr(4), cr(5, after=after, start_on="b/cr-4"))
    dep = d.crs[2]
    assert start_base(d, dep, REPO) == "b/cr-1"  # the in-stack CR is never the base
    assert stack_base(d, dep, REPO) == "b/cr-1"
    assert stack_base(d, dep, REPO, planned=True) == "b/cr-1"
    assert start_base(d, d.crs[0], REPO) == "main"  # the apart CR's own base


@pytest.mark.parametrize(
    ("after", "base"), [(["CR-2", "CR-1"], "b/cr-1"), (["CR-1", "CR-2"], "b/cr-2")]
)
def test_with_two_out_of_order_dependencies_the_last_in_after_gives_the_base(
    after: list[str], base: str
) -> None:
    d = of("stack", held_cr(1), cr(2, after=["CR-1"]), cr(3, after=after))
    assert start_base(d, d.crs[2], REPO) == base
    assert stack_base(d, d.crs[2], REPO) == base


@pytest.mark.parametrize(
    ("after", "owner"), [(["CR-2", "CR-6"], "CR-6"), (["CR-6", "CR-2"], "CR-1")]
)
def test_two_apart_owners_give_the_owner_of_the_last_candidate(
    after: list[str], owner: str
) -> None:
    d = of(
        "stack",
        held_cr(1, "O-1"),
        cr(2, after=["CR-1"]),
        cr(3, after=after),
        held_cr(6, "O-2"),
    )
    found = apart_owner(d.crs, d.crs[2], d.mode)
    assert found is not None and found.id == owner
    assert waits_with(d, d.crs[2]) == f"held {owner} (order {found.held})"
    assert start_base(d, d.crs[2], REPO) == ("b/cr-6" if owner == "CR-6" else "b/cr-2")


def test_a_held_live_cr_leaves_the_stack_and_its_dependent_reads_draft() -> None:
    d = of(
        "stack",
        cr(1),
        held_cr(2),
        cr(3, after=["CR-2"], pr_base="b/cr-2"),
        cr(4, status="queued", pr=None, stacked=False),
    )
    dep = d.crs[2]
    assert [x.id for x in chain(d)] == ["CR-1", "CR-4"]
    top, merge = top_cr(d), next_merge(d)
    assert top is not None and top.id == "CR-4" and merge is not None and merge.id == "CR-1"
    assert ready_word(d, dep, REPO) == "PR in draft"  # a dependent never reads ready to merge
    assert draft_waited(d, dep, REPO) == ("waits with held CR-2 (order O-1): `order unhold CR-2`")
    assert draft_waited(d, d.crs[1], REPO) == "held (order O-1): `order unhold CR-2`"


def series_of(*crs: CrEntry) -> BatchRecord:
    return of("series", *crs)


def test_series_a_queued_third_is_no_dependent_and_starts_on_the_first() -> None:
    first = cr(1, stacked=False)
    held = held_cr(2)
    held.start_on = None
    third = cr(3, status="queued", pr=None, stacked=False)
    fourth = cr(4, status="queued", pr=None, stacked=False)
    d = series_of(first, held, third, fourth)
    assert not out_of_order(d.crs, third, "series")
    pred = series_predecessor(d.crs, third)
    assert pred is not None and pred.id == "CR-1"  # skips the held one
    assert start_on_for(d, third) == "b/cr-1"  # recorded at its take
    assert start_base(d, third, REPO) == "b/cr-1"
    third.start_on = "b/cr-1"
    third.status, third.pr, third.pr_draft = "ready", f"{PR}3", False
    assert next_merge(d) is first  # the first's merge comes first
    first.status = "merged"
    merge = next_merge(d)
    assert merge is not None and merge.id == "CR-3"  # then the third, once it is ready


def test_series_a_third_started_on_the_held_second_keeps_it_and_waits_with_it() -> None:
    first = cr(1, status="merged", stacked=False)
    held = held_cr(2)
    third = cr(3, start_on="b/cr-2", stacked=False, pr_draft=True)
    fourth = cr(4, status="queued", pr=None, stacked=False)
    d = series_of(first, held, third, fourth)
    assert out_of_order(d.crs, third, "series")
    owner = apart_owner(d.crs, third, "series")
    assert owner is not None and owner.id == "CR-2" and third.start_on == "b/cr-2"
    third.status, third.pr_draft = "ready", False
    merge = next_merge(d)
    assert merge is None or merge.id != "CR-3"  # not the next merge even once ready
    assert ready_word(d, third, REPO) == "PR in draft"
    with pytest.raises(ChantierError, match=r"CR-3 waits with held CR-2 \(order O-1\)"):
        _check_out_of_draft(d, [third], REPO)  # the check `stack --out-of-draft` runs in a stack
    assert start_base(d, third, REPO) == "b/cr-2"  # its base stays the held second's branch
    pred = series_predecessor(d.crs, fourth)
    assert pred is not None and pred.id == "CR-1"  # skips both the held CR and its dependent
