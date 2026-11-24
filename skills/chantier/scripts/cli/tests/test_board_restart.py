"""`serve --restart` and what it rests on: the private-key op `server.stop`, the refusals of the
restart (the guard of a surface a chantier dev session holds, an older board, a refused key, a
silent board, a running client command, the 120 s wait), the seat's `build`, the watcher that
starts no board under the guard, and the shipped cards that name the restart. No process is
signalled and no test sleeps: the probe, the op and the clock are replaced."""

from __future__ import annotations

import json
import os
from http import HTTPStatus
from pathlib import Path
from typing import Any

import pytest
from conftest import SKILL, Chantier, Surface
from test_board_running import LINK_PORT, _prepare_board
from test_server_api import board as server_board  # noqa: F401 - the fixture
from test_server_api import call
from test_watch_board import SESSION, seat
from watch_fakes import FakeBoard, serving

from chantier import __version__, procs
from chantier.board import restart, running
from chantier.board.api import ops
from chantier.board.projects import open_projects
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE
from chantier.core.repo import Repo
from chantier.hub import autostart, lock, state
from chantier.hub.watch import RETRY_S, Watch
from chantier.hub.watch_lines import NO_BOARD
from chantier.plugin_files import detect_host, own_transcript

DEV = ("s-dev", "/dev/checkout/chantier")
OK = (200, {"ok": True, "data": {"stopping": True, "pid": 4242}})
STOP = running.stop_command(4242)


def test_server_stop_is_for_the_private_key_and_waits_for_no_running_command(
    request: pytest.FixtureRequest,
) -> None:
    board = request.getfixturevalue("server_board")
    stopped: list[int] = []
    board.ctx.stop = lambda: stopped.append(1)
    assert ops.call(board.ctx, "server.stop", {}, "read").status == HTTPStatus.FORBIDDEN

    assert stopped == []
    board.ctx.runs.begin()
    status, data = call(board, "server.stop")
    assert (status, data["error"]) == (HTTPStatus.CONFLICT, ops.COMMAND_RUNS) and stopped == []
    board.ctx.runs.end()  # the grace after a command's end does not count
    status, data = call(board, "server.stop")
    assert status == HTTPStatus.OK and data["data"] == {"stopping": True, "pid": os.getpid()}
    assert stopped == [1]


def _restart_world(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, case: str
) -> tuple[list[int], list[str]]:
    """A recorded board of this version; the op, the probe and the clock are replaced."""
    plan = (False, None, None) if case == "none" else (True, None, None)
    path, bound = _prepare_board(repo, chantier, monkeypatch, plan)
    home = open_projects().home
    if case != "none":
        record = {
            "pid": 4242,
            "host": "127.0.0.1",
            "port": LINK_PORT,
            "version": "0.0.1",
            "served": open_projects().served.as_posix(),
            "started": "2026-01-01T00:00:00Z",
        }
        data = json.loads(path.read_text("utf-8"))
        path.write_text(json.dumps({**data, "server": record, "key": "old-key"}), "utf-8")
    asked: list[str] = []
    clock = [0.0]

    def sleep(seconds: float) -> None:
        clock[0] += seconds
        if case == "stops" and clock[0] >= 1.0:  # the old board's `finally` removes its entry
            state.remove_entry(home.git_dir, state.SERVER, 4242)

    monkeypatch.setattr(restart, "_sleep", sleep)
    monkeypatch.setattr(restart, "_clock", lambda: clock[0])
    monkeypatch.setattr(restart, "probe", lambda *_a, **_k: None)
    monkeypatch.setattr(procs, "alive", lambda _pid: case != "stops" or clock[0] < 1.0)
    answers: dict[str, Any] = {
        "unknown-op": (404, {"error": "unknown op 'server.stop'"}),
        "key-refused": (401, {}),
        "command-runs": (409, {"error": ops.COMMAND_RUNS}),
    }

    def call_op(host: str, port: int, key: str, op: str, timeout: float) -> Any:
        asked.append(f"{host}:{port} {key} {op} {timeout}")
        if case == "silent":
            raise OSError("timed out")
        return answers.get(case, OK)

    monkeypatch.setattr(restart, "call_op", call_op)
    return bound, asked


@pytest.mark.parametrize(
    ("case", "refusal"),
    [
        ("unknown-op", "has no clean stop"),
        ("key-refused", "refused the key"),
        ("silent", "does not answer"),
        ("command-runs", ops.COMMAND_RUNS),
        ("never-ends", "is still stopping after 120 s"),
    ],
)
def test_serve_restart_refuses_in_one_line_and_stops_nothing_by_force(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, case: str, refusal: str
) -> None:
    bound, asked = _restart_world(repo, chantier, monkeypatch, case)
    code, out, err = chantier("serve", "--restart", "--port", "0")
    assert code == EXIT_PRECONDITION and err.count("\n") == 1 and refusal in err
    assert not bound and out == []  # no start line, no new board
    assert asked == [f"127.0.0.1:{LINK_PORT} old-key server.stop {restart.ASK_S}"]
    if case in ("unknown-op", "key-refused", "silent", "never-ends"):
        assert "PID 4242" in err and "chantier serve 0.0.1" in err
        assert ("then run serve --restart again" in err) == (case != "never-ends")
        assert (STOP in err) == (case != "never-ends")


