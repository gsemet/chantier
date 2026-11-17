"""One board per planning surface: the running board's record and what a new `board` does."""

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
) -> tuple[Path, list[int]]:
    alive, record, answer = plan
    prepared(repo, chantier, "Board one")
    path = board_key.key_path(open_projects().home)
    board_key.load_or_create(open_projects().home)
    if record is not None:
        data = json.loads(path.read_text("utf-8"))
        path.write_text(json.dumps({**data, "running": record}), "utf-8")
    monkeypatch.setattr(procs, "alive_since", lambda *_a, **_k: alive)
    monkeypatch.setattr(command, "probe", lambda *_a, **_k: answer)
    monkeypatch.setattr(running, "find_pid", lambda _port: None)
    bound: list[int] = []

    def serve(_projects: object, _seats: object, sock: socket.socket) -> None:
        bound.append(sock.getsockname()[1])
        sock.close()

    monkeypatch.setattr(command, "_run", serve)
    _signals_nothing(monkeypatch)
    return path, bound


def _answer(served: str, version: str, pid: int | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"board": True, "version": version, "served": served}
    if pid is not None:
        body["pid"] = pid
    return body


@pytest.mark.parametrize(
    "case", ["same", "other-version", "silent", "dead", "no-record-old", "no-record-old-pid"]
)
def test_a_new_board_reuses_refuses_or_starts_by_what_the_surface_already_runs(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    served = open_projects().served.as_posix()
    rec = {
        "pid": 4242,
        "host": "127.0.0.1",
        "port": LINK_PORT,
        "version": __version__,
        "served": served,
        "started": "2026-01-01T00:00:00Z",
    }
    plans: dict[str, tuple[bool, dict[str, Any] | None, Any]] = {
        "same": (True, rec, _answer(served, __version__)),
        "other-version": (True, {**rec, "version": "0.0.1"}, _answer(served, "0.0.1")),
        "silent": (True, rec, None),
        "dead": (False, rec, None),
        "no-record-old": (False, None, _answer(served, "0.0.1")),
        "no-record-old-pid": (False, None, _answer(served, "0.0.1", 777)),
    }
    path, bound = _prepare_board(repo, chantier, monkeypatch, plans[case])
    code, out, err = chantier("board", "--host", "127.0.0.1", "--port", str(LINK_PORT + 1))
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
        # the fresh record was written (`_run` is stubbed, so it stays)
        assert json.loads(path.read_text("utf-8"))["running"]["pid"] == os.getpid()
    else:
        assert code == EXIT_EXTERNAL and "0.0.1" in err and not bound
        if case == "no-record-old":
            assert "PID unknown" in err and "port" in err
        else:
            assert "PID 777" in err and running.stop_command(777) in err


def test_new_key_keeps_the_running_record_and_the_exit_removes_only_its_own(repo: Path) -> None:
    home = open_projects().home
    path = board_key.key_path(home)
    first = board_key.load_or_create(home)
    running.write(path, "127.0.0.1", PORT, "1", "x")
    assert board_key.load_or_create(home, new=True) != first
    data = json.loads(path.read_text("utf-8"))
    assert data["running"]["port"] == PORT and data["running"]["pid"] == os.getpid()
    running.remove(path, os.getpid() + 1)
    assert "running" in json.loads(path.read_text("utf-8"))
    running.remove(path, os.getpid())
    assert "running" not in json.loads(path.read_text("utf-8"))
    assert board_key.read_key(path)
