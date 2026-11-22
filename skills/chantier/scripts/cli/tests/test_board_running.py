"""One surface server per planning surface: its `server` entry in `server.json`, the migration of
`board.json`, and what a new `board` does."""

from __future__ import annotations

import json
import os
import socket
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import prepared
from conftest import Chantier

from chantier import __version__, procs
from chantier.board import command, running
from chantier.board import key as board_key
from chantier.board.projects import open_projects
from chantier.core.errors import EXIT_EXTERNAL
from chantier.core.files import try_lock, unlock
from chantier.hub import state

LINK_PORT = 40123
PORT = 1234


def _signals_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_a: object, **_k: object) -> None:
        raise AssertionError("a process was signalled")

    monkeypatch.setattr(os, "kill", forbidden)


def _prepare_board(
    repo: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    plan: tuple[bool, dict[str, Any] | None, Any],
    old: bool = False,
) -> tuple[Path, list[int]]:
    """`old`: the record sits in an older version's `board.json` (with a key) instead."""
    alive, record, answer = plan
    prepared(repo, chantier, "Board one")
    home = open_projects().home
    path = board_key.key_path(home)
    if old:
        old_file = path.with_name(state.OLD_BOARD)
        old_file.parent.mkdir(parents=True, exist_ok=True)
        data = {"key": "old-key", "created": "2026-01-01T00:00:00Z"}
        old_file.write_text(json.dumps(data if record is None else {**data, "running": record}))
    else:
        board_key.load_or_create(home)
        if record is not None:
            data = json.loads(path.read_text("utf-8"))
            path.write_text(json.dumps({**data, "server": record}), "utf-8")
    monkeypatch.setattr(procs, "alive_since", lambda *_a, **_k: alive)
    monkeypatch.setattr(command, "probe", lambda *_a, **_k: answer)
    monkeypatch.setattr(running, "find_pid", lambda _port: None)
    bound: list[int] = []

    def serve(_ctx: object, sock: socket.socket, files: Any, _args: object) -> None:
        bound.append(sock.getsockname()[1])
        files.stop()
        sock.close()

    monkeypatch.setattr(command, "_run", serve)
    _signals_nothing(monkeypatch)
    return path, bound


def _answer(served: str, version: str, pid: int | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"board": True, "version": version, "served": served}
    if pid is not None:
        body["pid"] = pid
    return body


def _plans(served: str) -> dict[str, tuple[bool, dict[str, Any] | None, Any]]:
    """(the recorded process is alive, the `server` entry, what the probe answers) by case."""
    rec = {
        "pid": 4242,
        "host": "127.0.0.1",
        "port": LINK_PORT,
        "version": __version__,
        "served": served,
        "started": "2026-01-01T00:00:00Z",
    }
    older = _answer(served, "0.0.1")
    return {
        "same": (True, rec, _answer(served, __version__)),
        "other-version": (True, {**rec, "version": "0.0.1"}, older),
        "silent": (True, rec, None),
        "dead": (False, rec, None),
        "no-record-old": (False, None, older),
        "no-record-old-pid": (False, None, _answer(served, "0.0.1", 777)),
        "migrate-live-older": (True, {**rec, "version": "0.0.1"}, older),
        "migrate-key-only": (False, None, None),
    }


