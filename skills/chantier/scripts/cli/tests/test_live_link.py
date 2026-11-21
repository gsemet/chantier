"""`chantier live` against one real server (`127.0.0.1`, port 0, in a thread) over a running batch
whose CR one is taken (its lease is live): `--once` on each transport, a journal line read once,
`auto` falling back on a refused upgrade, a wrong key, the refusals of the command line; and the
import check of `clients/tui/`. One server for the module, the times shortened by the seam."""

from __future__ import annotations

import ast
import contextlib
import io
import re
import shutil
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import open_batch
from conftest import PLUGIN_ROOT, SEEDED_COMMON_DIRS, SKILL, _key

from chantier import __version__
from chantier.board import key as keys
from chantier.board import reads
from chantier.board.api import times
from chantier.board.api.push import PushLoop, PushThread
from chantier.board.app import make_server
from chantier.board.context import Context
from chantier.board.projects import Projects
from chantier.board.seats import Seats
from chantier.cli import main
from chantier.clients.tui import link as link_module
from chantier.clients.tui.link import Event, Link
from chantier.clients.tui.model import Model
from chantier.commands import live as live_command
from chantier.core import clock
from chantier.core.errors import EXIT_EXTERNAL, EXIT_USAGE
from chantier.core.repo import Repo
from chantier.hub import journal as forge_journal
from chantier.hub import state

T0 = "2030-01-01T00:00:00Z"  # the lease taken at T0 is live until 00:10:00
WAIT_S = 10.0
TUI = SKILL / "scripts" / "cli" / "src" / "chantier" / "clients" / "tui"
ALLOWED = ("chantier.clients.tui", "chantier.core.errors")
NEEDS_KEY = "this board needs the link with its key"
LEASE = re.compile(r"lease \d\d:\d\d")


class Live:
    def __init__(self, work: Path, port: int, key: str, cr: str) -> None:
        self.work, self.port, self.key, self.cr = work, port, key, cr

    def url(self, key: str | None = None) -> str:
        return f"http://127.0.0.1:{self.port}/?k={self.key if key is None else key}"


