"""The socket of the surface server: bound before anything is printed, a port held said."""

from __future__ import annotations

import errno
import socket
import sys
from collections.abc import Callable

from chantier.core.errors import EXIT_EXTERNAL, ChantierError

TAKES_PORT = (
    "board: port {port} is held by another chantier board ({who}): this one takes port {free}"
)
WSAEADDRINUSE = 10048  # Windows' "address in use"


def _in_use(e: OSError) -> bool:
    return e.errno == errno.EADDRINUSE or getattr(e, "winerror", None) == WSAEADDRINUSE


def not_started(reason: object) -> ChantierError:
    return ChantierError(f"board not started: {' '.join(str(reason).split())}", EXIT_EXTERNAL)


def bind(
    host: str,
    port: int,
    held: Callable[[], str] | None = None,
    other: Callable[[], str | None] | None = None,
) -> socket.socket:
    """The socket, bound and listening before anything is printed (a client that connects on the
    start line is queued): a port held fails here, unless `other` names another chantier board
    there (the default port only): then a free port is taken, and said. On
    Windows SO_REUSEADDR lets a second socket take a port in use: never there."""
    sock = socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET, socket.SOCK_STREAM)
    try:
        if sys.platform != "win32":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(socket.SOMAXCONN)
    except (OSError, OverflowError) as e:
        sock.close()
        if other is not None and isinstance(e, OSError) and _in_use(e) and (who := other()):
            free = bind(host, 0)
            print(TAKES_PORT.format(port=port, who=who, free=free.getsockname()[1]), flush=True)
            return free
        if held is not None and isinstance(e, OSError) and _in_use(e):
            raise not_started(held()) from e
        raise not_started(e) from e
    return sock
