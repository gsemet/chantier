"""The board stays on this machine unless asked: its default address, `board.host: network`
(found at each start), the lines it prints, and the cookie's life."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest
from batch_helpers import prepared
from conftest import Chantier
from test_board_running import _answer, _prepare_board

from chantier import __version__
from chantier.board import address, command, guard
from chantier.board import key as keys
from chantier.board.context import Request
from chantier.board.projects import open_projects
from chantier.board.watch_files import FileWatchThread
from chantier.core.errors import ChantierError
from chantier.core.repo import Repo
from chantier.playbook.board_check import HOST_NOT_NETWORK

LAN, OTHER_LAN = "192.168.1.20", "10.0.0.7"
SEE_OTHER = 303
NETWORK = "board:\n  host: network\n"


def _route(monkeypatch: pytest.MonkeyPatch, *found: str) -> None:
    """`_default_route_address` answers these addresses in turn (the last one again)."""
    answers = list(found)
    monkeypatch.setattr(
        address,
        "_default_route_address",
        lambda: answers.pop(0) if len(answers) > 1 else answers[0],
    )


def _config(repo: Path, text: str) -> Repo:
    (repo / "chantier.yaml").write_text(text, encoding="utf-8")
    return Repo.find()


def test_the_default_is_this_machine_and_network_is_found_at_each_start(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    here = Repo.find()
    assert address.settings(here, None, None) == ("127.0.0.1", 8765, False)
    there = _config(repo, NETWORK)
    _route(monkeypatch, LAN)
    assert address.settings(there, None, None) == ("0.0.0.0", 8765, False)
    assert address.settings(there, "0.0.0.0", 0) == ("0.0.0.0", 0, False)
    assert address.settings(there, "127.0.0.1", 0) == ("127.0.0.1", 0, False)  # not no-network
    _route(monkeypatch, "127.0.0.1")
    assert address.settings(there, None, None) == ("127.0.0.1", 8765, True)
    assert address.settings(there, "0.0.0.0", None)[2] is False
    _route(monkeypatch, LAN, OTHER_LAN)  # the address is not stored: each call finds it again
    assert LAN in address.url("0.0.0.0", 1)
    assert OTHER_LAN in address.url("0.0.0.0", 1)


@pytest.mark.parametrize(
    "value", ["127.0.0.1", "0.0.0.0", LAN, '""', "a b", "[network]", "network 1"]
)
def test_a_fixed_host_in_chantier_yaml_is_refused_with_the_way_to_give_it(
    repo: Path, value: str
) -> None:
    here = _config(repo, f"board:\n  host: {value}\n")
    with pytest.raises(ChantierError) as refused:
        address.settings(here, None, None)
    assert HOST_NOT_NETWORK in str(refused.value) and "--host" in str(refused.value)
    port = _config(repo, 'board:\n  port: "8 8"\n')
    with pytest.raises(ChantierError, match='"port" is one integer'):
        address.settings(port, None, None)


def _served(_ctx: object, sock: socket.socket, files: FileWatchThread, _args: object) -> None:
    """The board serves nothing: its socket closed, its file watch stopped (Windows lets the test
    folder go)."""
    files.stop()
    sock.close()


def _start(chantier: Chantier, repo: Path, config: str | None) -> list[str]:
    prepared(repo, chantier, "Board one")
    if config:
        (repo / "chantier.yaml").write_text(config, encoding="utf-8")
    code, out, err = chantier("board", "--port", "0")
    assert code == 0, err
    return out


@pytest.mark.parametrize("route", [LAN, "127.0.0.1"])
def test_start_lines_with_network_and_the_default(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, route: str
) -> None:
    _route(monkeypatch, route)
    monkeypatch.setattr(command, "probe", lambda *_a, **_k: None)
    monkeypatch.setattr(command, "_run", _served)
    out = _start(chantier, repo, NETWORK)
    lines_with_network = ("link", "local", "beyond", "files")
    if route == LAN:
        assert out[0].startswith(f"board on http://{LAN}:") and " over " in out[0]
        assert out[1].startswith("on this machine: http://127.0.0.1:")
        assert out[2].startswith("board: listens on the local network (0.0.0.0)")
        assert len(out) == len(lines_with_network) and out[-1] == command.WATCHES
    else:
        assert out[0].startswith("board on http://127.0.0.1:")
        assert out[1:] == [command.NO_NETWORK, command.WATCHES]


def test_the_default_start_prints_one_line(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(command, "probe", lambda *_a, **_k: None)
    monkeypatch.setattr(command, "_run", _served)
    out = _start(chantier, repo, None)
    assert out[0].startswith("board on http://127.0.0.1:") and out[1:] == [command.WATCHES]


def test_the_cookie_lasts_30_days_and_the_exchange_sets_it() -> None:
    cookie = keys.set_cookie("k")
    assert "Max-Age=2592000" in cookie and "HttpOnly" in cookie and "SameSite=Strict" in cookie
    got = guard.exchange(Request("GET", "/", {"k": "k"}, {}), "k")
    assert got is not None and got.status == SEE_OTHER
    assert "Max-Age=2592000" in got.all_headers()["Set-Cookie"]


@pytest.mark.parametrize(
    ("host", "lines"),
    [
        ("0.0.0.0", ("already", "on this", "listens")),
        (LAN, ("already", "listens")),
        ("127.0.0.1", ("already",)),
    ],
)
def test_a_second_start_says_when_the_running_board_is_open(
    repo: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    host: str,
    lines: tuple[str, ...],
) -> None:
    served = open_projects().served.as_posix()
    rec = {
        "pid": 4242,
        "host": host,
        "port": 40123,
        "version": __version__,
        "served": served,
        "started": "2026-01-01T00:00:00Z",
    }
    _prepare_board(repo, chantier, monkeypatch, (True, rec, _answer(served, __version__)))
    _route(monkeypatch, LAN)
    monkeypatch.setattr(command, "register_seat", lambda *_a, **_k: True)
    code, out, err = chantier("board", "--seat", "s")
    assert code == 0, err
    marks = {
        "already": "board already running at http://",
        "on this": "on this machine: http://127.0.0.1:",
        "listens": f"board: listens on the local network ({host})",
    }
    assert [line[: len(marks[m])] for line, m in zip(out, lines, strict=True)] == [
        marks[m] for m in lines
    ]
    assert len(out) == len(lines)
