"""`chantier board`: the surface server (the web board, and the forge hub loop in the same
process). The options, the key, the start lines and the probe of a server already running;
`starlette` and `uvicorn` load only once the board serves."""

from __future__ import annotations

import argparse
import contextlib
import errno
import os
import socket
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from chantier import __version__
from chantier.board import running
from chantier.board.address import (
    is_loopback,
    local_url,
    probe,
    register_seat,
    settings,
    url,
)
from chantier.board.api.push import PushLoop, PushThread
from chantier.board.app import make_server
from chantier.board.context import Context
from chantier.board.key import KeyFile, load_or_create
from chantier.board.projects import Projects, check_planning, open_projects
from chantier.board.seats import Seats
from chantier.core import clock
from chantier.core.errors import EXIT_EXTERNAL, EXIT_USAGE, ChantierError
from chantier.declare.board import SHIPPED_UI
from chantier.hub import state
from chantier.hub.loop import HubLoop, HubThread
from chantier.playbook.layers import load_board
from chantier.writer import lines as writer_lines
from chantier.writer import record as writer_record
from chantier.writer.loop import WriterLoop, WriterThread

T = TypeVar("T")
NOT_APPLIED = (
    "--ui not applied: a board already serves this surface; stop it to change what it serves"
)
BEYOND = (
    "board: listens on the local network ({host}); the link holds its key: give it to the user "
    "only, plain HTTP"
)


def _not_started(reason: object) -> ChantierError:
    return ChantierError(f"board not started: {' '.join(str(reason).split())}", EXIT_EXTERNAL)


WSAEADDRINUSE = 10048  # Windows' "address in use"
WAY_OUT = "pass --port <n> (0: any free port)"


def _in_use(e: OSError) -> bool:
    return e.errno == errno.EADDRINUSE or getattr(e, "winerror", None) == WSAEADDRINUSE


def _held_by(host: str, port: int, key: str, from_config: bool) -> str:
    """The refusal's text for a port in use: what holds it as far as the probe tells, and the
    way out."""
    where = f"port {port} on {host}"
    out = WAY_OUT + (" or change board.port in chantier.yaml" if from_config else "")
    found = probe(host, port, key)
    if isinstance(found, dict):
        link = url(host, port, key)
        return (
            f"{where} is held by a chantier board over {found.get('served')}: open {link}, or {out}"
        )
    if found == "another-key":
        return (
            f"{where} is held by another chantier board (another project's key; its session "
            f"printed its link): {out}"
        )
    return f"{where} is in use (a board may already run there, or another program): {out}"


def _bind(host: str, port: int, held: Callable[[], str] | None = None) -> socket.socket:
    """The socket, bound and listening before anything is printed (a client that connects on the
    start line is queued): a port held fails here. On
    Windows SO_REUSEADDR lets a second socket take a port in use: never there."""
    sock = socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET, socket.SOCK_STREAM)
    try:
        if sys.platform != "win32":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(socket.SOMAXCONN)
    except (OSError, OverflowError) as e:
        sock.close()
        if held is not None and isinstance(e, OSError) and _in_use(e):
            raise _not_started(held()) from e
        raise _not_started(e) from e
    return sock


def _start_writer(projects: Projects) -> WriterThread | None:
    """The surface's writer, only when the folder served is an external planning surface: its
    start line, and its thread. A writer that cannot start (its lock is held by another process)
    leaves the board serving, and says why."""
    home = projects.home
    if not home.external:
        return None
    loop = WriterLoop(home)
    why = loop.start()
    if why:
        print(f"board: writer not started: {' '.join(why.split())}", flush=True)
        return None
    print(writer_lines.state_line(writer_record.read(home.git_dir)), flush=True)
    thread = WriterThread(loop)
    thread.start()
    return thread


def _run(projects: Projects, seats: Seats, sock: socket.socket, ui: Path | None) -> None:
    """Serve until Ctrl-C, or, for a board started with `--seat`, until its seats leave."""
    box: list[Any] = []

    def stop() -> None:
        box[0].should_exit = True

    ctx = Context(
        projects,
        KeyFile(state.path(projects.home.git_dir)),
        seats,
        __version__,
        stop,
        ui,
        sock.getsockname()[:2],
    )
    box.append(make_server(ctx))
    seats.arm(stop)
    hub = HubThread(HubLoop(projects.home), stop)
    hub.start()
    ctx.push = PushLoop(ctx)
    push = PushThread(ctx.push, stop)
    push.start()
    writer = _start_writer(projects)
    try:
        box[0].run(sockets=[sock])
    except KeyboardInterrupt:
        pass
    finally:
        if writer is not None:
            writer.stop()  # its final cycle, before the server's entry goes
        push.stop()
        hub.stop()
        sock.close()
        with contextlib.suppress(OSError):  # an entry left behind names a dead process
            state.remove_entry(projects.home.git_dir, state.SERVER, os.getpid())