def _cli(*args: object) -> tuple[int, list[str], str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main([str(a) for a in args])
    return code, out.getvalue().splitlines(), err.getvalue()


def _batch(work: Path, mp: pytest.MonkeyPatch) -> str:
    """A running batch of one CR, taken at T0: its id."""
    mp.setenv("CHANTIER_SKILL_DIR", str(SKILL))
    mp.setenv("CHANTIER_PLUGIN_ROOT", str(PLUGIN_ROOT))
    mp.setenv("HOME", str(work.parent))
    mp.setenv("USERPROFILE", str(work.parent))
    for var in ("CHANTIER_ROOT", "CHANTIER_BATCH", "CLAUDE_CODE_SESSION_ID", "COPILOT_CLI"):
        mp.delenv(var, raising=False)
    (cr,) = open_batch(work, _cli, mp, "Watched live")
    code, out, err = _cli("take", cr, "--epoch", 1)
    assert code == 0 and out[0].endswith(", lease 1 until 00:10:00"), err
    return cr


@pytest.fixture(scope="module")
def live(repo_template: Path, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Live]:
    work = tmp_path_factory.mktemp("live") / "proj"
    shutil.copytree(repo_template, work)
    with pytest.MonkeyPatch.context() as mp:
        mp.chdir(work)
        mp.setitem(SEEDED_COMMON_DIRS, _key(work), str(work / ".git"))
        mp.setattr(clock, "_fixed", [])
        clock.fix(T0)
        mp.setenv(times.TEST_ENV, "0.2:1:0.3:1")
        mp.setenv("NO_PROXY", "127.0.0.1")
        cr = _batch(work, mp)
        found = Repo.find(readonly=True)
        projects = Projects(found, None, [])
        secret = keys.load_or_create(found)
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        host, port = sock.getsockname()[:2]
        box: list[Any] = []
        ctx = Context(
            projects,
            keys.KeyFile(keys.key_path(found)),
            Seats(projects),
            "t",
            lambda: setattr(box[0], "should_exit", True),
            None,
            (host, port),
        )
        box.append(make_server(ctx))
        ctx.push = PushLoop(ctx)
        push = PushThread(ctx.push, ctx.stop)
        push.start()
        thread = threading.Thread(target=box[0].run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        while not box[0].started:
            thread.join(0.01)
        for _ in range(3):  # the live reading settles
            reads.state_of(ctx, projects.all()[0], ask=True)
        state.write_server(found.git_dir, host, port, __version__, str(work))
        yield Live(work, port, secret, cr)
        box[0].should_exit = True
        thread.join(WAIT_S)
        push.stop()
        sock.close()


@pytest.mark.parametrize("transport", ["ws", "http"])
def test_live_once_prints_the_working_cr_and_its_lease_and_a_journal_line_comes_once(
    live: Live, transport: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["live", "--once", "--transport", transport]) == 0  # the recorded board
    out = capsys.readouterr().out
    assert "working 1" in out and live.cr in out and LEASE.search(out), out
    assert "\x1b" not in out  # plain text
    _a_line_comes_once(live, transport)


def _a_line_comes_once(live: Live, transport: str) -> None:
    """A second read of the link: its first answers, then one line appended to the journal comes
    in one `events` event, and no event gives it again within the next second."""
    link, m = Link(live.url().split("?")[0], live.key, transport), Model()
    text = f"probe {transport}"
    told: list[str] = []
    deadline, until = time.monotonic() + WAIT_S, None
    with contextlib.closing(link.items()) as items:
        link.want(m.wanted())
        for item in items:
            m.feed(item)
            link.want(m.wanted())
            if isinstance(item, Event) and item.topic == "events":
                told += [str(x.get("text") or "") for x in item.data["lines"]]
            if not m.missing() and until is None:
                until = deadline
                event = forge_journal.board_event("new", [transport], text)
                forge_journal.append(Repo.find(readonly=True), [event], "board")
            if any(text in x for x in told) and until == deadline:
                until = time.monotonic() + 1.0
            if until is not None and time.monotonic() > until:
                break
            assert time.monotonic() < deadline, told
    assert sum(text in x for x in told) == 1, told  # given once, never again


def test_auto_ends_on_http_when_the_websocket_route_refuses_the_upgrade(
    live: Live, monkeypatch: pytest.MonkeyPatch
) -> None:
    refused = f"ws://127.0.0.1:{live.port}/api/v1/no-socket"  # the real server answers 404
    monkeypatch.setattr(Link, "ws_address", lambda _self: refused)
    link = Link(f"http://127.0.0.1:{live.port}/", live.key, "auto")
    with contextlib.closing(link.items()) as items:
        link.want(Model().wanted())
        first = next(items)
    assert getattr(first, "transport", None) == "http"


@pytest.mark.parametrize("transport", ["ws", "http"])
def test_once_exits_4_with_what_is_missing_by_its_deadline(
    live: Live, transport: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(live_command, "ONCE_S", 0.5)
    monkeypatch.setattr(Model, "missing", lambda _self: ["never"])  # one answer never comes
    monkeypatch.setattr(link_module, "POLL_S", 60.0)  # a poll alone would wait past it
    start = time.monotonic()
    code, _, err = _cli("live", "--once", "--transport", transport)
    assert code == EXIT_EXTERNAL and "no first answer within 0.5 s for never" in err, err
    assert time.monotonic() - start < WAIT_S / 2  # well before a held poll would answer


@pytest.mark.parametrize("transport", ["ws", "http", "auto"])
def test_a_wrong_key_exits_4_with_the_servers_sentence(live: Live, transport: str) -> None:
    code, _, err = _cli("live", "--once", "--url", live.url("wrong"), "--transport", transport)
    assert code == EXIT_EXTERNAL and NEEDS_KEY in err, err


def test_the_command_lines_refusals(
    live: Live, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    code, _, err = _cli("live", "--once", "--url", f"http://127.0.0.1:{live.port}/")
    assert code == EXIT_USAGE and "the link holds no key (?k=...)" in err, err
    code, _, err = _cli("live")  # stdout is not a terminal here
    assert code == EXIT_USAGE and "run it in a terminal, or pass --once" in err, err
    other = tmp_path / "other"
    shutil.copytree(live.work, other)
    (other / ".git" / "chantier" / "server.json").unlink()
    monkeypatch.chdir(other)
    monkeypatch.setitem(SEEDED_COMMON_DIRS, _key(other), str(other / ".git"))
    code, _, err = _cli("live", "--once")
    assert code == EXIT_EXTERNAL and "no board runs for this surface" in err, err


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.update(f"{node.module}.{a.name}" for a in node.names)
    return {n for n in names if n.split(".")[0] == "chantier"}


def test_the_terminal_client_imports_only_itself_the_version_and_the_errors() -> None:
    modules = sorted(TUI.glob("*.py"))
    assert {p.name for p in modules} >= {"__init__.py", "link.py", "model.py", "screen.py"}
    for path in modules:
        for name in _imports(path):
            assert name == "chantier.__version__" or name.startswith(ALLOWED), (path.name, name)
