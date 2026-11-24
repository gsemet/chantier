"""The Foreman's watcher: a `watch` run by the session the running or paused batch records as its
Foreman reads only that batch's merge, red-CI and wait-met lines, starts no server and never ends
on the seat; the `watch: not running` line and `status` name it. No test sleeps."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import open_batch, record, write_record
from conftest import Chantier
from forge_world import BOARD_LINE, CYCLE, QUIET
from test_watch_stream import IDLE_S, paused_crs, seat_of_another
from watch_fakes import FakeBoard, served

from chantier import __version__
from chantier.board.projects import project_name
from chantier.board.seats import SEAT_CHECK_S
from chantier.core.repo import Repo
from chantier.hub import autostart, journal, lock, watch_lines
from chantier.hub import times as hub_times
from chantier.hub.autostart import watch_command
from chantier.hub.lines import watch_lines as status_watch_lines
from chantier.hub.schemas import merged_text, red_text
from chantier.hub.watch import END, EVENTS, IDLE, Watch
from chantier.hub.watch_lines import Ended
from chantier.hub.watch_reads import Rules

KINDS = 3  # then the "still watching" line
FM, COS = "fm-1", "cos-1"
BATCH = "batch-01"
MERGED = {
    "type": "merged@1",
    "batch": BATCH,
    "cr": "CR-1",
    "pr": "P",
    "into": "main",
    "into_cr": None,
    "merged_at": "t",
}
RED = journal.red_event(BATCH, "CR-1", "P", "c" * 40)
MET = {
    "type": "wait-cleared@1",
    "batch": BATCH,
    "cr": "CR-1",
    "wait": "w1",
    "wait_type": "pipeline",
    "ref": "abc",
    "seen_at": "t",
}
ARRIVED = {
    "type": "arrived@1",
    "project": "p",
    "folder": "1-inbox/x",
    "stage": "inbox",
    "before": None,
    "via": "pull",
    "upstream": None,
}
CONFIG = {"type": "config@1", "key": "batch.slots", "old": 1, "new": 2, "batch": None}
OTHER_BATCH = {**MERGED, "batch": "batch-02"}
WAKING: list[dict[str, Any]] = [MERGED, RED, MET]
QUIETLY: list[dict[str, Any]] = [BOARD_LINE, CONFIG, OTHER_BATCH]


def write_batch(
    repo: Path,
    status: str,
    crs: list[dict[str, Any]],
    foreman: str | None = FM,
    steering: str | None = None,
) -> None:
    folder = repo / ".agents" / "changes" / "4-batch"
    folder.mkdir(parents=True, exist_ok=True)
    data = {"id": BATCH, "status": status, "crs": crs, "foreman_transcript": foreman}
    if steering:
        data["steering"] = steering
    (folder / "batch.json").write_text(json.dumps(data), encoding="utf-8")


def watcher(
    repo: Path, mp: pytest.MonkeyPatch, board: FakeBoard | None = None, **rules: Any
) -> Watch:
    mp.setattr(autostart, "session_key", lambda: FM)
    found = Repo.find()
    return Watch(found, 0, __version__, Rules(stream=True, **rules), board or served(found))


@pytest.mark.parametrize("status", ["running", "paused"])
def test_the_foremans_watcher_tells_its_batchs_three_kinds_and_runs_on(
    repo: Path, monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    write_batch(repo, status, paused_crs("open"))
    w = watcher(repo, monkeypatch)
    found, told = w.repo, []
    for t in range(80):
        if t in (0, 40):  # the quiet lines in the same window move the cursor, say nothing
            lines = [*QUIETLY, *WAKING] if t == 0 else [{**MERGED, "cr": "CR-2"}]
            journal.append(found, lines, "hub")
            journal.append(found, [ARRIVED], "writer")
        if t == SEAT_CHECK_S + 5:
            seat_of_another(repo)  # another session's seat does not end it
        reason = w.poll(float(t))
        assert reason in (None, EVENTS)
        if reason == EVENTS:
            told.append(w.tell(float(t)))
    w.close()
    first, second = told
    assert first[:2] == [merged_text(MERGED), red_text(RED)] and len(first) == KINDS + 1
    assert first[2].startswith("forge saw pipeline met: CR-1 w1")
    assert second[0].startswith("forge saw merged: CR-2") and "still watching" in second[-1]
    assert second[-1].endswith(f"{watch_command(found, w.cursor)})") and w.cursor > len(first)


@pytest.mark.parametrize("case", ["other", "closed", "direct"])
def test_the_foremans_watcher_ends_with_its_line_when_the_batch_no_longer_records_it(
    repo: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    write_batch(repo, "running", paused_crs("open"))
    w = watcher(repo, monkeypatch)
    ended = None
    for t in range(3 * SEAT_CHECK_S):
        if t == SEAT_CHECK_S + 1:
            write_batch(
                repo,
                "closed" if case == "closed" else "running",
                paused_crs("open"),
                {"other": "fm-2", "direct": None}.get(case, FM),
            )
        if reason := w.poll(float(t)):
            ended = reason
            break
    assert ended == END and w.code(END) == 0
    want = watch_lines.FOREMAN_CLOSED if case == "closed" else watch_lines.FOREMAN_OTHER
    assert w.lines(END) == [want.format(batch=BATCH)]
    w.close()


def test_the_foremans_watcher_of_a_paused_batch_with_no_pr_open_ends_at_the_idle_period(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(hub_times.TEST_ENV, f"{CYCLE:g}:{QUIET:g}:{IDLE_S}")
    write_batch(repo, "paused", paused_crs("merged"))
    w = watcher(repo, monkeypatch)
    ended = next((t for t in range(5 * IDLE_S) if w.poll(float(t))), None)
    assert ended == IDLE_S and w.poll(float(ended)) == IDLE
    assert w.lines(IDLE)[-1].startswith(f"watch: no event for {BATCH} in 2 h; the Foreman's")
    assert w.lines(EVENTS)[-1].startswith(f"watch: {BATCH} still running: for the Foreman")
    w.close()


def test_the_foremans_watcher_starts_no_server_and_ends_at_once_with_no_server(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_batch(repo, "running", paused_crs("open"))
    found = Repo.find()
    board = FakeBoard(found)
    w = watcher(repo, monkeypatch, board)
    with pytest.raises(Ended) as e:
        w.start()
    assert board.spawned == [] and "timer is the Foreman's wake" in e.value.line
    assert e.value.line == watch_lines.FOREMAN_NO_SERVER.format(project=project_name(found))
    w.close()


@pytest.mark.parametrize("status", ["running", "paused"])
@pytest.mark.parametrize("session", [FM, COS])
def test_the_not_running_line_and_the_status_line_name_the_foremans_watcher(
    repo: Path, monkeypatch: pytest.MonkeyPatch, status: str, session: str
) -> None:
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    monkeypatch.setattr(autostart, "session_key", lambda: session)
    write_batch(repo, status, paused_crs("open"))
    found = Repo.find()
    command = watch_command(found, 0)
    assert command.endswith(" --stream")
    if session == FM:
        assert autostart.not_running_line(found) == [
            f"watch: not running: for the Foreman, start in the background: {command}"
        ]
        return
    assert autostart.not_running_line(found)[0].startswith("watch: not running: for the Chief")
    d = autostart.open_record(found)
    assert d is not None
    assert "foreman watch: not running" in status_watch_lines(found, d)
    held = lock.WatcherLock(found.git_dir, project_name(found), FM)
    assert held.acquire()
    assert "foreman watch: running" in status_watch_lines(found, d)
    held.release()
    write_batch(repo, status, paused_crs("open"), None)  # direct mode: no such line
    d = autostart.open_record(found)
    assert d is not None
    assert not any(x.startswith("foreman watch:") for x in status_watch_lines(found, d))


@pytest.mark.parametrize("steering", ["direct", "foreman"])
def test_a_direct_batch_never_records_a_foremans_watcher(
    repo: Path, monkeypatch: pytest.MonkeyPatch, steering: str
) -> None:
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    monkeypatch.setattr(autostart, "session_key", lambda: FM)
    write_batch(repo, "running", paused_crs("open"), FM, steering)
    found = Repo.find()
    line = autostart.not_running_line(found)[0]
    assert line.startswith("watch: not running: for the Chief") == (steering == "direct")
    assert (autostart.foreman_batch(found) is None) == (steering == "direct")


@pytest.mark.parametrize(("epoch", "code"), [(1, 0), (0, 1)])
def test_order_merged_as_the_foreman_on_a_paused_batch_needs_the_current_epoch(
    repo: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    epoch: int,
    code: int,
) -> None:
    cr = open_batch(repo, chantier, monkeypatch, "Alpha")[0]
    data = record(repo)
    data["status"] = "paused"
    write_record(repo, data)
    assert (chantier("order", "merged", cr, "--epoch", epoch)[0] == 0) == (code == 0)
    assert (record(repo)["crs"][0]["status"] == "merged") == (code == 0)
