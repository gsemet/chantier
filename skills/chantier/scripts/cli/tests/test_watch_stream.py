"""The watcher that runs through several events (`watch --stream`) and its idle end, which waits
for no batch in flight: the same batch the forge hub follows (`batch_prs.followed_batch`). No test
sleeps: the watcher is driven with an injected monotonic time."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from forge_world import BOARD_LINE, CYCLE, QUIET, crs_of
from watch_fakes import served

from chantier import __version__
from chantier.board.seats import SEAT_CHECK_S
from chantier.core.repo import Repo
from chantier.hub import autostart, batch_prs, journal, watch_lines
from chantier.hub import times as hub_times
from chantier.hub.autostart import watch_command
from chantier.hub.watch import EVENTS, IDLE, SEAT, Watch
from chantier.hub.watch_reads import Rules

IDLE_S = 30  # the idle end the test times give (`<cycle>:<quiet>:<idle_end>`)


def write_status(repo: Path, status: str | None, crs: list[dict[str, Any]] | None = None) -> None:
    """The project's `batch.json` with this status and these CRs; None writes none."""
    folder = repo / ".agents" / "changes" / "4-batch"
    folder.mkdir(parents=True, exist_ok=True)
    if status is None:
        (folder / "batch.json").unlink(missing_ok=True)
        return
    data = {"id": "batch-01", "status": status, "crs": crs or []}
    (folder / "batch.json").write_text(json.dumps(data), encoding="utf-8")


def seat_of_another(repo: Path) -> None:
    folder = repo / ".agents" / "changes"
    folder.mkdir(parents=True, exist_ok=True)
    data = {"session": "s", "transcript": "xyz-2"}
    (folder / "seat.json").write_text(json.dumps(data), encoding="utf-8")


@pytest.mark.parametrize(
    ("wake_every", "at", "blocks"), [(0.0, (0, 40), (20, 60)), (30.0, (0, 35), (30, 60))]
)
def test_a_streaming_watcher_tells_each_block_and_runs_on_until_the_seat_moves(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    wake_every: float,
    at: tuple[int, int],
    blocks: tuple[int, int],
) -> None:
    monkeypatch.setattr(autostart, "session_key", lambda: "abc-1")
    found = Repo.find()
    w = Watch(found, 0, __version__, Rules(wake_every=wake_every, stream=True), served(found))
    told: list[tuple[int, list[str]]] = []
    ended: tuple[int, str] | None = None
    for t in range(120):
        if t in at:
            journal.append(found, [BOARD_LINE], "board")
        if t == blocks[1] + SEAT_CHECK_S:
            seat_of_another(repo)
        reason = w.poll(float(t))
        if reason == EVENTS:
            told.append((t, w.tell(float(t))))
        elif reason:
            ended = (t, reason)
            break
    w.close()
    name = f"{found.root.name} (no batch)"
    assert [t for t, _ in told] == list(blocks)  # the second no sooner than wake_every after
    for n, (_, out) in enumerate(told, start=1):
        assert len(out) == len(("event", "still watching")) and out[0].startswith("board wrote")
        assert out[-1] == watch_lines.STREAM_TOLD.format(
            name=name, n=n, watch=watch_command(found, n)
        )
    assert ended == (blocks[1] + SEAT_CHECK_S, SEAT)
    assert w.lines(SEAT) == [
        f"watch: the seat of {found.root.name} is another session's now; ended"
    ]


def paused_crs(kind: str) -> list[dict[str, Any]]:
    crs = crs_of("alpha", "merged")
    if kind == "open":
        crs[1]["status"] = "ready"
    if kind == "no PR":
        for c in crs:
            c["pr"], c["status"] = None, "working"
    return crs


# (the batch's status or None for no batch, its CRs, whether a batch is in flight)
FLIGHTS: list[Any] = [
    ("running", "open", True),
    ("paused", "open", True),
    ("paused", "merged", False),
    ("paused", "no PR", False),
    ("closed", "merged", False),
    (None, "merged", False),
]


@pytest.mark.parametrize(("status", "crs", "flying"), FLIGHTS)
def test_the_idle_end_waits_for_no_batch_in_flight(
    repo: Path, monkeypatch: pytest.MonkeyPatch, status: str | None, crs: str, flying: bool
) -> None:
    monkeypatch.setenv(hub_times.TEST_ENV, f"{CYCLE:g}:{QUIET:g}:{IDLE_S}")
    write_status(repo, status, paused_crs(crs))
    found = Repo.find()
    assert (batch_prs.followed_batch(found) is not None) == flying  # the hub follows it too
    w = Watch(found, 0, __version__, board=served(found))
    ended = next((t for t in range(5 * IDLE_S) if w.poll(float(t))), None)
    w.close()
    assert ended == (None if flying else IDLE_S)
    if not flying:
        name = "batch-01" if status == "paused" else f"{found.root.name} (no batch)"
        assert w.lines(IDLE)[-1].startswith(f"watch: no event for {name} in 2 h; ended")


def test_the_idle_end_counts_from_the_last_moment_a_batch_was_in_flight(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(hub_times.TEST_ENV, f"{CYCLE:g}:{QUIET:g}:{IDLE_S}")
    write_status(repo, "running")
    found = Repo.find()
    w = Watch(found, 0, __version__, board=served(found))
    change = 5 * SEAT_CHECK_S
    ended = None
    for t in range(5 * IDLE_S):
        if t == change:
            write_status(repo, "closed")
        if w.poll(float(t)):
            ended = t
            break
    w.close()
    assert ended == change - 1 + IDLE_S  # one idle period after the last poll that saw it
