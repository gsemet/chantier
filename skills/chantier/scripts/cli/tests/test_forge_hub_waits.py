"""The forge hub's `waits` provider on the fake forge world: a met wait is one `wait-cleared@1`
line, a wait the forge cannot tell is named in the hub's entry, and the waits add no query."""

from __future__ import annotations

from typing import Any

import pytest
from forge_world import (
    CALLS,
    CYCLE,
    LINK,
    MAIN,
    T1,
    T2,
    World,
    crs_of,
    merged,
    write_batch,
)

from chantier.hub import waits as waits_provider

A, B = "a" * 40, "b" * 40
RED_A = {"checks": "failing", "head": A}


def _wait(wait_id: str, type_: str, ref: str, link: str) -> dict[str, Any]:
    return {
        "id": wait_id, "type": type_, "ref": ref, "link": link, "since": T1, "note": "n",
        "cleared_at": None, "cleared_by": None,
    }  # fmt: skip


def test_a_met_wait_is_told_once_and_one_the_forge_cannot_tell_is_named_in_the_hub_record(
    world: World,
) -> None:
    first, second = LINK.format("alpha", 10), LINK.format("alpha", 11)
    crs = crs_of("alpha", "blocked")
    crs[0]["waits"] = [
        _wait("w1", "pipeline", A, first),
        _wait("w2", "merge", first, first),
        _wait("w3", "approval", second, second),
        _wait("w4", "answer", "which?", ""),
    ]
    write_batch(world.project("alpha"), "running", crs)
    world.forge = {11: {"review": "unknown"}}
    world.hub.cycle(0.0)
    world.hub.cycle(CYCLE)  # the same facts again: the line is not written twice
    (line,) = world.journal("alpha")
    assert (line["type"], line["source"], line["cr"], line["wait"]) == (
        "wait-cleared@1", "hub", "CR-1", "w1",
    )  # fmt: skip
    assert line["wait_type"] == "pipeline" and line["ref"] == A
    assert world.hub.record["projects"]["alpha"]["waits_unseen"] == ["CR-1 w3"]
    assert all(len(c) <= CALLS for c in world.calls)  # the links join the one read of the cycle


GL = "https://gitlab.com/acme/alpha/-/merge_requests/{}"
APPROVED, CLOSED = {"review": "approved"}, {"state": "closed", "closed_at": T2}
WAIT_CASES: list[Any] = [  # (id, forge, wait type, wait ref, lines wanted, GitLab)
    ("gh approval approved", APPROVED, "approval", "", 1, False),
    ("gh green pipeline on the head", {}, "pipeline", A, 1, False),
    ("gh merge", merged(MAIN, T1), "merge", "", 1, False),
    ("gh red pipeline", RED_A, "pipeline", A, 0, False),
    ("gh green on another head", {}, "pipeline", B, 0, False),
    ("gh review unknown", {"review": "unknown"}, "approval", "", 0, False),
    ("gl green pipeline", {}, "pipeline", A, 1, True),
    ("gl merge", merged(MAIN, T1), "merge", "", 1, True),
    ("gl approval, unproved", APPROVED, "approval", "", 0, True),
]


def _waiting(  # noqa: PLR0913, PLR0917
    world: World,
    kind: str,
    ref: str,
    gitlab: bool,
    status: str = "blocked",
    batch: str = "running",
) -> str:
    """Alpha's CR-1 waits (w1) on its own PR, on GitHub or on GitLab; the wait's link. A paused
    batch keeps that one PR open (CR-2's merged)."""
    crs = crs_of("alpha", status)
    link = GL.format(10) if gitlab else crs[0]["pr"]
    if gitlab:
        for i, c in enumerate(crs):
            c["pr"] = GL.format(10 + i)
    crs[0]["waits"] = [_wait("w1", kind, ref or link, link)]
    if batch == "paused":
        crs[1]["status"] = "merged"
    write_batch(world.project("alpha"), batch, crs)
    return link


@pytest.mark.parametrize("case", [c[1:] for c in WAIT_CASES], ids=[c[0] for c in WAIT_CASES])
def test_a_met_wait_gives_one_line_and_an_unmet_one_none(
    world: World, case: tuple[dict[str, Any], str, str, int, bool]
) -> None:
    forge, kind, ref, lines, gitlab = case
    _waiting(world, kind, ref, gitlab)
    world.forge = {10: forge}
    world.hub.cycle(0.0)
    world.hub.cycle(CYCLE)  # never twice
    got = [e for e in world.journal("alpha") if e["type"] == "wait-cleared@1"]
    assert [(e["cr"], e["wait"], e["wait_type"]) for e in got] == [("CR-1", "w1", kind)] * lines
    if gitlab and kind == "approval":  # unproved: no review is asked and no read is made for it
        assert not any("review" in a for a in world.asked)


def test_a_wait_on_another_repository_is_not_read_and_the_read_does_not_refuse(
    world: World,
) -> None:
    other = "https://github.com/acme/elsewhere/pull/7"
    crs = crs_of("alpha", "blocked")
    crs[0]["waits"] = [_wait("w1", "merge", other, other)]
    write_batch(world.project("alpha"), "running", crs)
    world.forge = {7: merged(MAIN, T1)}
    world.hub.cycle(0.0)
    assert not any(other in c for c in world.calls)
    entry = world.hub.record["projects"]["alpha"]
    assert entry["error"] is None and entry["read_at"] and entry["waits_unseen"] == []
    assert not [e for e in world.journal("alpha") if e["type"] == "wait-cleared@1"]


@pytest.mark.parametrize("batch", ["running", "paused"])
def test_the_waits_add_no_read_one_call_per_project_and_cycle(world: World, batch: str) -> None:
    link = _waiting(world, "merge", "", False, batch=batch)
    world.forge = {10: merged(MAIN, T1)}
    world.hub.cycle(0.0)
    world.hub.cycle(CYCLE)
    alpha = [c for c in world.calls if any("/alpha/" in x for x in c)]
    assert len(alpha) == len(world.calls) // CALLS == CALLS  # one read per cycle, per project
    assert all(c.count(link) == 1 for c in alpha)
    got = [e for e in world.journal("alpha") if e["type"] == "wait-cleared@1"]
    assert [(e["cr"], e["wait"]) for e in got] == [("CR-1", "w1")]  # a paused batch's too


@pytest.mark.parametrize(
    ("kind", "ref", "unseen", "seen"),
    [
        ("approval", "", {"review": "unknown"}, {"review": "pending"}),
        ("pipeline", A, {"head": B}, {"checks": "failing"}),
        ("merge", "", CLOSED, {}),
    ],
)
def test_a_wait_the_forge_cannot_tell_is_named_with_no_line_and_leaves_when_seen_again(
    world: World, kind: str, ref: str, unseen: dict[str, Any], seen: dict[str, Any]
) -> None:
    _waiting(world, kind, ref, False)
    world.forge = {10: unseen}
    world.hub.cycle(0.0)
    assert world.hub.record["projects"]["alpha"]["waits_unseen"] == ["CR-1 w1"]
    assert not [e for e in world.journal("alpha") if e["type"] == "wait-cleared@1"]
    world.forge = {10: seen}
    world.hub.cycle(CYCLE)
    assert world.hub.record["projects"]["alpha"]["waits_unseen"] == []


@pytest.mark.parametrize("status", ["cancelled", "merged"])
def test_the_wait_of_an_ended_cr_gives_no_interest(world: World, status: str) -> None:
    _waiting(world, "merge", "", False, status)
    assert not [i for i in waits_provider.PROVIDER.collect(world.repo("alpha"))]