def _another_version(version: object, pid: object, link: str, stop: str) -> ChantierError:
    return _not_started(
        f"chantier board {version} (PID {pid}) already serves this surface at {link}; this is "
        f"chantier {__version__}: to replace it, stop it ({stop}), then run board again"
    )


def _silent(run: dict[str, Any]) -> ChantierError:
    return _not_started(
        f"a chantier board {run.get('version')} (PID {run['pid']}) holds this surface at "
        f"{run['host']}:{run['port']} and does not answer: stop it "
        f"({running.stop_command(run['pid'])}), then run board again"
    )


def _recorded(projects: Projects, run: dict[str, Any], key: str) -> tuple[str, int]:
    """The board the record names, which a live process holds: its address when it answers as
    this version over this folder; a refusal otherwise. Nothing is signalled."""
    host, port = run["host"], run["port"]
    found = probe(host, port, key)
    if not isinstance(found, dict) or found.get("served") != projects.served.as_posix():
        raise _silent(run)
    if found.get("version") != __version__:
        raise _another_version(
            found.get("version"), run["pid"], url(host, port, key), running.stop_command(run["pid"])
        )
    return host, port


def _answering(projects: Projects, host: str, port: int, key: str) -> tuple[str, int] | None:
    """No record: a board of this folder, behind this key, that answers at the configured
    address. An older version is refused, its PID from its answer or looked up."""
    found = probe(host, port, key) if port else None
    if not isinstance(found, dict) or found.get("served") != projects.served.as_posix():
        return None
    if found.get("version") == __version__:
        return host, port
    pid = found.get("pid") or running.find_pid(port)
    stop = (
        running.stop_command(pid)
        if pid
        else f"stop it from the session that started it, or end the process that listens on "
        f"port {port}"
    )
    raise _another_version(found.get("version"), pid or "unknown", url(host, port, key), stop)


def _writing(write: Callable[[], T]) -> T:
    """A write of `server.json`; a refused one is `board not started: <path>: <reason>`."""
    try:
        return write()
    except OSError as e:
        raise _not_started(e) from e


def _announce(host: str, bound: int, key: str, served: str) -> None:
    print(f"board on {url(host, bound, key)} over {served}", flush=True)
    if local := local_url(host, bound, key):
        print(f"on this machine: {local}", flush=True)
    if not is_loopback(host):
        print(BEYOND.format(host=host), flush=True)


def _ui(arg: Path | str) -> Path | None:
    """The folder to serve: `None` for `none`, else a folder holding an `index.html`."""
    if arg == "none":
        return None
    folder = Path(arg).resolve()
    if not (folder / "index.html").is_file():
        raise ChantierError(
            f"--ui {arg}: not a folder with an index.html: give a folder of static files, or none",
            EXIT_USAGE,
        )
    return folder


def board(args: argparse.Namespace) -> list[str]:
    if args.clock:
        try:
            clock.fix(args.clock)
        except ValueError as e:
            raise ChantierError(
                f"--clock {args.clock!r}: use YYYY-MM-DDTHH:MM:SSZ", EXIT_USAGE
            ) from e
    ui = _ui(args.ui)
    projects = open_projects()
    try:
        check_planning(projects)
    except ChantierError as e:
        raise _not_started(e) from e
    host, port = settings(projects.home, args.host, args.port)
    git_dir = projects.home.git_dir
    _writing(lambda: state.migrate(git_dir))
    key = _writing(lambda: load_or_create(projects.home, args.new_key))
    seats = Seats(projects, follows=bool(args.seat))
    if args.seat:
        seats.add(projects.home_id, args.seat)
    run = state.live_entry(git_dir, state.SERVER)
    there = _recorded(projects, run, key) if run else _answering(projects, host, port, key)
    if there:
        if args.seat and not register_seat(*there, key, projects.home_id, args.seat):
            raise _not_started("the board already running there did not take the seat")
        lines = [f"board already running at {url(*there, key)}"]
        if local := local_url(*there, key):
            lines.append(f"on this machine: {local}")
        if args.ui != SHIPPED_UI:
            lines.append(NOT_APPLIED)
        return lines
    _writing(lambda: state.check_writable(git_dir))  # a refused write: known before any bind
    from_config = args.port is None and "port" in load_board(projects.home)[0]
    sock = _bind(host, port, lambda: _held_by(host, port, key, from_config))
    bound, served = sock.getsockname()[1], projects.served.as_posix()
    try:
        _writing(lambda: state.write_server(git_dir, host, bound, __version__, served))
    except ChantierError:
        sock.close()
        raise
    _announce(host, bound, key, served)
    _run(projects, seats, sock, ui)
    return []
