"""The socket of the surface server: bound before anything is printed, a port held said."""

from __future__ import annotations

import errno
import socket
import sys
from collections.abc import Callable

from chantier.core.errors import EXIT_EXTERNAL, ChantierError
from chantier.playbook.board_check import MAX_PORT

TAKES_PORT = "board: port {port} is held by {holder}: this one takes port {free}"
NO_FREE_PORT = "no free port from {port} to {last} on {host}: pass --port <n> (0: any free port)"
WSAEADDRINUSE = 10048  # Windows' "address in use"
WSAEACCES = 10013  # Windows' "access denied": a port in a reserved range, or held exclusively


def _held(e: OSError) -> bool:
    """A port that is held, or that Windows denies: the walk goes on past it."""
    return e.errno == errno.EADDRINUSE or getattr(e, "winerror", None) in (WSAEADDRINUSE, WSAEACCES)


def not_started(reason: object) -> ChantierError:
    return ChantierError(f"board not started: {' '.join(str(reason).split())}", EXIT_EXTERNAL)


def _open(host: str, port: int) -> socket.socket:
    """One socket, bound and listening, or the OSError of its bind. On Windows SO_REUSEADDR lets a
    second socket take a port in use: never there."""
    sock = socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET, socket.SOCK_STREAM)
    try:
        if sys.platform != "win32":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(socket.SOMAXCONN)
    except (OSError, OverflowError):
        sock.close()
        raise
    return sock


def _stop_or_walk(
    e: OSError | OverflowError,
    last: int,
    held: Callable[[], str] | None,
    walking: bool,
    none_free: str,
) -> None:
    """Returns when the walk goes on past `last`; else raises the refusal."""
    is_held = isinstance(e, OSError) and _held(e)
    if is_held and walking:
        if last >= MAX_PORT:
            raise not_started(none_free) from e
        return
    raise not_started(held() if is_held and held is not None else e) from e


def bind(
    host: str,
    port: int,
    held: Callable[[], str] | None = None,
    holder: Callable[[], str] | None = None,
) -> socket.socket:
    """The socket, bound and listening before anything is printed (a client that connects on the
    start line is queued). A port held fails here with `held()`'s text. With `holder` (the default
    port only), the walk goes on to the next port while one is held, up to MAX_PORT, and the line
    that names the default port's holder (`holder()`) is printed once a later port is kept."""
    last = port
    none_free = NO_FREE_PORT.format(port=port, last=MAX_PORT, host=host)
    while True:
        try:
            sock = _open(host, last)
        except (OSError, OverflowError) as e:
            _stop_or_walk(e, last, held, holder is not None, none_free)
            last += 1
            continue
        if holder is not None and last != port:
            print(TAKES_PORT.format(port=port, holder=holder(), free=last), flush=True)
        return sock
