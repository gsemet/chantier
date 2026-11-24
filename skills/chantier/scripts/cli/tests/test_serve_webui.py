"""The surface server's command is `serve`, and `webui` prints its link: the renamed lines, the
two surfaces on one machine, each server's own cookie, and `webui`'s start."""

from __future__ import annotations

import errno
import socket
import types
from pathlib import Path
from typing import Any

import pytest
from conftest import Chantier
from test_board_running import _answer, _prepare_board

from chantier.board import address, binding, command, guard, routes, running
from chantier.board import key as keys
from chantier.board.context import Context, Request
from chantier.board.key import KeyFile
from chantier.board.projects import open_projects
from chantier.board.seats import Seats
from chantier.commands import live, webui
from chantier.core.errors import EXIT_EXTERNAL, ChantierError
from chantier.hub import feed, watch_lines
from chantier.playbook.board_check import MAX_PORT
from chantier.writer import lines as writer_lines

OK, UNAUTHORISED, USAGE, START_S = 200, 401, 2, 20
ANOTHER = command._another_version("1", 7, "http://x/", "kill 7").args[0]


@pytest.mark.parametrize(
    ("text", "wanted"),
    [
        (ANOTHER, "chantier serve 1 (PID 7)"),
        (ANOTHER, "then run serve again"),
        (running.silent_text({"pid": 7, "host": "h", "port": 1}), "then run serve again"),
        (writer_lines.START, "$CHANTIER serve --seat <session id> --forge-always"),
        (writer_lines.older_text({"version": "1", "pid": 7}), "chantier serve 1 (PID 7)"),
        (watch_lines.NO_KEY, "{cli} serve --seat <session id> --forge-always"),
        (watch_lines.NOT_STARTED, "{cli} serve --seat {session}"),
        (live.NO_BOARD, "start one with chantier serve (or chantier webui)"),
    ],
)
def test_the_lines_that_name_the_command_name_serve(text: str, wanted: str) -> None:
    assert wanted in text and "board --" not in text


@pytest.mark.parametrize(("word", "found"), [("serve", 11), ("board", 12), ("other", None)])
def test_the_watcher_starts_serve_and_find_pid_knows_serve_and_board(
    repo: Path, monkeypatch: pytest.MonkeyPatch, word: str, found: int | None
) -> None:
    argv = feed.serve_argv(open_projects().home, "s-1")
    assert argv[-4:] == ["serve", "--seat", "s-1", "--stop-idle"]
    import psutil

    listen = types.SimpleNamespace(status=psutil.CONN_LISTEN, laddr=types.SimpleNamespace(port=77))

    def proc(pid: int, *cmd: str) -> Any:
        return types.SimpleNamespace(
            info={"pid": pid, "cmdline": list(cmd)}, net_connections=lambda kind: [listen]
        )

    procs = [proc(5, "python", "chantier", "status"), proc(found or 13, "chantier", word)]
    monkeypatch.setattr(psutil, "process_iter", lambda _a: procs)
    assert running.find_pid(77) == found


