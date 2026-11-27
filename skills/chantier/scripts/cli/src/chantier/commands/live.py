"""`chantier live`: one to four running boards watched live in the terminal, through the server's
published API (`clients/tui/`), read-only toward the server. A board is the one recorded as running
for this surface or project, called on the loopback address, or each `--url`; `live` never starts
one and never writes `server.json`. The one file it writes is `live.json` in the user's chantier
configuration folder, the two column widths, on a mouse drag's release; it reads it at its start,
before it connects, and `--once` does neither. It prints through its own console and returns no
lines."""

from __future__ import annotations

import argparse
import contextlib
import os
import signal
import sys
import threading
import time
import urllib.parse
from typing import Any

from chantier.board.address import loopback_base
from chantier.board.projects import open_projects
from chantier.clients import profiles
from chantier.clients.remote import profile_for
from chantier.clients.tui import screen, widths
from chantier.clients.tui.boxes import agent_lines
from chantier.clients.tui.link import Link
from chantier.clients.tui.model import Model, merged
from chantier.clients.tui.ready import ready_height
from chantier.clients.tui.view import View
from chantier.core.errors import EXIT_EXTERNAL, EXIT_USAGE, ChantierError
from chantier.hub import state

ONCE_S = 10.0  # `--once` waits this long for the first event of every subscription
ONCE_W = 120  # `--once`'s width when the terminal says none
FLOW_SHOWN = 40  # `--once` prints at most this many lines of the flow
MAX_BOARDS = 4
LABELS = "abcd"
LOOK_S = 0.05  # `--once` looks at what the readers have found this often
NO_KEY = "--url: the link holds no key (?k=...): give the link the board printed"
NO_BOARD = (
    "live: no board runs for this surface: start one with chantier serve (or chantier webui), "
    "or pass --url <link>"
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


def _check_only(models: list[Model]) -> None:
    """Refuse a `--only` id that no board serves, once every board is known."""
    if any(m.board is None for m in models):
        return
    if len(models) == 1:
        unknown = models[0].unknown_only()
        if unknown:
            served = ", ".join(p["id"] for p in models[0].projects()) or "none"
            raise ChantierError(f"--only {unknown[0]}: the board serves {served}", EXIT_USAGE)
        return
    ids = {p["id"] for m in models for p in m.projects()}
    nobody = [x for x in models[0].only if x not in ids]
    if nobody:
        names = ", ".join(m.named(p["id"]) for m in models for p in m.projects()) or "none"
        raise ChantierError(f"--only {nobody[0]}: no board serves it; served: {names}", EXIT_USAGE)


def _width() -> int:
    try:
        return os.get_terminal_size(sys.stdout.fileno()).columns
    except (AttributeError, OSError, ValueError):
        return ONCE_W


def height_for(models: Model | list[Model]) -> int:
    """`--once`'s height: what the tallest of the three columns needs, each box with its header
    row and borders. Projects and Ready are at most half the body, so the body is at least twice
    each of them."""
    models = [models] if isinstance(models, Model) else models
    box, head = screen.BORDERS, screen.HEADER_ROW
    projects = box + 2 * sum(len(m.watched()) for m in models)
    agents = box + max(len(agent_lines(models)), 1)
    ready = box + head + ready_height(models)
    tasks = box + head + screen.tasks_height(models)
    flow = box + head + min(len(merged(models)), FLOW_SHOWN)
    body = max(projects + agents, ready + tasks, flow, 2 * projects, 2 * ready, 3 + box)
    return screen.header_height(models) + screen.FOOTER_H + body


def _read(
    link: Link, m: Model, models: list[Model], lock: threading.Lock, stop: threading.Event
) -> None:
    """Feed the model with what the link gives, under the lock, until `stop` is set. A key or
    protocol refusal of the link ends it with the board's address; `--only`'s errors do not."""
    link.want(m.wanted())
    with contextlib.closing(link.items()) as items:
        while True:
            try:
                item = next(items)
            except StopIteration:
                return
            except ChantierError as e:
                raise ChantierError(f"{e} (board {link.base})", e.code) from e
            if stop.is_set():
                return
            with lock:
                m.feed(item)
                _check_only(models)
            link.want(m.wanted())


def _start(
    links: list[Link], models: list[Model], lock: threading.Lock, stop: threading.Event
) -> tuple[list[threading.Thread], list[ChantierError]]:
    """One reader thread per board; the errors of the readers are kept in the list."""
    failed: list[ChantierError] = []

    def work(link: Link, m: Model) -> None:
        try:
            _read(link, m, models, lock, stop)
        except ChantierError as e:
            failed.append(e)

    threads = [
        threading.Thread(target=work, args=(k, m), name=f"chantier-live-{i}", daemon=True)
        for i, (k, m) in enumerate(zip(links, models, strict=True))
    ]
    for t in threads:
        t.start()
    return threads, failed


def _missing(models: list[Model]) -> list[str]:
    if len(models) == 1:
        return models[0].missing()
    return [f"{m.label} {x}" for m in models for x in m.missing()]


def _pending(models: list[Model]) -> list[str]:
    return [x for m in models for x in m.pending_prs()]


def once(links: list[Link], models: list[Model]) -> None:
    """One printed screen once every subscription of every board has answered; exit 4 with what
    is missing after `ONCE_S`, on either transport (a poll is never held past the deadline). A
    `prs` answer the forge has not given by then is no reason to fail: the screen prints and
    Ready reads `not read`."""
    deadline = time.monotonic() + ONCE_S
    for link in links:
        link.deadline = deadline
    lock, stop, look = threading.Lock(), threading.Event(), threading.Event()
    _, failed = _start(links, models, lock, stop)
    try:
        while True:
            with lock:
                missing, pending = _missing(models), _pending(models)
            if failed:
                raise failed[0]
            if not missing and (not pending or time.monotonic() > deadline):
                break
            if time.monotonic() > deadline:
                what = ", ".join(missing)
                sentence = (
                    f"live: the board gave no first answer within {ONCE_S:g} s for {what}"
                    if len(models) == 1
                    else f"live: no first answer within {ONCE_S:g} s for {what}"
                )
                raise ChantierError(sentence, EXIT_EXTERNAL)
            look.wait(LOOK_S)
    finally:
        stop.set()
    with lock:
        # a reader raises `--only`'s error after its last feed, so the loop may see every board
        # complete before the error is kept: judge the finished models here, whatever the order
        _check_only(models)
        screen.plain(models, _width(), height_for(models), sys.stdout)


def watch(
    links: list[Link],
    models: list[Model],
    view: View | None = None,
    term: Any = None,
    console: Any = None,
) -> None:
    """The screen, redrawn once a second and at each key, one reader thread per board; `q` and
    Ctrl-C (and SIGTERM on POSIX) leave, with the terminal given back."""
    view = view or View()
    lock, stop = threading.Lock(), threading.Event()
    threads, failed = _start(links, models, lock, stop)

    def terminate(_signum: int, _frame: Any) -> None:
        raise KeyboardInterrupt

    previous = None
    if sys.platform != "win32" and threading.current_thread() is threading.main_thread():
        previous = signal.signal(signal.SIGTERM, terminate)
    try:
        screen.run(models, view, lock, lambda: all(t.is_alive() for t in threads), term, console)
    except KeyboardInterrupt:
        return
    finally:
        stop.set()
        if previous is not None:
            signal.signal(signal.SIGTERM, previous)
    if failed:
        raise failed[0]


def _boards(args: argparse.Namespace) -> tuple[list[tuple[str, str]], bool]:
    """The (base address, key) of each board asked for, or the active profile's, or the recorded
    one; and whether the user gave the address (its proxies then count)."""
    if len(args.url) > MAX_BOARDS:
        raise ChantierError(f"--url: at most {MAX_BOARDS} boards in one screen", EXIT_USAGE)
    boards = [from_link(u) for u in args.url]
    seen: set[str] = set()
    for base, _ in boards:
        if base in seen:
            raise ChantierError(f"--url {base}: given twice", EXIT_USAGE)
        seen.add(base)
    if boards:
        return boards, True
    if taken := profile_for(args):  # no --url: the active profile's server
        return [(taken[1].url, taken[1].key)], True
    return [recorded()], False


def _kept_view() -> View:
    """A view with the column widths `live.json` keeps, which it writes there at a drag's release;
    a file with a fault is refused."""
    view = View()
    view.file = profiles.config_dir() / widths.FILE
    view.left, view.right = widths.load(view.file)
    return view


def live(args: argparse.Namespace) -> list[Any]:
    if not args.once and not sys.stdout.isatty():
        raise ChantierError(NO_TERMINAL, EXIT_USAGE)
    view = None if args.once else _kept_view()  # before any connection
    boards, explicit = _boards(args)
    links = [Link(b, k, args.transport, proxies=explicit) for b, k in boards]
    labels = list(LABELS[: len(boards)]) if len(boards) > 1 else [""]
    models = [
        Model(only=list(args.only), label=label, base=base)
        for (base, _), label in zip(boards, labels, strict=True)
    ]
    if view is None:
        once(links, models)
    else:
        watch(links, models, view)
    return []
