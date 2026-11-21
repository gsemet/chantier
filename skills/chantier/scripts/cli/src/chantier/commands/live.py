"""`chantier live`: a running board watched live in the terminal, read-only, through the server's
published API (`clients/tui/`). The board is the one recorded as running for this surface or
project, called on the loopback address, or the one of `--url`; `live` never starts one and never
writes `server.json`. It prints through its own console and returns no lines."""

from __future__ import annotations

import argparse
import contextlib
import os
import sys
import threading
import time
import urllib.parse
from typing import Any

from chantier.board.address import loopback_base
from chantier.board.projects import open_projects
from chantier.clients.tui import screen
from chantier.clients.tui.link import Link
from chantier.clients.tui.model import Model
from chantier.core.errors import EXIT_EXTERNAL, EXIT_USAGE, ChantierError
from chantier.hub import state

ONCE_S = 10.0  # `--once` waits this long for the first event of every subscription
ONCE_W = 120  # `--once`'s width when the terminal says none
FLOW_SHOWN = 40  # `--once` prints at most this many lines of the flow
NO_KEY = "--url: the link holds no key (?k=...): give the link the board printed"
NO_BOARD = (
    "live: no board runs for this surface: start one with chantier board, or pass --url <link>"
)
NO_TERMINAL = "live draws a screen: run it in a terminal, or pass --once for one printed screen"


def from_link(link: str) -> tuple[str, str]:
    """The base address (scheme, host, port and path prefix) and the key of a board's link."""
    parts = urllib.parse.urlsplit(link)
    key = urllib.parse.parse_qs(parts.query).get("k", [""])[0]
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ChantierError(f"--url {link}: give the http(s) link the board printed", EXIT_USAGE)
    if not key:
        raise ChantierError(NO_KEY, EXIT_USAGE)
    path = parts.path if parts.path.endswith("/") else parts.path + "/"
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, "", "")), key


def recorded() -> tuple[str, str]:
    """The board recorded as running for this surface or project, on the loopback address."""
    found = state.live_server(open_projects().home.git_dir)
    if found is None:
        raise ChantierError(NO_BOARD, EXIT_EXTERNAL)
    entry, key = found
    return loopback_base(str(entry["host"]), int(entry["port"])), key


def _check_only(m: Model) -> None:
    unknown = m.unknown_only()
    if unknown:
        served = ", ".join(p["id"] for p in m.projects()) or "none"
        raise ChantierError(f"--only {unknown[0]}: the board serves {served}", EXIT_USAGE)


def _width() -> int:
    try:
        return os.get_terminal_size(sys.stdout.fileno()).columns
    except (AttributeError, OSError, ValueError):
        return ONCE_W


def height_for(m: Model) -> int:
    """`--once`'s height: what the longest column needs."""
    rows = m.rows()
    working = sum(1 for _, r in rows if r.get("state") == "working")
    review = sum(1 for _, r in rows if r.get("to_review"))
    blocked = sum(1 for _, r in rows if r.get("state") == "blocked")
    tasks = 2 * working + review + bool(review) + blocked + bool(blocked) or 1
    left = 2 * len(m.watched()) + 2 + max(len(m.agents()), 1)
    body = max(min(len(m.flow), FLOW_SHOWN), tasks, left, 3)
    return screen.HEADER_H + screen.FOOTER_H + screen.BORDERS + body


def once(link: Link, m: Model) -> None:
    """One printed screen once every subscription has answered; exit 4 with what is missing
    after `ONCE_S`, on either transport (a poll is never held past the deadline)."""
    deadline = time.monotonic() + ONCE_S
    link.deadline = deadline
    link.want(m.wanted())
    with contextlib.closing(link.items()) as items:
        for item in items:
            m.feed(item)
            _check_only(m)
            link.want(m.wanted())
            if not m.missing():
                break
            if time.monotonic() > deadline:
                missing = ", ".join(m.missing())
                raise ChantierError(
                    f"live: the board gave no first answer within {ONCE_S:g} s for {missing}",
                    EXIT_EXTERNAL,
                )
    screen.plain(m, _width(), height_for(m), sys.stdout)


def _read(link: Link, m: Model, lock: threading.Lock, stop: threading.Event) -> None:
    """Feed the model with what the link gives, under the lock, until `stop` is set."""
    link.want(m.wanted())
    with contextlib.closing(link.items()) as items:
        for item in items:
            if stop.is_set():
                return
            with lock:
                m.feed(item)
                _check_only(m)
            link.want(m.wanted())


def watch(link: Link, m: Model) -> None:
    """The screen, redrawn once a second, the link read in a thread of its own; Ctrl-C leaves."""
    lock = threading.Lock()
    stop = threading.Event()
    failed: list[ChantierError] = []

    def work() -> None:
        try:
            _read(link, m, lock, stop)
        except ChantierError as e:
            failed.append(e)

    reader = threading.Thread(target=work, name="chantier-live", daemon=True)
    reader.start()
    try:
        screen.run(m, lock, reader.is_alive)
    except KeyboardInterrupt:
        return
    finally:
        stop.set()
    if failed:
        raise failed[0]


def live(args: argparse.Namespace) -> list[Any]:
    if not args.once and not sys.stdout.isatty():
        raise ChantierError(NO_TERMINAL, EXIT_USAGE)
    base, key = from_link(args.url) if args.url else recorded()
    link = Link(base, key, args.transport, proxies=bool(args.url))
    m = Model(only=list(args.only))
    if args.once:
        once(link, m)
    else:
        watch(link, m)
    return []
