"""The board's `needs_you`: what needs the user, from a prepared project state, with its keys."""

from __future__ import annotations

import json
from typing import Any

import pytest
from forge_world import World, crs_of, write_batch

from chantier.board.needs import needs_you
from chantier.board.state import project_line, project_state
from chantier.core import waits

APPROVE = "https://github.com/acme/alpha/pull/77"
T1, T2, T3, T4 = (f"2026-11-2{n}T10:00:00Z" for n in (1, 2, 3, 4))

KEYS = [
    f"question:i:idea:w1:{T4}",
    f"approval:CR-2:w2:{T3}",
    f"blocked:CR-4:{T3}",
    f"question:CR-1:w1:{T2}",
    f"merge:CR-3:{T1}",
]


def _wait(wait_id: str, type_: str, ref: str, link: str | None, since: str, **more: Any) -> Any:
    return waits.make(wait_id, type_, ref, link, "a note") | {"since": since} | more


def _event(kind: str, cr: str, t: str, **more: Any) -> dict[str, Any]:
    return {"t": t, "actor": "x", "kind": kind, "cr": cr, **more}


def _write_events(world: World, events: list[dict[str, Any]]) -> None:
    path = world.project("alpha") / "changes" / "4-batch" / "events.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")


def _state(world: World, status: str = "running", /, **tweak: Any) -> dict[str, Any]:
    """Alpha's batch: CR-1 asks (answer wait), CR-2 wants an approval, CR-3 is ready to merge,
    CR-4 is blocked; plus a pipeline wait, a merge wait, a cleared wait and a merged CR's wait."""
    crs = crs_of("alpha", "ready", 5)
    crs[0].update(status="working", waits=[_wait("w1", "answer", "Which way?", None, T2)])
    crs[1].update(status="working", waits=[_wait("w2", "approval", "", APPROVE, T3)])
    crs[3].update(status="blocked", blocked_reason="no key")
    crs[4].update(
        status="merged",
        waits=[_wait("w9", "answer", "gone?", None, T4)],
    )
    crs[2]["waits"] = [
        _wait("w3", "pipeline", "p", None, T4),
        _wait("w4", "merge", "m", None, T4),
        _wait("w5", "answer", "done", None, T4, cleared_at=T4, cleared_by="hand"),
    ]
    for c in crs:
        c.update(tweak.get(c["id"], {}))
    write_batch(world.project("alpha"), status, crs)
    _write_events(
        world,
        [
            _event("take", "CR-3", T1),
            _event("handback", "CR-3", T1, result="ready"),
            _event("take", "CR-4", T3),
        ],
    )
    repo = world.repo("alpha")
    item = world.project("alpha") / "changes" / "2-backlog" / "P2" / "idea"
    item.mkdir(parents=True, exist_ok=True)
    (item / "01-intent.md").write_text("# Idea\n", encoding="utf-8")
    (item / waits.FILE).write_text(
        waits.file_text([_wait("w1", "answer", "Q backlog", None, T4)]), encoding="utf-8"
    )
    state = project_state("alpha", repo, True, None)
    state["seat"] = {"title": "Chief of Staff - alpha", "env": "claude-code"}
    return state


def _by_kind(entries: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for e in entries:
        out.setdefault(e["kind"], []).append(e)
    return out


def test_the_four_kinds_come_from_the_record_and_the_planning_folder_newest_first(
    world: World,
) -> None:
    entries = needs_you(_state(world))
    assert [e["key"] for e in entries] == KEYS
    by = _by_kind(entries)
    assert sorted(by) == ["approval", "blocked", "merge", "question"]
    questions = {e["cr"]: e for e in by["question"]}
    assert questions["CR-1"]["text"] == "Which way?"
    assert questions["CR-1"]["session"] == "Chief of Staff - alpha"
    assert questions[None]["item"] == "idea" and questions[None]["text"] == "Q backlog"
    assert questions[None]["key"] == f"question:i:idea:w1:{T4}"
    (approval,) = by["approval"]
    assert (approval["cr"], approval["pr"], approval["since"]) == ("CR-2", APPROVE, T3)
    (blocked,) = by["blocked"]
    assert (blocked["cr"], blocked["text"], blocked["pr"]) == ("CR-4", "no key", None)
    assert blocked["key"] == f"blocked:CR-4:{T3}"
    (merge,) = by["merge"]
    assert merge["key"] == f"merge:CR-3:{T1}" and merge["since"] == T1
    assert (merge["merge_place"], merge["merge_total"]) == (1, 1)
    assert merge["pr"] == "https://github.com/acme/alpha/pull/12"
    assert len(entries) == len(KEYS)  # no pipeline or merge wait, no cleared, no merged CR's
    sinces = [e["since"] for e in entries]
    assert sinces == sorted(sinces, reverse=True)


def test_the_project_line_carries_the_entries(world: World) -> None:
    state = _state(world)
    assert project_line("alpha", state)["needs_you"] == needs_you(state)


def test_a_cr_ready_to_merge_with_an_open_approval_gives_two_entries(world: World) -> None:
    state = _state(world, **{"CR-3": {"waits": [_wait("w7", "approval", "", APPROVE, T2)]}})
    mine = [e for e in needs_you(state) if e["cr"] == "CR-3"]
    assert sorted(e["kind"] for e in mine) == ["approval", "merge"]
    assert len({e["key"] for e in mine}) == len(mine)


def test_a_paused_batch_gives_the_same_entries(world: World) -> None:
    running = needs_you(_state(world))
    assert needs_you(_state(world, "paused")) == running and running


def test_merge_and_blocked_follow_state_at_never_updated(world: World) -> None:
    before = needs_you(_state(world, **{"CR-3": {"updated": T1}, "CR-4": {"updated": T1}}))
    after = needs_you(_state(world, **{"CR-3": {"updated": T4}, "CR-4": {"updated": T4}}))
    assert [e["key"] for e in before] == [e["key"] for e in after]
    state = _state(world)
    row = next(c for c in state["batch"]["crs"] if c["cr"] == "CR-3")
    row["times"] = {"state_at": None}
    row["handed_back_at"] = T2
    assert f"merge:CR-3:{T2}" in [e["key"] for e in needs_you(state)]
    row["handed_back_at"] = None
    merge = next(e for e in needs_you(state) if e["kind"] == "merge")
    assert (merge["key"], merge["since"]) == ("merge:CR-3:", None)
    assert needs_you(state)[-1] == merge  # an entry with no time comes last


@pytest.mark.parametrize(
    "change",
    [
        {"CR-1": {"waits": []}},  # the wait cleared
        {"CR-3": {"status": "merged"}},  # the CR merged
        {"CR-4": {"status": "working", "blocked_reason": None}},  # no longer blocked
    ],
)
def test_an_entry_leaves_when_its_fact_ends(world: World, change: dict[str, Any]) -> None:
    before = {e["key"] for e in needs_you(_state(world))}
    after = {e["key"] for e in needs_you(_state(world, **change))}
    assert len(before - after) == 1 and not after - before


def test_a_cr_blocked_again_has_a_new_key(world: World) -> None:
    first = next(e for e in needs_you(_state(world)) if e["kind"] == "blocked")
    _write_events(world, [_event("take", "CR-4", T1), _event("take", "CR-4", T4)])
    repo = world.repo("alpha")
    state = project_state("alpha", repo, True, None)
    again = next(e for e in needs_you(state) if e["kind"] == "blocked")
    assert again["key"] != first["key"] and again["since"] == T4
