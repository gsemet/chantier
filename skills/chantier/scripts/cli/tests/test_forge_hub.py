"""The forge hub and `chantier watch`: the election, the cycle, the journal both the hub and the
board's page write, the watcher's end, its refusals and what `status` says.

No test reaches a forge (`forge_read.read` is replaced) and none sleeps: the cycle and the end
are driven with an injected monotonic time."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import changes, name_server, open_batch, record
from conftest import Chantier
from forge_world import (
    B1,
    BOARD_LINE,
    CALLS,
    CYCLE,
    LINK,
    MAIN,
    NEW_VERSION,
    QUIET,
    T1,
    T2,
    World,
    crs_of,
    merged,
    shape,
    write_batch,
)

from chantier import __version__
from chantier.board import prs
from chantier.core.errors import ChantierError
from chantier.core.repo import Repo
from chantier.hub import journal, lock, state
from chantier.hub.autostart import watch_command
from chantier.hub.watch import EVENTS, Watch

RED_A, RED_B = {"checks": "failing", "head": "a" * 40}, {"checks": "failing", "head": "b" * 40}
A, B = "a" * 40, "b" * 40
# (what the forge shows for alpha's PRs 10 and 11 at each cycle, alpha's journal after it)
CYCLES: list[Any] = [
    (
        "merged into main, once",
        [{10: merged(MAIN, T1)}, {10: merged(MAIN, T1)}],
        [[(1, "hub", "merged", "CR-1", None)]] * 2,
    ),
    (
        "into another CR's branch, then landed",
        [{11: merged(B1, T1)}, {11: merged(B1, T1), 10: merged(MAIN, T2)}],
        [
            [(1, "hub", "merged", "CR-2", None)],
            [
                (1, "hub", "merged", "CR-2", None),
                (2, "hub", "merged", "CR-1", None),
                (3, "hub", "merged", "CR-2", "CR-1"),
            ],
        ],
    ),
    (
        "red CI by head",
        [{10: RED_A}, {10: RED_A}, {10: RED_B}],
        [
            [(1, "hub", "checks-red", "CR-1", A)],
            [(1, "hub", "checks-red", "CR-1", A)],
            [(1, "hub", "checks-red", "CR-1", A), (2, "hub", "checks-red", "CR-1", B)],
        ],
    ),
]


@pytest.mark.parametrize(("label", "reads", "expected"), CYCLES, ids=[c[0] for c in CYCLES])
def test_a_hub_cycle_writes_each_event_once(
    world: World, label: str, reads: list[dict[int, Any]], expected: list[list[tuple[Any, ...]]]
) -> None:
    for step, (forge, want) in enumerate(zip(reads, expected, strict=True)):
        world.forge = forge
        world.hub.cycle(step * CYCLE)
        assert shape(world.journal("alpha")) == want, label
        assert world.journal("beta") == []  # an event lands in its own project's journal only
        assert world.journal("gamma") == world.journal("delta") == []


def test_a_hub_cycle_reads_only_what_there_is_to_read_and_is_due_every_twenty_seconds(
    world: World,
) -> None:
    assert world.hub.due(0.0)
    world.hub.cycle(0.0)
    assert not world.hub.due(CYCLE - 1) and world.hub.due(CYCLE)
    # alpha and beta are read, one call each; gamma is paused and delta has no PR left open
    assert sorted(c[0] for c in world.calls) == [LINK.format("alpha", 10), LINK.format("beta", 20)]
    assert len(world.calls) == CALLS
    # a PR failing but not ready to merge in the record gives no event
    write_batch(world.project("alpha"), "running", crs_of("alpha", "working"))
    world.forge = {10: RED_A}
    world.hub.cycle(CYCLE)
    assert world.journal("alpha") == []


def test_a_forge_error_lands_in_the_hub_record_not_in_the_journal(world: World) -> None:
    git_dir = world.repo("alpha").git_dir
    world.failure = ChantierError("gh: not found on PATH", 4)
    world.hub.cycle(0.0)
    mine = state.live_entry(git_dir, state.HUB)
    assert mine is not None
    assert mine["projects"]["alpha"]["error"] == "gh: not found on PATH"
    assert world.journal("alpha") == [] and world.journal("beta") == []
    world.failure = None
    world.hub.cycle(CYCLE)
    mine = state.live_entry(git_dir, state.HUB)
    assert mine is not None and mine["projects"]["alpha"]["error"] is None
    assert mine["projects"]["alpha"]["read_at"]


def test_a_native_stack_merged_in_one_go_is_told_landed_with_its_bottom(world: World) -> None:
    write_batch(world.project("alpha"), "running", crs_of("alpha", count=3))
    on_default = {"merged_on_default": True}
    world.forge = {
        10: {**merged(MAIN, T1), **on_default},
        11: {**merged(B1, "2026-11-18T10:00:01Z"), **on_default},
        12: {**merged("chantier/b/cr-2", "2026-11-18T10:00:02Z"), **on_default},
    }
    world.hub.cycle(0.0)
    world.hub.cycle(CYCLE)  # read again: still one line each
    entries = [e for e in world.journal("alpha") if e["kind"] == "merged"]
    assert [(e["cr"], e.get("landed_with")) for e in entries] == [
        ("CR-1", None),
        ("CR-2", "CR-1"),
        ("CR-3", "CR-1"),
    ]
    told = [journal.merged_text(e) for e in entries[1:]]
    assert told == [
        f"forge saw merged: CR-{n} {LINK.format('alpha', 9 + n)} into CR-{n - 1}'s branch at "
        f"{at}, landed with CR-1 at {T1}; for the Chief of Staff: order merged CR-{n}"
        for n, at in ((2, "2026-11-18T10:00:01Z"), (3, "2026-11-18T10:00:02Z"))
    ]


@pytest.mark.parametrize("first", ["board", "hub"])
def test_the_board_and_the_hub_share_the_journal_once(world: World, first: str) -> None:
    world.forge = {10: merged(MAIN, T1)}
    repo = world.repo("alpha")

    def board() -> None:
        withpr = [
            {
                "cr": c["id"],
                "title": "",
                "kind": None,
                "pr": c["pr"],
                "branch": c["branch"],
                "to_review": True,
                "state": "ready",
            }
            for c in crs_of("alpha")
        ]
        rows = prs.rows_of(withpr, world.read([c["pr"] for c in withpr]), {})
        journal.append(repo, [BOARD_LINE], "board")  # a board line never blocks the merge
        journal.append(repo, journal.merged_events("batch-01", rows), "board")

    if first == "board":
        board()
        world.hub.cycle(0.0)
    else:
        world.hub.cycle(0.0)
        board()
    (only,) = (e for e in world.journal("alpha") if e["kind"] == "merged")
    assert (only["source"], only["cr"]) == (first, "CR-1")


def test_the_start_line_names_the_hub_and_a_hub_of_another_version(world: World) -> None:
    beta = world.repo("beta")
    world.hub.close()
    held = lock.HubLock(beta.git_dir)
    assert held.acquire()  # another process is the hub
    for version, tail in ((NEW_VERSION, ""), ("0.0.1", f"; hub is chantier {NEW_VERSION}")):
        state.write_hub(beta.git_dir, state.hub_record(NEW_VERSION))
        w = Watch(beta, 3, version)
        assert w.start_line() == f"watch: beta from cursor 3 for project{tail}"
        w.close()
    held.release()
    w = Watch(beta, 0, NEW_VERSION)
    assert w.start_line() == "watch: beta from cursor 0 for project, the hub"
    w.close()
    state.remove_entry(beta.git_dir, state.HUB, os.getpid())
    tail = "; board is chantier 0.0.1: its writes do not reach this watcher, restart it"
    for version, said in (("0.0.1", tail), (NEW_VERSION, "")):
        name_server(beta.git_dir, version=version)  # a live server: no watcher is the hub
        w = Watch(beta, 0, NEW_VERSION)
        assert w.start_line() == f"watch: beta from cursor 0 for project{said}"
        w.close()
    state.remove_entry(beta.git_dir, state.SERVER, os.getpid())
    w = Watch(beta, 0, NEW_VERSION)
    assert (
        w.start_line() == "watch: beta from cursor 0 for project, the hub"
    )  # no live entry: nothing said
    w.close()


CONFIGS = [
    ({"key": "batch.slots", "old": 4, "new": 6, "batch": "batch-01"},
     "config changed on the board: batch.slots 4 -> 6; batch-01 keeps 4 until an order slots"),
    ({"key": "batch.slots", "old": 4, "new": 6, "batch": None},
     "config changed on the board: batch.slots 4 -> 6; from the next open (no batch)"),
    ({"key": "specifying.parallel", "old": 4, "new": 6, "batch": "batch-01"},
     "config changed on the board: specifying.parallel 4 -> 6"),
    ({"key": "specifying.parallel", "old": 4, "new": 2, "batch": None},
     "config changed on the board: specifying.parallel 4 -> 2"),
]  # fmt: skip


@pytest.mark.parametrize(("event", "text"), CONFIGS, ids=["slots", "slots-none", "up", "down"])
def test_a_config_line_ends_the_watcher_and_is_told_in_its_form(
    repo: Path, event: dict[str, Any], text: str
) -> None:
    folder = repo / ".agents" / "changes" / "4-batch"
    folder.mkdir(parents=True)
    data = {"id": "batch-01", "status": "running", "crs": []}
    (folder / "batch.json").write_text(json.dumps(data), encoding="utf-8")
    found = Repo.find()
    w = Watch(found, 0, __version__)
    journal.append(found, [{"kind": "config", **event}], "board")
    ended = next(((t, r) for t in range(60) if (r := w.poll(float(t)))), None)
    w.close()
    assert ended == (int(QUIET), EVENTS)
    again = "still running: for the Chief of Staff, start again in the background now: "
    last = f"watch: batch-01 {again}{watch_command(found, 1)}"
    assert w.lines(EVENTS) == [text, last]


def test_status_and_the_start_line_name_the_journal_the_hub_and_its_version(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b, c, d = open_batch(repo, chantier, monkeypatch, "Alpha", "Beta", "Gamma", "Delta")
    found = Repo.find()
    batch = record(repo)["id"]
    base = {"kind": "merged", "batch": batch, "pr": "P", "into": "main", "merged_at": "t"}
    stacked = {**base, "into": "chantier/b/cr-0", "into_cr": a}
    journal.append(
        found,
        [
            {**base, "cr": a, "into_cr": None},
            {**stacked, "cr": b},
            {**stacked, "cr": c},
            {**stacked, "cr": c, "landed_with": a, "landed_at": "u"},
            journal.red_event(batch, d, "P", "d" * 40),
        ],
        "hub",
    )

    def forge_lines() -> list[str]:
        return [x for x in chantier("status")[1] if x.startswith(("forge ", "watch:"))]

    order = "for the Chief of Staff: order merged"
    got = forge_lines()
    last = 5  # the journal's highest seq
    assert got[0] == "forge hub: none running" and got[-1].startswith("watch: not running:")
    assert f" watch --after {last}; after the user's no" in got[-1]
    assert got[-1].endswith(f" watch --once --after {last}") and "watch: chantier watch" not in got
    got = got[1:-1]
    assert got[0] == f"forge saw merged: {a} P into main at t; {order} {a}"
    assert got[1] == (
        f"forge saw merged: {b} P into {a}'s branch at t; for the Chief of Staff: not landed, "
        f"tell the user, record nothing until {a} lands"
    )
    assert (
        got[2]
        == f"forge saw merged: {c} P into {a}'s branch at t, landed with {a} at u; {order} {c}"
    )
    assert not any("checks red" in x for x in got)
    git, pid = found.git_dir, os.getpid()
    state.write_hub(git, state.hub_record("0.0.1"))
    hub = f"forge hub: PID {pid}, a watcher, last read none yet"
    assert forge_lines()[0] == f"{hub}; hub is chantier 0.0.1"
    state.write_hub(git, state.hub_record(__version__))
    assert forge_lines()[0] == hub
    name_server(git)  # the hub's PID is the live server's
    assert forge_lines()[0] == hub.replace("a watcher", "the surface server")
    assert (changes(repo) / journal.FILE).is_file()