@pytest.mark.parametrize(
    "case",
    [
        "same",
        "other-version",
        "silent",
        "dead",
        "no-record-old",
        "no-record-old-pid",
        "migrate-live-older",
        "migrate-key-only",
    ],
)
def test_a_new_board_reuses_refuses_or_starts_by_what_the_surface_already_runs(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    plan = _plans(open_projects().served.as_posix())[case]
    path, bound = _prepare_board(repo, chantier, monkeypatch, plan, old=case.startswith("migrate"))
    code, out, err = chantier("serve", "--host", "127.0.0.1", "--port", str(LINK_PORT + 1))
    stop = running.stop_command(4242)
    if case == "same":
        assert code == 0
        assert out[0].startswith(f"board already running at http://127.0.0.1:{LINK_PORT}/")
        assert not bound
    elif case == "other-version":
        assert code == EXIT_EXTERNAL and err.count("\n") == 1
        assert "0.0.1" in err and __version__ in err and "PID 4242" in err and stop in err
        assert not bound
    elif case == "silent":
        assert code == EXIT_EXTERNAL and "does not answer" in err and "PID 4242" in err
        assert stop in err and not bound
    elif case == "dead":
        assert code == 0 and len(bound) == 1
        # the fresh entry was written (`_run` is stubbed, so it stays)
        assert json.loads(path.read_text("utf-8"))["server"]["pid"] == os.getpid()
    elif case == "migrate-live-older":
        assert code == EXIT_EXTERNAL and "0.0.1" in err and "PID 4242" in err and stop in err
        assert not bound and not path.with_name(state.OLD_BOARD).exists()
        assert json.loads(path.read_text("utf-8"))["key"] == "old-key"
    elif case == "migrate-key-only":
        assert code == 0 and len(bound) == 1 and not path.with_name(state.OLD_BOARD).exists()
        assert json.loads(path.read_text("utf-8"))["key"] == "old-key"
    else:
        assert code == EXIT_EXTERNAL and "0.0.1" in err and not bound
        if case == "no-record-old":
            assert "PID unknown" in err and "port" in err
        else:
            assert "PID 777" in err and running.stop_command(777) in err


def test_new_key_keeps_the_running_record_and_the_exit_removes_only_its_own(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared(repo, chantier, "Board one")
    home = open_projects().home
    git = home.git_dir
    path = board_key.key_path(home)
    first = board_key.load_or_create(home)
    state.write_server(git, "127.0.0.1", PORT, "1", "x")
    state.write_hub(git, state.hub_record("1"))
    assert board_key.load_or_create(home, new=True) != first
    data = json.loads(path.read_text("utf-8"))
    assert data["server"]["port"] == PORT and data["server"]["pid"] == os.getpid()
    assert data["hub"]["pid"] == os.getpid()
    for name in (state.SERVER, state.HUB):
        state.remove_entry(git, name, os.getpid() + 1)
        assert name in json.loads(path.read_text("utf-8"))
        state.remove_entry(git, name, os.getpid())
        assert name not in json.loads(path.read_text("utf-8"))
    assert board_key.read_key(path)
    # a refused write (the write lock held) at start: nothing is bound, nothing is printed
    monkeypatch.setattr(state, "WAIT_S", 0.05)
    held = (path.parent / state.LOCK).open("a+")
    assert try_lock(held)
    bound: list[int] = []
    monkeypatch.setattr(command, "_bind", lambda *_a, **_k: bound.append(1))
    monkeypatch.setattr(command, "probe", lambda *_a, **_k: None)
    try:
        for extra in ((), ("--new-key",)):
            code, out, err = chantier("serve", "--port", "0", *extra)
            assert code == EXIT_EXTERNAL and out == [] and not bound
            assert f"board not started: {path}: " in err and "write lock" in err
    finally:
        unlock(held)
        held.close()


@pytest.mark.parametrize("chosen", [True, False], ids=["single-project", "no-project-chosen"])
def test_board_seat_adds_the_foreign_build_line_only_for_the_sessions_own_project(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, chosen: bool
) -> None:
    """A recorded board at this version with another `source`: one added line, exit 0, the seat
    registered; none when `open_projects()` only took the first project of a surface."""
    served = open_projects().served.as_posix()
    rec = {
        "pid": 4242,
        "host": "127.0.0.1",
        "port": LINK_PORT,
        "version": __version__,
        "source": "/uv/cache/chantier",
        "served": served,
        "started": "2026-01-01T00:00:00Z",
    }
    _prepare_board(repo, chantier, monkeypatch, (True, rec, _answer(served, __version__)))
    seats: list[tuple[Any, ...]] = []

    def register(*a: Any) -> bool:
        seats.append(a)
        return True

    monkeypatch.setattr(command, "register_seat", register)
    monkeypatch.setattr("chantier.hub.lines.is_dev_checkout", lambda: True)
    monkeypatch.setattr("chantier.hub.lines.is_chantier_project", lambda _repo: True)
    real = open_projects

    def opened() -> Any:
        found = real()
        found.chosen = chosen
        return found

    monkeypatch.setattr("chantier.board.command.open_projects", opened)
    code, out, err = chantier("serve", "--seat", "s-1")
    assert code == 0, err
    assert any(x.startswith("board already running at") for x in out) and len(seats) == 1
    said = [x for x in out if x.startswith("board runs another build of chantier")]
    assert said == (
        [
            f"board runs another build of chantier {__version__} (/uv/cache/chantier), "
            "not this checkout's"
        ]
        if chosen
        else []
    )
