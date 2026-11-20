"""The base of a CR in a stack batch: `start_base`, `stack_base` and the record's place come from
one function (`stack_start`), so the take's printed base and the record's place never differ."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from batch_helpers import open_batch, record, write_record
from conftest import Chantier

from chantier.commands.facts import stack_lines
from chantier.core.records import BatchRecord, CrEntry
from chantier.core.repo import Repo
from chantier.hub import journal
from chantier.hub.schemas import PUBLISHED
from chantier.stack_words import draft_waits, ready_word
from chantier.stacks import off_place, stack_base, stack_start, start_base, start_on_for

PR = "https://github.com/o/r/pull/"
REPO = cast(Repo, SimpleNamespace(config={"default_branch": "main", "remote": "origin"}))


def cr(n: int, **kw: Any) -> CrEntry:
    """A working CR with a PR, a branch `b-<n>` and the order `n`."""
    fields: dict[str, Any] = {
        "status": "working",
        "pr": f"{PR}{n}",
        "order": n,
        "branch": f"b-{n}",
    }
    return CrEntry(id=f"CR-{n}", **{**fields, **kw})


def noPr(n: int, **kw: Any) -> CrEntry:
    return cr(n, pr=None, **kw)


def placed(n: int) -> CrEntry:
    return cr(n, stacked=True)


STACKED = [placed(1), placed(2), placed(3), placed(4)]
BELOW = [cr(5), noPr(6, status="queued"), noPr(7, status="queued")]
CASES = [
    # (id, crs, the CR asked, expected base)
    ("A", [*STACKED, cr(5, after=["CR-3", "CR-2", "CR-1"], pr_base="b-1")], 5, "b-4"),
    ("B", [noPr(1), noPr(2), noPr(3), noPr(4, status="queued", after=["CR-3", "CR-1"])], 4, "b-3"),
    ("B2", [noPr(1), cr(2), noPr(3), noPr(4, status="queued", after=["CR-1"])], 4, "b-2"),
    ("C", [*BELOW, cr(8, after=[], start_on="b-5", pr_base="b-5")], 8, "b-5"),
    ("D", [cr(5), noPr(6, status="queued"), noPr(7), cr(8, after=[], pr_base="b-5")], 8, "b-5"),
    ("D2", [noPr(1), noPr(2), noPr(3, status="queued")], 3, "main"),
    ("F", [cr(1), noPr(2, status="queued", after=["CR-3"]), noPr(3, status="queued")], 2, "b-3"),
]


@pytest.mark.parametrize(("crs", "n", "want"), [c[1:] for c in CASES], ids=[c[0] for c in CASES])
def test_one_function_names_the_base_of_an_unplaced_cr(
    crs: list[CrEntry], n: int, want: str
) -> None:
    d = BatchRecord(id="batch-01", mode="stack", crs=crs)
    c = next(x for x in crs if x.id == f"CR-{n}")
    assert start_base(d, c, REPO) == want
    assert stack_base(d, c, REPO) == want
    assert stack_base(d, c, REPO, planned=True) == want
    by_branch = {x.branch: x for x in crs}
    open_deps = {x.branch for x in crs if x.id in c.after}
    owner = by_branch.get(want)
    assert want == "main" or want in open_deps or (owner is not None and owner.pr)


def test_a_cr_off_its_place_is_to_stack_on_the_cr_below_that_has_a_pr() -> None:
    crs = [*STACKED, cr(5, after=["CR-3", "CR-2", "CR-1"], pr_base="b-1")]
    d = BatchRecord(id="batch-01", mode="stack", crs=crs)
    assert off_place(d, crs[4], REPO) == ("b-1", "CR-4")
    row = stack_lines(REPO, "batch-01", d)[-1]
    assert row.startswith("CR-5 ") and row.endswith("(note rebase: stacked on CR-4)")
    crs[4].pr_base = "b-4"
    assert off_place(d, crs[4], REPO) is None


def test_a_cr_taken_on_a_pr_stays_on_it_and_is_on_its_place() -> None:
    d = BatchRecord(id="batch-01", mode="stack", crs=[*BELOW, cr(8, start_on="b-5", pr_base="b-5")])
    assert off_place(d, d.crs[3], REPO) is None
    assert " base b-5 " in stack_lines(REPO, "batch-01", d)[-1]


@pytest.mark.parametrize(
    ("n", "want"), [(1, "main"), (2, "b-1"), (4, "b-3")], ids=["first", "second", "fourth"]
)
def test_a_placed_cr_keeps_the_cr_just_below_it(n: int, want: str) -> None:
    d = BatchRecord(id="batch-01", mode="stack", crs=[*STACKED, noPr(5, status="queued")])
    assert stack_base(d, d.crs[n - 1], REPO) == want
    assert stack_base(d, d.crs[n - 1], REPO, planned=True) == want


def test_start_base_of_a_placed_cr_with_no_pr_is_the_default_branch() -> None:
    crs = [placed(1), placed(2), placed(3).model_copy(update={"pr": None})]
    d = BatchRecord(id="batch-01", mode="stack", crs=crs)
    assert start_base(d, crs[2], REPO) == "main"


def test_take_prints_the_base_the_stack_row_shows(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = open_batch(
        repo, chantier, monkeypatch, "A", "B", "C", "D", args=("--mode", "stack", "--slots", 4)
    )
    data = record(repo)
    for i, c in enumerate(data["crs"], 1):
        c["order"] = i
    for c in data["crs"][:3]:
        c["status"] = "ready"  # handed back with no PR: open, with a branch of its own
    data["crs"][3]["after"] = [ids[2], ids[0]]
    write_record(repo, data)
    code, out, err = chantier("take", ids[3], "--epoch", 1)
    assert code == 0, err
    branch = next(c["branch"] for c in record(repo)["crs"] if c["id"] == ids[2])
    line = next(x for x in out if x.startswith("worktree: "))
    assert f" base {branch};" in line
    rows = chantier("take", "stack", "--epoch", 1)[1]
    assert next(x for x in rows if x.startswith(f"{ids[3]} ")).count(f" base {branch} ") == 1


LANDED = [
    # (id, crs, the CR asked, landed, without the set, with it)
    ("below", [cr(1), cr(2), noPr(3, status="queued")], 3, {"CR-2"}, "b-2", "b-1"),
    ("below-all", [cr(1), cr(2), noPr(3, status="queued")], 3, {"CR-1", "CR-2"}, "b-2", "main"),
    (
        "live-start-on",
        [cr(1), cr(2), noPr(3, status="queued", start_on="b-2")],
        3,
        {"CR-2"},
        "b-2",
        "b-1",
    ),
    (
        "dependency",
        [noPr(1), cr(2), noPr(3, status="queued", after=["CR-2"])],
        3,
        {"CR-2"},
        "b-2",
        "main",
    ),
    ("empty-set", [cr(1), cr(2), noPr(3, status="queued")], 3, set(), "b-2", "b-2"),
]


@pytest.mark.parametrize(
    ("crs", "n", "landed", "plain", "want"), [c[1:] for c in LANDED], ids=[c[0] for c in LANDED]
)
def test_a_cr_seen_merged_is_no_start_base(
    crs: list[CrEntry], n: int, landed: set[str], plain: str, want: str
) -> None:
    d = BatchRecord(id="batch-01", mode="stack", crs=crs)
    c = next(x for x in crs if x.id == f"CR-{n}")
    seen = frozenset(landed)
    assert start_base(d, c, REPO) == plain
    assert start_base(d, c, REPO, seen) == want
    assert stack_start(d, c, REPO, seen) == want
    expected = None if want == "main" else want
    if not c.start_on and not c.after:
        assert start_on_for(d, c, seen) == expected


def test_a_series_predecessor_and_the_release_top_skip_a_cr_seen_merged() -> None:
    top = CrEntry(id="CR-9", status="working", order=9, branch="b-9", kind="release")
    crs = [cr(1), cr(2), top]
    seen = frozenset({"CR-2"})
    series = BatchRecord(id="batch-01", mode="series", crs=crs)
    assert start_base(series, crs[1], REPO, seen) == "b-1"
    assert start_base(series, crs[2], REPO, seen) == "b-1"
    assert start_base(series, crs[2], REPO) == "b-2"
    assert start_base(series, noPr(3, order=3), REPO, seen) == "main"


WORDS = [
    # (id, the CR asked ("c"), other CRs, its word, what it waits for)
    ("default", {"pr_base": "main"}, [noPr(1)], "ready to merge", "its turn out of draft"),
    (
        "default-draft",
        {"pr_base": "main", "pr_draft": True},
        [noPr(1)],
        "PR in draft",
        "its turn out of draft",
    ),
    (
        "open-ready",
        {"pr_base": "b-1"},
        [cr(1, status="ready", pr_draft=False, pr_base="main")],
        "ready to merge",
        "its turn out of draft",
    ),
    (
        "open-not-ready",
        {"pr_base": "b-1"},
        [cr(1, status="ready", pr_draft=True)],
        "PR in draft",
        "CR-1",
    ),
    ("open-working", {"pr_base": "b-1"}, [cr(1)], "PR in draft", "CR-1"),
    (
        "merged",
        {"pr_base": "b-1"},
        [cr(1, status="merged"), noPr(2)],
        "PR in draft",
        "CR-2",
    ),
    ("no-cr", {"pr_base": "elsewhere"}, [noPr(1)], "PR in draft", "elsewhere"),
    ("cancelled", {"pr_base": "b-1"}, [cr(1, status="cancelled")], "PR in draft", "CR-1"),
    ("no-base", {}, [noPr(1)], "PR in draft", "CR-1"),
    (
        "loop",
        {"pr_base": "b-1"},
        [cr(1, status="ready", pr_draft=False, pr_base="b-9")],
        "PR in draft",
        "CR-1",
    ),
    (
        "placed",
        {"pr_base": "main", "stacked": True},
        [noPr(1)],
        "PR in draft",
        "CR-1",
    ),
]


@pytest.mark.parametrize(
    ("fields", "others", "word", "waits"), [w[1:] for w in WORDS], ids=[w[0] for w in WORDS]
)
def test_a_ready_cr_not_placed_reads_its_word_from_its_pr_base(
    fields: dict[str, Any], others: list[CrEntry], word: str, waits: str
) -> None:
    me = cr(9, status="ready", pr_draft=fields.get("pr_draft", False), order=9)
    for k, v in fields.items():
        setattr(me, k, v)
    d = BatchRecord(id="batch-01", mode="stack", crs=[*others, me])
    assert ready_word(d, me, REPO) == word
    if word == "PR in draft":
        assert draft_waits(d, me, REPO) == waits


def test_two_crs_on_each_others_branches_read_pr_in_draft() -> None:
    a = cr(1, status="ready", pr_draft=False, pr_base="b-2")
    b = cr(2, status="ready", pr_draft=False, pr_base="b-1")
    d = BatchRecord(id="batch-01", mode="stack", crs=[a, b])
    assert ready_word(d, a, REPO) == ready_word(d, b, REPO) == "PR in draft"


def test_seen_merged_counts_a_listed_line_of_this_batch_cr_and_pr(tmp_path: Path) -> None:
    mine = {"type": "merged@1", "v": journal.VERSION, **PUBLISHED["merged@1"].example}
    mine["pr"] = f"{PR}88"
    crs = [cr(12, pr=f"{PR}88")]
    d = BatchRecord(id="batch-29", crs=crs)

    def seen(*lines: dict[str, Any], batch: BatchRecord = d) -> frozenset[str]:
        (tmp_path / journal.FILE).write_text(
            "".join(json.dumps(x) + chr(10) for x in lines), encoding="utf-8"
        )
        return journal.seen_merged(journal.read(tmp_path)[0], batch)

    assert seen(mine) == {"CR-12"}
    assert seen({**mine, "landed_with": "CR-13", "landed_at": "2026-11-18T10:02:00Z"}) == {"CR-12"}
    assert seen(mine, batch=BatchRecord(id="batch-30", crs=crs)) == frozenset()
    assert seen({**mine, "pr": f"{PR}89"}) == frozenset()
    assert seen({**mine, "cr": "CR-13"}) == frozenset()
    assert seen({**mine, "v": journal.VERSION + 1}) == frozenset()
    assert seen({**mine, "merged_at": 5}) == frozenset()