def test_serve_restart_waits_for_the_old_board_then_serves_here(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    bound, _ = _restart_world(repo, chantier, monkeypatch, "stops")
    code, out, err = chantier("serve", "--restart", "--port", "0")
    assert code == 0 and err == "" and len(bound) == 1
    assert out == [f"board stopped: chantier 0.0.1 (PID 4242, {state.UNKNOWN})", *out[1:]]
    assert out[1].startswith("board on http://")  # the usual start lines, on this build


def test_serve_restart_with_no_board_says_so_and_serves(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    bound, asked = _restart_world(repo, chantier, monkeypatch, "none")
    code, out, _ = chantier("serve", "--restart", "--port", "0")
    assert code == 0 and out[0] == restart.NONE_RUNNING and len(bound) == 1 and asked == []


def test_serve_restart_refuses_under_the_guard_and_with_stop_idle(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    bound, asked = _restart_world(repo, chantier, monkeypatch, "stops")
    assert chantier("serve", "--restart", "--stop-idle")[0] == EXIT_USAGE
    monkeypatch.setattr(autostart, "other_dev_build", lambda *_a: DEV)
    code, out, err = chantier("serve", "--restart")
    assert code == EXIT_PRECONDITION and out == [] and not bound and asked == []
    assert err.strip() == (
        "error: board not restarted: a chantier dev session (s-dev) holds its seat; its build "
        "(/dev/checkout/chantier) serves this surface"
    )


def _chantier_project(surface: Surface, build: str | None, held: str | None) -> Repo:
    """The surface's `chantier` project with a seat (its session `s-dev`, its transcript `t-dev`,
    its build) and, when `held`, a watcher lock of that session; `demo`'s repo is returned."""
    found = Repo.find()  # before the second project exists
    changes = surface.root / "projects" / "chantier" / "changes"
    changes.mkdir(parents=True)
    data = {"session": "s-dev", "transcript": "t-dev"} | ({"build": build} if build else {})
    (changes / "seat.json").write_text(json.dumps(data), encoding="utf-8")
    if held:
        mine = lock.WatcherLock(found.git_dir, "chantier", held)
        assert mine.acquire()
        autostart_locks.append(mine)
    return found


autostart_locks: list[lock.WatcherLock] = []


@pytest.fixture(autouse=True)
def _release_locks() -> Any:
    yield
    for held in autostart_locks:
        held.release()
    autostart_locks.clear()


@pytest.mark.parametrize(
    ("build", "held", "found"),
    [
        ("/dev/b", "t-dev", ("s-dev", "/dev/b")),
        ("/dev/b", None, None),  # the session's watcher is down: a stale seat claims nothing
        ("/dev/b", "t-other", None),
        (None, "t-dev", None),  # a seat taken before `build` existed
    ],
)
def test_a_dev_session_holds_its_seat_when_its_seat_names_a_build_and_its_watcher_runs(
    surface: Surface, build: str | None, held: str | None, found: tuple[str, str] | None
) -> None:
    repo = _chantier_project(surface, build, held)
    assert autostart.dev_build(repo) == found
    assert autostart.other_dev_build(repo, "/dev/b") is None  # its own build is not another
    assert autostart.other_dev_build(repo, "/studio/b") == found


def test_a_dev_session_holds_no_seat_off_a_planning_surface(repo: Path) -> None:
    assert autostart.dev_build(Repo.find()) is None


@pytest.mark.parametrize(
    ("guarded", "own"), [(True, "/studio/b"), (False, "/studio/b"), (True, DEV[1])]
)
def test_a_watcher_under_the_guard_starts_no_board_and_links_when_one_runs(
    repo: Path, monkeypatch: pytest.MonkeyPatch, guarded: bool, own: str
) -> None:
    seat(repo, "abc-1")
    monkeypatch.setattr(autostart, "session_key", lambda: "abc-1")
    monkeypatch.setattr(autostart, "dev_build", lambda _repo: DEV if guarded else None)
    found = Repo.find()
    fake = FakeBoard(found, starts=serving)
    w = Watch(found, 0, __version__, board=fake)
    w.build = own
    line = w.start()
    waits = guarded and own != DEV[1]
    assert (NO_BOARD in line[0]) is waits and bool(fake.spawned) is not waits
    assert len(line) == (1 if waits else 2)  # no board line while it waits
    if not waits:
        w.close()
        return
    assert fake.feeds == [] and w.feed is None and w.lost_at == fake.now
    assert w.poll(1.0) is None and fake.spawned == []  # not yet tried again
    assert w.poll(RETRY_S) is None and fake.spawned == [] and w.end is None
    fake.running = {"pid": 4242, "host": "127.0.0.1", "port": 1, "version": __version__}
    assert w.poll(2 * RETRY_S) is None and [a for a, _ in fake.feeds] == [0]
    assert fake.registered == [(found.root.name, SESSION)]  # linked as it does with a board
    w.close()


def test_seat_take_records_the_dev_builds_source_and_the_plugin_mode_none(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s-1")
    assert detect_host() == "claude" and own_transcript("claude") is not None
    path = repo / ".agents" / "changes" / "seat.json"
    for dev in (True, False):
        monkeypatch.setattr("chantier.commands.seat.is_dev_mode", lambda _repo, dev=dev: dev)
        assert chantier("seat", "take", "s-1", "--over", "s-1")[0] == 0
        data = json.loads(path.read_text("utf-8"))
        assert data.get("build") == (state.build_source() if dev else None)
        assert ("build" in data) is dev


def _flat(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def test_the_cards_offer_the_restart_and_the_hosts_run_it() -> None:
    refs = SKILL / "references"
    for name in ("session-start-chief-of-staff.md", "chief-of-staff-steering.md"):
        text = _flat(refs / name)
        assert "never stop or restart the board" not in text, name
        assert "serve --restart" in text or "Restart the board" in text, name
    assert "serve --restart --seat <id>" in _flat(refs / "session-start-chief-of-staff.md")
    for host in ("claude-code.md", "copilot.md"):
        row = next(
            line
            for line in (refs / "hosts" / host).read_text("utf-8").splitlines()
            if line.startswith("| Run the board")
        )
        assert "serve --restart --seat <id>" in row, host
