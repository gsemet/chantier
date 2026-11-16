"""`chantier board`: the web board's server. The options, the key, the start lines and the probe
of a board already running; `starlette` and `uvicorn` load only once the board serves."""

from __future__ import annotations

import argparse
import errno
import socket
import sys
from collections.abc import Callable
from typing import Any

from chantier import __version__
from chantier.board.address import (
    is_loopback,
    probe,
    register_seat,
    settings,
    url,
)
from chantier.board.app import make_server
from chantier.board.context import Context
from chantier.board.key import KeyFile, key_path, load_or_create
from chantier.board.projects import Projects, check_planning, open_projects
from chantier.board.seats import Seats
from chantier.core import clock
from chantier.core.errors import EXIT_EXTERNAL, EXIT_USAGE, ChantierError
from chantier.playbook.config import FILE, load_board

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


def _run(projects: Projects, seats: Seats, sock: socket.socket) -> None:
    """Serve until Ctrl-C or until the seats leave."""
    box: list[Any] = []

    def stop() -> None:
        box[0].should_exit = True

    ctx = Context(projects, KeyFile(key_path(projects.home)), seats, __version__, stop)
    box.append(make_server(ctx))
    seats.arm(stop)
    try:
        box[0].run(sockets=[sock])
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()


def _running(projects: Projects, host: str, port: int, key: str) -> bool:
    """A board of this folder, behind this key, already answers there."""
    found = probe(host, port, key) if port else None
    return isinstance(found, dict) and found.get("served") == projects.served.as_posix()


def board(args: argparse.Namespace) -> list[str]:
    if args.clock:
        try:
            clock.fix(args.clock)
        except ValueError as e:
            raise ChantierError(
                f"--clock {args.clock!r}: use YYYY-MM-DDTHH:MM:SSZ", EXIT_USAGE
            ) from e
    projects = open_projects()
    try:
        check_planning(projects)
    except ChantierError as e:
        raise _not_started(e) from e
    host, port = settings(projects.home, args.host, args.port)
    key = load_or_create(projects.home, args.new_key)
    seats = Seats(projects)
    if args.seat:
        seats.add(projects.home_id, args.seat)
    if _running(projects, host, port, key):
        if args.seat and not register_seat(host, port, key, projects.home_id, args.seat):
            raise _not_started("the board already running there did not take the seat")
        return [f"board already running at {url(host, port, key)}"]
    from_config = args.port is None and "port" in load_board(projects.home.root / FILE)[0]
    sock = _bind(host, port, lambda: _held_by(host, port, key, from_config))
    link = url(host, sock.getsockname()[1], key)
    print(f"board on {link} over {projects.served.as_posix()}", flush=True)
    if not is_loopback(host):
        print(BEYOND.format(host=host), flush=True)
    _run(projects, seats, sock)
    return []