def test_a_command_named_board_is_an_invalid_choice(
    chantier: Chantier, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as stopped:
        chantier("board", "--port", "0")
    assert stopped.value.code == USAGE and "invalid choice: 'board'" in capsys.readouterr().err


def _hold(count: int = 1) -> tuple[list[socket.socket], int]:
    """`count` consecutive ports held on 127.0.0.1, and the free one right above them."""
    while True:
        first = socket.socket()
        first.bind(("127.0.0.1", 0))
        base = first.getsockname()[1]
        held, spare = [first], socket.socket()
        try:
            for port in range(base + 1, base + count):
                held.append(socket.socket())
                held[-1].bind(("127.0.0.1", port))
            spare.bind(("127.0.0.1", base + count))
        except OSError:
            for each in (*held, spare):
                each.close()
            continue
        spare.close()
        for each in held:
            each.listen(1)
        return held, base


@pytest.mark.parametrize(
    "case",
    [
        ("another-key", 1, False, "another chantier board (another project's key)"),
        ("another-folder", 1, False, "another chantier board (/elsewhere/surface)"),
        ("plain", 1, False, "another program"),
        ("plain", 2, False, "another program"),
        ("another-key", 1, True, ""),
    ],
)
def test_a_default_port_held_walks_to_the_first_free_port_above_it(
    repo: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    case: tuple[str, int, bool, str],
) -> None:
    holder, rows, named, who = case
    answers: dict[str, Any] = {
        "another-key": "another-key",
        "another-folder": _answer("/elsewhere/surface", "1"),
        "plain": "other",
    }
    path, bound = _prepare_board(repo, chantier, monkeypatch, (False, None, answers[holder]))
    held, port = _hold(rows)
    try:
        monkeypatch.setattr(address, "DEFAULT_PORT", port)
        code, out, err = chantier("serve", *(("--port", str(port)) if named else ()))
        if not named:
            assert code == 0, err
            assert (
                out[0] == f"board: port {port} is held by {who}: this one takes port {port + rows}"
            )
            assert bound == [port + rows] and out[1].startswith("board on ")
            assert f":{port + rows}/" in out[1] and str(port + rows) in path.read_text("utf-8")
        else:
            assert code == EXIT_EXTERNAL and not bound and out == []
            assert "is held by another chantier board" in err or "is in use" in err
    finally:
        for each in held:
            each.close()


class Refused(OSError):
    """A bind error as Windows words it: `winerror` set, `errno` not the POSIX one."""

    def __init__(self, winerror: int) -> None:
        super().__init__(0, "refused")
        self.winerror = winerror


@pytest.mark.parametrize(
    ("error", "last", "wanted"),
    [
        (OSError(errno.EADDRINUSE, "in use"), MAX_PORT, "no free port from 8765 to 65535 on h:"),
        (Refused(binding.WSAEACCES), 8767, "this one takes port 8768"),
        (Refused(binding.WSAEADDRINUSE), 8766, "this one takes port 8767"),
        (OSError(errno.EPERM, "denied"), 8766, "board not started: [Errno 1] denied"),
    ],
)
def test_the_walk_counts_in_use_and_access_denied_as_held_and_ends_at_the_last_port(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: OSError,
    last: int,
    wanted: str,
) -> None:
    sock = socket.socket()

    def refuse(_host: str, port: int) -> socket.socket:
        if port <= last:
            raise error
        return sock

    monkeypatch.setattr(binding, "_open", refuse)
    try:
        if error.errno == errno.EPERM or last == MAX_PORT:
            with pytest.raises(ChantierError) as stopped:
                binding.bind("h", 8765, None, lambda: "another program")
            assert wanted in str(stopped.value) and stopped.value.code == EXIT_EXTERNAL
        else:
            assert binding.bind("h", 8765, None, lambda: "another program") is sock
            assert wanted in capsys.readouterr().out
    finally:
        sock.close()


def test_each_servers_cookie_is_its_own(repo: Path, tmp_path: Path) -> None:
    one, two = keys.cookie_name(tmp_path / "a"), keys.cookie_name(tmp_path / "b")
    assert one != two and one == keys.cookie_name(tmp_path / "a")
    assert len(one) == len("chantier_board_") + 12
    both = {"cookie": f"{one}=key-a; {two}=key-b"}
    assert guard.authorised(Request("GET", "/", {}, both), "key-a", one)
    assert guard.authorised(Request("GET", "/", {}, both), "key-b", two)
    assert not guard.authorised(Request("GET", "/", {}, both), "key-a", two)
    got = guard.exchange(Request("GET", "/", {"k": "key-a"}, {}), "key-a", one)
    assert got is not None and got.all_headers()["Set-Cookie"].startswith(f"{one}=key-a;")
    assert two not in got.all_headers()["Set-Cookie"]
    keyfile = tmp_path / "key.json"
    keyfile.write_text('{"key": "k1"}', encoding="utf-8")
    projects = open_projects()
    ctx = Context(projects, KeyFile(keyfile), Seats(projects), "0", lambda: None, None)
    for cookie, status in (("chantier_board=k1", UNAUTHORISED), (f"{ctx.cookie}=k1", OK)):
        head = {"cookie": cookie, "host": "board"}
        assert routes.handle(ctx, Request("GET", "/api/board", {}, head)).status == status


class FakeBoard:
    """`webui`'s reach outside itself: the record, the probe, the spawn, the clock."""

    def __init__(self, recorded: bool, answers: bool, starts: bool) -> None:
        self.entry = {"host": "127.0.0.1", "port": 4321, "pid": 9, "version": "1", "served": "/s"}
        self.up, self.answers, self.starts = recorded, answers, starts
        self.spawned: list[list[str]] = []
        self.now = 0.0

    def recorded(self, _git_dir: Path) -> tuple[dict[str, Any], str] | None:
        return (self.entry, "k9") if self.up else None

    def probe(self, *_a: object) -> dict[str, Any] | None:
        return {"board": True} if self.answers else None

    def spawn(self, argv: list[str], _cwd: Path) -> None:
        self.spawned.append(argv)
        self.up = self.answers = self.starts

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


WEBUI_STATES = {  # recorded, answers, a spawned server comes up
    "running": (True, True, True),
    "starts": (False, False, True),
    "timeout": (False, False, False),
    "silent": (True, False, False),
}


@pytest.mark.parametrize("case", ["running", "starts", "timeout", "silent"])
def test_webui_prints_the_link_and_starts_a_server_when_none_runs(
    repo: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    fake = FakeBoard(*WEBUI_STATES[case])
    monkeypatch.setattr(webui, "Board", lambda: fake)
    keys.load_or_create(open_projects().home)
    read = command.READ_ONLY.format(
        link=f"http://127.0.0.1:4321/?k={keys.public_key(open_projects().home)}"
    )
    code, out, err = chantier("webui")
    if case in ("running", "starts"):
        assert read in out and out.index(read) == 1  # after the private link's line
    if case == "running":
        assert code == 0 and out[0] == "board already running at http://127.0.0.1:4321/?k=k9"
        assert not fake.spawned
    elif case == "starts":
        assert code == 0 and out[0] == "board on http://127.0.0.1:4321/?k=k9 over /s"
        assert out[-1] == webui.STOPS_IDLE
        assert fake.spawned[0][-2:] == ["serve", "--stop-idle"] and "--seat" not in fake.spawned[0]
    elif case == "timeout":
        assert code == EXIT_EXTERNAL and "did not start within 20 s" in err and " serve " in err
        assert out == [] and fake.now >= START_S
    else:
        assert code == EXIT_EXTERNAL and err.startswith("error: webui: a chantier board")
        assert "then run serve again" in err and not fake.spawned
