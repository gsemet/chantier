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
from batch_helpers import changes, open_batch, record
from conftest import Chantier, Surface

from chantier import __version__
from chantier.board import forge_read, prs
from chantier.commands.forge_stack_gh import pr_parts
from chantier.core.errors import ChantierError
from chantier.core.repo import Repo
from chantier.hub import journal, lock
from chantier.hub import times as hub_times
from chantier.hub.autostart import watch_command
from chantier.hub.cycle import Hub
from chantier.hub.watch import EVENTS, NO_BATCH, Watch

LINK = "https://github.com/acme/{}/pull/{}"
OPEN: dict[str, Any] = {
    "state": "open",
    "conflicting": False,
    "checking": False,
    "checks": "green",
    "base": "main",
    "head": "a" * 40,
    "merged_at": None,
    "closed_at": None,
}
T1, T2 = "2026-11-18T10:00:00Z", "2026-11-18T10:00:05Z"
MAIN, B1 = "main", "chantier/b/cr-1"
FIRST_PR = {"alpha": 10, "beta": 20, "gamma": 30, "delta": 40}
CYCLE, QUIET = 20.0, 20.0
EXIT_USAGE, EXIT_PRECONDITION = 1, 2
NEW_VERSION = "9.9.9"
CALLS = 2  # alpha and beta: one call each


def crs_of(name: str, state: str = "ready", count: int = 2) -> list[dict[str, Any]]:
    return [
        {
            "id": f"CR-{i + 1}",
            "status": state,
            "order": i,
            "pr": LINK.format(name, FIRST_PR[name] + i),
            "pr_draft": False,
            "pr_base": "main",
            "branch": f"chantier/b/cr-{i + 1}",
        }
        for i in range(count)
    ]


def write_batch(project: Path, status: str, crs: list[dict[str, Any]]) -> None:
    folder = project / "changes" / "4-batch"
    folder.mkdir(parents=True, exist_ok=True)
    data = {"id": "batch-01", "status": status, "settings": {"default_branch": "main"}, "crs": crs}
    (folder / "batch.json").write_text(json.dumps(data), encoding="utf-8")


class World:
    """A surface of four projects: alpha and beta run a batch of two ready CRs, gamma's is paused,
    delta's CRs are merged. The forge answers `forge` (a PR number to the fields that differ
    from `OPEN`); every call of the seam is kept in `calls`."""

    def __init__(self, surface: Surface, monkeypatch: pytest.MonkeyPatch) -> None:
        self.root = surface.root
        write_batch(self.project("alpha"), "running", crs_of("alpha"))
        write_batch(self.project("beta"), "running", crs_of("beta"))
        write_batch(self.project("gamma"), "paused", crs_of("gamma"))
        write_batch(self.project("delta"), "running", crs_of("delta", "merged"))
        self.forge: dict[int, dict[str, Any]] = {}
        self.calls: list[list[str]] = []
        self.failure: Exception | None = None
        monkeypatch.setattr(forge_read, "read", self.read)
        self.hub = Hub(self.repo("alpha"), NEW_VERSION)

    def project(self, name: str) -> Path:
        folder = self.root / "projects" / name
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def repo(self, name: str) -> Repo:
        return Repo.find(self.root, str(self.project(name)))

    def read(self, links: list[str]) -> dict[int, dict[str, Any]]:
        self.calls.append(links)
        if self.failure:
            raise self.failure
        return {n: {**OPEN, **self.forge.get(n, {})} for n in (int(pr_parts(x)[3]) for x in links)}

    def journal(self, name: str) -> list[dict[str, Any]]:
        return journal.read(self.repo(name).changes)[0]


@pytest.fixture
def world(surface: Surface, monkeypatch: pytest.MonkeyPatch) -> World:
    return World(surface, monkeypatch)


def merged(base: str, at: str) -> dict[str, Any]:
    return {"state": "merged", "base": base, "merged_at": at}


