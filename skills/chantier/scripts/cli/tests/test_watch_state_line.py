"""The steering session's watcher prints the `state:` line just before the last line of each
telling (`--stream`'s block, the end lines `events` and `idle`): the Foreman's watcher of its
batch, or the seat's of a batch steered `direct`; no other watcher. No test sleeps: the watcher is
driven with an injected monotonic time."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_watch_foreman import BATCH, FM, watcher

from chantier.hub.watch import EVENTS, IDLE, SEAT
from chantier.status.state_line import STATE

CRS: list[dict[str, Any]] = [
    {"id": "CR-1", "order": 1, "status": "working"},
    {"id": "CR-2", "order": 2, "status": "ready"},
    {"id": "CR-3", "order": 3, "status": "merged"},
]
WANT = STATE.format(
    batch=BATCH,
    status="running",
    epoch=2,
    counts="working 1, ready 1, merged 1",
    held=1,
    slots=3,
    due=1,  # CR-2 handed back, no ask yet
)


def write(repo: Path, foreman: str | None, steering: str | None) -> Path:
    folder = repo / ".agents" / "changes" / "4-batch"
    folder.mkdir(parents=True, exist_ok=True)
    data = {
        "id": BATCH,
        "status": "running",
        "slots": 3,
        "foreman_epoch": 2,
        "crs": CRS,
        "foreman_transcript": foreman,
        "steering": steering,
    }
    (folder / "batch.json").write_text(json.dumps(data), encoding="utf-8")
    return folder


# (the batch's foreman transcript and steering, or None for no batch; whether the line shows)
WHO: list[Any] = [
    pytest.param((FM, "foreman"), True, id="foremans-watcher"),
    pytest.param((None, "direct"), True, id="seat-watcher-direct"),
    pytest.param(("fm-2", "foreman"), False, id="seat-watcher-foreman-batch"),
    pytest.param(None, False, id="no-batch"),
]


@pytest.mark.parametrize(("batch", "shown"), WHO)
def test_only_the_steering_watcher_prints_the_state_line_before_its_last_line(
    repo: Path, monkeypatch: pytest.MonkeyPatch, batch: tuple[str | None, str] | None, shown: bool
) -> None:
    if batch is not None:
        write(repo, *batch)
    w = watcher(repo, monkeypatch)
    assert w.poll(0.0) is None
    block, ended, idle = w.tell(1.0), w.lines(EVENTS), w.lines(IDLE)
    w.close()
    for out in (block, ended, idle):
        assert (out[-2:-1] == [WANT]) == shown and len(out) == 1 + shown
    assert not any(x.startswith("state:") for x in w.lines(SEAT))


def test_an_unreadable_events_file_says_so_on_the_state_line(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = write(repo, FM, "foreman")
    (folder / "events.jsonl").mkdir()  # a folder where the file is: it cannot be read
    w = watcher(repo, monkeypatch)
    block = w.tell(0.0)
    w.close()
    assert block[-2].startswith("state: unreadable (")
