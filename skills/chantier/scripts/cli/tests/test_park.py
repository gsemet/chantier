"""`park`: a CR stuck on an outside wait leaves the slots, the stack and the series order, and
`take` brings it back; `close` and the batch's end say its way back. On prepared records."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import batch_of, changes, events, open_batch, record, write_record
from conftest import Chantier
from test_stack_hold import PR, stacked_batch

from chantier.commands.endpause import left_open, way_back
from chantier.core.errors import EXIT_CONFLICT
from chantier.core.records import BatchRecord, CrEntry
from chantier.core.waits import make
from chantier.rails import (
    apart_owner,
    held,
    is_parked,
    out_of_order,
    series_predecessor,
    waits_for,
)

WAITS = ("--wait", "answer=which API?")


def set_status(i: int, status: str) -> Callable[[dict[str, Any]], None]:
    def mutate(data: dict[str, Any]) -> None:
        data["crs"][i]["status"] = status

    return mutate


def make_held(data: dict[str, Any]) -> None:
    data["crs"][1].update(held="O-1", stacked=False)


def make_release(data: dict[str, Any]) -> None:
    data["crs"][1].update(kind="release", status="working")


def make_fix(data: dict[str, Any]) -> None:
    data["crs"][1].update(kind="fix", status="working")


def make_parked(data: dict[str, Any]) -> None:
    data["crs"][1].update(
        status="blocked", parked="2026-11-21T10:00:00Z", blocked_reason="parked: x", stacked=False
    )


def working_stack(repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    ids = stacked_batch(repo, chantier, monkeypatch)
    data = record(repo)
    data["crs"][1].update(status="working", agent="agent-x")
    write_record(repo, data)
    return ids


@pytest.mark.parametrize(
    ("mutate", "args", "words"),
    [
        (make_held, WAITS, "is held (order O-1): the user's hold, not a park"),
        (set_status(1, "ready"), WAITS, "is ready: only a working or blocked CR is parked"),
        (make_release, WAITS, "is the release CR"),
        (make_fix, WAITS, "is a fix CR"),
        (make_parked, WAITS, "is already parked (since 10:00)"),
        (set_status(1, "working"), (), "has no outside wait recorded"),
    ],
)
def test_park_refuses_and_writes_nothing(  # noqa: PLR0913, PLR0917 - the case is three values
    repo: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    mutate: Callable[[dict[str, Any]], None],
    args: tuple[str, ...],
    words: str,
) -> None:
    ids = stacked_batch(repo, chantier, monkeypatch)
    data = record(repo)
    mutate(data)
    write_record(repo, data)
    path, log = changes(repo) / "4-batch" / "batch.json", changes(repo) / "4-batch" / "events.jsonl"
    before = (path.read_bytes(), log.read_bytes())
    code, _, err = chantier("park", ids[1], *args, "--epoch", 1)
    assert code != 0 and words in err
    assert (path.read_bytes(), log.read_bytes()) == before


def test_park_leaves_the_stack_and_take_brings_it_back_on_top(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, b, _ = working_stack(repo, chantier, monkeypatch)
    code, out, err = chantier("park", b, *WAITS, "--epoch", 1)
    assert code == 0, err
    assert out[0].startswith(f"parked {b}: waits for w1 answer since ")
    assert any(x.startswith("stack: `take stack") for x in out)
    crs = record(repo)["crs"]
    assert crs[1]["status"] == "blocked" and crs[1]["parked"]
    assert crs[1]["blocked_reason"].startswith("parked: ") and crs[1]["stacked"] is False
    assert "start_on" not in crs[2]
    _, out, _ = chantier("status")
    assert any(x.startswith(f"parked: {b} since ") and "the stack" in x for x in out)
    for args, words in [
        (("take", b, "--note", "back", "--epoch", 1), f"`wait {b} clear w1 --epoch <n>` first"),
        (("handback", b, "ready", "x"), "is parked"),
    ]:
        code, _, err = chantier(*args)
        assert code != 0 and words in err
    assert chantier("wait", b, "clear", "w1", "--epoch", 1)[0] == 0
    assert chantier("agents", "set", b, "-", "--epoch", 1)[0] == 0
    top = max(x["order"] for x in crs)
    code, out, err = chantier("take", b, "--note", "wait cleared: the answer", "--epoch", 1)
    assert code == 0 and "back on top of the stack" in out[0], err
    back = record(repo)["crs"][1]
    assert "parked" not in back and back["order"] == top + 1 and back["status"] == "working"


def test_a_parked_crs_dependents_wait_with_it_and_a_series_successor_keeps_its_base() -> None:
    crs = [
        CrEntry(id="CR-1", status="merged", order=1, branch="b/1"),
        CrEntry(id="CR-2", status="blocked", order=2, branch="b/2", parked="t"),
        CrEntry(id="CR-3", status="working", order=3, branch="b/3", start_on="b/2"),
        CrEntry(id="CR-4", status="queued", order=4, branch="b/4", after=["CR-3"]),
    ]
    d = BatchRecord(id="batch-01", mode="series", crs=crs)
    assert is_parked(crs[1]) and out_of_order(crs, crs[2], "series")
    assert apart_owner(crs, crs[3], "series").id == "CR-2"  # through the queued dependent
    pred = series_predecessor(crs, crs[2])
    assert pred is not None and pred.id == "CR-1"  # skips the parked CR
    assert waits_for(crs, crs[3], "series") == ["CR-3 working"]
    assert out_of_order(d.crs, crs[2], "series")


def test_the_way_back_of_each_kind_and_a_queued_dependent_of_them() -> None:
    d = BatchRecord(
        id="batch-01",
        mode="stack",
        crs=[
            CrEntry(id="CR-1", status="merged", order=1),
            CrEntry(id="CR-2", status="blocked", order=2, parked="t", blocked_reason="parked: q"),
            CrEntry(id="CR-3", status="ready", order=3, held="O-4"),
            CrEntry(id="CR-4", status="blocked", order=4, blocked_reason="infra: down"),
            CrEntry(id="CR-5", status="queued", order=5, after=["CR-2", "CR-4"]),
            CrEntry(id="CR-6", kind="release", status="queued", order=6, after=["CR-5", "CR-4"]),
        ],
    )
    ways = [way_back(d, c) for c in d.crs[1:]]
    assert ways[0] == (
        'CR-2 is parked, its wait cleared: `take CR-2 --note "wait cleared: <what>" --epoch <n>`'
    )
    assert ways[1] == "CR-3 is held (order O-4): the user's `order unhold CR-3`"
    assert ways[2].startswith("CR-4 is blocked (infra: down): take it back (`take CR-4 ")
    assert ways[3] == (
        "CR-5 is queued, waiting for CR-2 parked, CR-4 blocked: it starts once each is back"
    )
    assert ways[4] == (
        "CR-6 is queued, waiting for CR-2 parked, CR-4 blocked: it starts once each is back"
    )
    (line,) = left_open(d)
    assert line.startswith("batch-01: every other CR is merged or cancelled; CR-2 is parked")
    assert line.endswith("(`order drop <cr> --note <trash|P1..P4|3-ready>`)")
    d.crs[3].status = "working"  # a CR still at work: the batch is not left open
    assert left_open(d) == []


def test_close_and_the_batchs_end_name_the_parked_crs_way_back(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = open_batch(repo, chantier, monkeypatch, "A", "B", args=("--mode", "parallel"))
    data = record(repo)
    data["crs"][0].update(status="ready", pr=f"{PR}1", pr_draft=False, branch="b/1")
    data["crs"][1].update(status="working", branch="b/2")
    write_record(repo, data)
    assert chantier("park", ids[1], *WAITS, "--epoch", 1)[0] == 0
    code, out, err = chantier("order", "merged", ids[0], "--note", "merged")
    assert code == 0, err
    text = "\n".join(out)
    assert f"every other CR is merged or cancelled; {ids[1]} is parked" in text
    assert "the batch stays open until it comes back" in text
    assert record(repo)["status"] != "paused"
    code, _, err = chantier("close")
    assert code != 0 and f"cannot close batch-01: {ids[1]} is parked" in err
    assert "Nothing was deleted." in err


def test_a_parked_series_cr_comes_back_after_the_started_crs_before_the_queued_ones(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b, c, d = open_batch(
        repo, chantier, monkeypatch, "A", "B", "C", "D", args=("--mode", "series")
    )
    data = record(repo)
    data["crs"][0].update(status="merged", branch="b/1")
    data["crs"][1].update(status="working", branch="b/2")
    write_record(repo, data)
    assert chantier("park", b, *WAITS, "--epoch", 1)[0] == 0
    assert chantier("wait", b, "clear", "w1", "--epoch", 1)[0] == 0
    code, out, err = chantier("take", b, "--note", "wait cleared: the answer", "--epoch", 1)
    assert code == 0 and "back in the series after its started CRs" in out[0], err
    orders = {x["id"]: x["order"] for x in record(repo)["crs"]}
    assert orders[a] < orders[b] < orders[c] < orders[d]


def test_dropping_a_parked_cr_names_its_dependents_and_the_stack_drivers_removal(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, b, c = working_stack(repo, chantier, monkeypatch)
    data = record(repo)
    data["crs"][2]["after"] = [b]
    write_record(repo, data)
    assert chantier("park", b, *WAITS, "--epoch", 1)[0] == 0
    code, out, err = chantier("order", "drop", b, "--note", "trash")
    assert code == 0, err
    line = next(x for x in out if "was parked" in x)
    assert c in line and "no stack driver needed" not in line and "stack driver" in line


@pytest.mark.parametrize("was", ["working", "blocked"])
def test_park_of_a_working_or_blocked_cr_keeps_the_earlier_reason_and_ends_the_old_lease(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, was: str
) -> None:
    a, _ = open_batch(repo, chantier, monkeypatch, "A", "B", args=("--mode", "parallel"))
    assert chantier("take", a, "--epoch", 1)[0] == 0  # a live lease
    data = record(repo)
    data["crs"][0]["agent"] = "agent-x"
    if was == "blocked":
        data["crs"][0].update(
            status="blocked",
            blocked_reason="question: which colour?",
            waits=[make("w1", "answer", "which colour?", None, "asked")],
        )
    write_record(repo, data)
    args = WAITS if was == "working" else ()
    code, out, err = chantier("park", a, *args, "--epoch", 1)
    assert code == 0, err
    assert f"stop its Driver if it still runs, then `agents set {a} - --epoch <n>`" in out
    crs = record(repo)["crs"]
    assert crs[0]["status"] == "blocked" and crs[0]["parked"] and crs[0]["waits"]
    if was == "blocked":
        assert crs[0]["blocked_reason"] == "parked: question: which colour?"
        assert next(e for e in events(repo) if e["kind"] == "park")["was"] == (
            "question: which colour?"
        )
    else:
        assert crs[0]["blocked_reason"].startswith("parked: w1 answer since ")
        assert "was" not in next(e for e in events(repo) if e["kind"] == "park")
    assert held(batch_of(repo)) == []  # no slot held
    code, _, err = chantier.bare("note", a, "more", "--lease", 1)  # type: ignore[attr-defined]
    assert code == EXIT_CONFLICT and "claim lost" in err, err
