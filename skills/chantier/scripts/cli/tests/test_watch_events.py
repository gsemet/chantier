"""What the Chief of Staff's watcher hears of the board: the board's and the roles' `config@1`
lines, which wake it or not, the end on another session's seat, the pull path and the lines never
deduplicated. No test sleeps: the end is driven with an injected monotonic time."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import host, open_batch
from conftest import Chantier
from forge_world import CYCLE, EXIT_USAGE, QUIET
from watch_fakes import served

from chantier import __version__, connectors
from chantier.board.seats import SEAT_CHECK_S
from chantier.core.repo import Repo
from chantier.hub import autostart, journal, lock
from chantier.hub import times as hub_times
from chantier.hub.autostart import pull_command, watch_command
from chantier.hub.watch import EVENTS, SEAT, Watch


def board_line(wakes: bool, action: str = "move") -> dict[str, Any]:
    return {
        "type": "board@1",
        "action": action,
        "items": ["x"],
        "text": "x: priority P2 -> P1",
        "wakes": wakes,
    }


def issue_line(wakes: bool, at: str = "2026-11-20T09:14:00Z") -> dict[str, Any]:
    return {
        "type": "issue@1",
        "tracker": "jira",
        "ref": "https://acme.atlassian.net/browse/PAY-12",
        "event": "commented",
        "at": at,
        "text": "keep the old order",
        "wakes": wakes,
        "folders": ["1-inbox/export"],
    }


def role_line() -> dict[str, Any]:
    key = "hosts.claude-code.roles.coder.model"
    return {"type": "config@1", "key": key, "old": "a", "new": "b", "batch": None}


RED = journal.red_event("batch-01", "CR-1", "P", "c" * 40)
# (the lines written at 0 s, at 15 s and at 30 s, the batch, the time the watcher ends)
ENDS: list[Any] = [
    ([RED], None, "running", 20),
    ([RED], 15, "running", 35),
    ([board_line(True)], None, "running", 20),
    ([issue_line(True)], None, "running", 20),
    ([issue_line(False)], None, "running", None),
    ([issue_line(False), board_line(True)], None, "running", 20),
    ([board_line(False)], None, "running", None),
    ([board_line(False), board_line(True)], None, "running", 20),
    ([role_line()], None, "running", 20),
    ([board_line(True)], None, "paused", 20),
    ([board_line(True)], None, "none", 20),
    ([], None, "running", None),
]


@pytest.mark.parametrize(("lines", "again", "status", "end"), ENDS)
def test_a_watcher_ends_twenty_seconds_after_the_last_line_that_wakes(
    repo: Path, lines: list[dict[str, Any]], again: int | None, status: str, end: int | None
) -> None:
    if status != "none":
        folder = repo / ".agents" / "changes" / "4-batch"
        folder.mkdir(parents=True)
        data = {"id": "batch-01", "status": status, "crs": []}
        (folder / "batch.json").write_text(json.dumps(data), encoding="utf-8")
    found = Repo.find()
    assert (hub_times.cycle_s(), hub_times.quiet_s()) == (CYCLE, QUIET)
    w = Watch(found, 0, __version__, board=served(found))
    ended: tuple[int, str] | None = None
    for t in range(120):
        if t == 0:
            journal.append(found, lines, "board")
        if again is not None and t == again:
            journal.append(found, [RED | {"head": "f" * 40}], "hub")
        reason = w.poll(float(t))
        if reason:
            ended = (t, reason)
            break
    w.close()
    assert ended == ((end, EVENTS) if end is not None else None)
    if end is not None:
        name = "batch-01" if status != "none" else f"{found.root.name} (no batch)"
        text = "still running: for the Chief of Staff, start again in the background now: "
        out = w.lines(EVENTS)
        assert out[-1] == f"watch: {name} {text}{watch_command(found, w.cursor)}"
        assert len(out) == len(w.events) + 1
        boards = sum(1 for x in lines if x["type"] == "board@1")
        assert sum(1 for x in out if x.startswith("board wrote")) == boards


def seat_file(repo: Path, transcript: str | None) -> None:
    folder = repo / ".agents" / "changes"
    folder.mkdir(parents=True, exist_ok=True)
    data = {"session": "s", "transcript": transcript}
    (folder / "seat.json").write_text(json.dumps(data), encoding="utf-8")


# (the watcher's key, the seat's transcript or "no seat", whether the seat ends it)
SEATS = [
    ("abc-1", "xyz-2", True),
    ("abc-1", "abc-1", False),
    ("abc-1", "abc_1!", True),
    ("abc-1", None, False),
    ("abc-1", "no seat", False),
    ("none", "xyz-2", False),
]


@pytest.mark.parametrize(("key", "transcript", "ends"), SEATS)
def test_the_seat_of_another_session_ends_the_watcher_with_its_line(
    repo: Path, monkeypatch: pytest.MonkeyPatch, key: str, transcript: str | None, ends: bool
) -> None:
    monkeypatch.setattr(autostart, "session_key", lambda: key)
    found = Repo.find()
    w = Watch(found, 0, __version__, board=served(found))
    assert w.poll(0.0) is None
    if transcript != "no seat":
        seat_file(repo, transcript)
    journal.append(found, [board_line(False)], "board")
    assert w.poll(5.0) is None  # between two looks
    got = w.poll(float(SEAT_CHECK_S))
    w.close()
    assert got == (SEAT if ends else None)
    if ends:
        assert w.lines(SEAT) == [
            journal.event_text(board_line(False) | {"seq": 1}),
            f"watch: the seat of {found.root.name} is another session's now; ended",
        ]


def test_watch_refusals_and_the_pull_path(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    open_batch(repo, chantier, monkeypatch, "Alpha")

    def files() -> list[str]:
        return sorted(p.as_posix() for p in repo.rglob("*") if ".git/" not in p.as_posix())

    before = files()
    for args in (("--after", "5"), ("--once", "--after", "5")):
        code, _, err = chantier("watch", *args)
        assert code == EXIT_USAGE and "watch: --after 5 is past the journal's end (0)" in err
    code, _, err = chantier("watch", "--once")
    assert code == EXIT_USAGE and "--once needs --after" in err
    assert files() == before and not (repo / ".git" / "chantier").exists()


def test_the_pull_path_prints_the_lines_past_the_cursor_and_takes_no_lock(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forge_read_called(
        links: list[str], facts: frozenset[str] = frozenset()
    ) -> dict[int, dict[str, Any]]:
        raise AssertionError("--once reads no forge")

    monkeypatch.setattr(connectors, "read", forge_read_called)
    host(monkeypatch)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s-me")
    found = Repo.find()
    journal.append(found, [board_line(False, "label"), board_line(True), role_line()], "board")
    command = pull_command(found, 3)
    for after, texts in ((0, 3), (1, 2), (3, 0)):
        code, out, err = chantier("watch", "--once", "--after", str(after))
        assert code == 0, err
        assert len(out) == texts + 1
        assert out[-1] == f"watch: cursor 3; next, at the user's next message: {command}"
    assert not (found.git_dir / "chantier" / "server.json").exists()
    assert lock.watchers(found.git_dir, found.root.name) == []
    code, out, _ = chantier("watch", "--once", "--after", "0")
    assert out[0].startswith("board wrote (label)") and out[1].startswith("board wrote (move)")
    assert out[2].startswith("config changed on the board: hosts.claude-code.roles.coder.model")


def test_the_board_and_config_lines_are_never_duplicates_and_status_holds_none(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    open_batch(repo, chantier, monkeypatch, "Alpha")
    found = Repo.find()
    twice = [board_line(True), board_line(True), role_line(), role_line()]
    merge = {
        "type": "merged@1",
        "batch": "b",
        "cr": "CR-1",
        "pr": "P",
        "into": "main",
        "into_cr": None,
        "merged_at": "t",
    }
    written = journal.append(found, [*twice[:2], merge, *twice[2:], merge], "board")
    assert len(written) == len(twice) + 1
    assert len(journal.append(found, [merge], "hub")) == 0  # the merge key is the merge's alone
    out = chantier("status")[1]
    assert not any(x.startswith(("board wrote", "config changed")) for x in out)
    assert "applies at the next batch" in journal.event_text(role_line())
    assert journal.event_text(role_line() | {"old": None}).startswith(
        "config changed on the board: hosts.claude-code.roles.coder.model inherited -> b; "
    )
    assert journal.event_text(board_line(True) | {"action": "edit"}) == (
        "board wrote (edit): x: priority P2 -> P1; for the Chief of Staff: tell the user, "
        "act on nothing"
    )


def test_an_issue_line_is_told_by_the_pull_path_and_status_holds_none(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    open_batch(repo, chantier, monkeypatch, "Alpha")
    found = Repo.find()
    quiet = issue_line(False, "2026-11-20T09:15:00Z")
    assert len(journal.append(found, [issue_line(True), quiet], "poller")) == len((True, False))
    assert journal.append(found, [issue_line(True) | {"text": "other words"}], "poller") == []
    told = (
        'tracker saw commented on https://acme.atlassian.net/browse/PAY-12 (1-inbox/export): "keep '
        'the old order"; for the Chief of Staff: tell the user in one line, record nothing'
    )
    assert journal.event_text(issue_line(True)) == told
    out = chantier("watch", "--once", "--after", "0")[1]
    assert out[:2] == [told, told]
    assert not any(" saw " in x for x in chantier("status")[1])