def shape(entries: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    """(seq, by, kind, cr, landed_with or head) of each line."""
    return [
        (e["seq"], e["by"], e["kind"], e["cr"], e.get("landed_with") or e.get("head"))
        for e in entries
    ]


def test_one_watcher_holds_the_hub_lock_and_the_next_takes_it(repo: Path) -> None:
    found = Repo.find()
    first, second = lock.HubLock(found.git_dir), lock.HubLock(found.git_dir)
    assert (first.acquire(), second.acquire()) == (True, False)
    hub = Hub(found, NEW_VERSION)
    held = lock.live(found.git_dir)
    assert held is not None
    assert (held["pid"], held["version"]) == (os.getpid(), NEW_VERSION)
    hub.close()
    first.release()
    assert lock.live(found.git_dir) is None
    assert not (found.git_dir / "chantier" / "hub.json").exists()
    assert second.acquire() is True
    second.release()


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
    mine = lock.live(git_dir)
    assert mine is not None
    assert mine["projects"]["alpha"]["error"] == "gh: not found on PATH"
    assert world.journal("alpha") == [] and world.journal("beta") == []
    world.failure = None
    world.hub.cycle(CYCLE)
    mine = lock.live(git_dir)
    assert mine is not None and mine["projects"]["alpha"]["error"] is None
    assert mine["projects"]["alpha"]["read_at"]


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
        journal.append(repo, journal.merged_events("batch-01", rows), "board")

    if first == "board":
        board()
        world.hub.cycle(0.0)
    else:
        world.hub.cycle(0.0)
        board()
    (only,) = world.journal("alpha")
    assert (only["seq"], only["by"], only["cr"]) == (1, first, "CR-1")


def test_the_start_line_names_the_hub_and_a_hub_of_another_version(world: World) -> None:
    beta = world.repo("beta")
    world.hub.close()
    held = lock.HubLock(beta.git_dir)
    assert held.acquire()  # another process is the hub
    for version, tail in ((NEW_VERSION, ""), ("0.0.1", f"; hub is chantier {NEW_VERSION}")):
        lock.write(beta.git_dir, lock.start_record(NEW_VERSION))
        w = Watch(beta, 3, version)
        assert w.start_line() == f"watch: beta from cursor 3{tail}"
        w.close()
    held.release()
    w = Watch(beta, 0, NEW_VERSION)
    assert w.start_line() == "watch: beta from cursor 0, the hub"
    w.close()


# (event times, a pause at this time or None, the time the watcher ends, why)
ENDS: list[Any] = [
    ([0], None, 20, EVENTS),
    ([0, 15, 30], None, 50, EVENTS),
    ([], None, None, None),
    ([0], 5, 5, NO_BATCH),
    ([], 5, 5, NO_BATCH),
]


@pytest.mark.parametrize(("times", "pause", "end", "why"), ENDS)
def test_a_watcher_ends_twenty_seconds_after_the_last_event(
    repo: Path, times: list[int], pause: int | None, end: int | None, why: str | None
) -> None:
    folder = repo / ".agents" / "changes" / "4-batch"
    folder.mkdir(parents=True)

    def write(status: str) -> None:
        data = {"id": "batch-01", "status": status, "crs": []}
        (folder / "batch.json").write_text(json.dumps(data), encoding="utf-8")

    write("running")
    found = Repo.find()
    assert (hub_times.cycle_s(), hub_times.quiet_s()) == (CYCLE, QUIET)
    w = Watch(found, 0, __version__)
    ended: tuple[int, str] | None = None
    for t in range(120):
        if t == pause:
            write("paused")
        if t in times:
            journal.append(found, [journal.red_event("batch-01", f"CR-{t}", "P", "c" * 40)], "hub")
        reason = w.poll(float(t))
        if reason:
            ended = (t, reason)
            break
    w.close()
    assert ended == ((end, why) if end is not None else None)
    if why == EVENTS:
        again = "still running: for the Chief of Staff, start again in the background now: "
        last = f"watch: batch-01 {again}{watch_command(found, len(times))}"
        assert w.lines(EVENTS)[-1] == last
    if why == NO_BATCH:
        assert w.lines(NO_BATCH)[-1] == f"watch: no running batch in {found.root.name}; ended"


def test_watch_refusals(repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch) -> None:
    code, _, err = chantier("watch")
    assert code == EXIT_PRECONDITION and "watch: no running batch in" in err
    assert "nothing to watch" in err
    open_batch(repo, chantier, monkeypatch, "Alpha")

    def files() -> list[str]:
        return sorted(p.as_posix() for p in repo.rglob("*") if ".git/" not in p.as_posix())

    before = files()
    code, _, err = chantier("watch", "--after", "5")
    assert code == EXIT_USAGE and "watch: --after 5 is past the journal's end (0)" in err
    assert files() == before and not (repo / ".git" / "chantier").exists()


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
    assert got[-1].endswith(f" watch --after {last}") and "watch: chantier watch" not in got
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
    held = lock.HubLock(found.git_dir)
    assert held.acquire()
    lock.write(found.git_dir, lock.start_record("0.0.1"))
    pid = os.getpid()
    assert forge_lines()[0] == f"forge hub: PID {pid}, last read none yet; hub is chantier 0.0.1"
    lock.write(found.git_dir, lock.start_record(__version__))
    assert forge_lines()[0] == f"forge hub: PID {pid}, last read none yet"
    held.release()
    assert (changes(repo) / journal.FILE).is_file()
