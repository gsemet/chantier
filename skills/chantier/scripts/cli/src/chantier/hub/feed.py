"""What a watcher needs of the surface server: the recorded server, the link to its `events` topic
read in a thread of its own (`Feed`), the detached start of a board, and the board's lines the
watcher passes on. `Board` gathers every call that reaches the server or the system, so a test
replaces it whole and drives the watcher with no server, no process and no sleep."""

from __future__ import annotations

import contextlib
import queue
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Protocol

from chantier import __version__
from chantier.board import address
from chantier.board.command import BEYOND, NO_NETWORK, files_line
from chantier.clients.tui.link import Idle, Item, Link, Linked, Refusal
from chantier.core.repo import Repo
from chantier.hub import state
from chantier.playbook.layers import load_board
from chantier.plugin_files import cli_command

CLIENT = f"chantier-watch/{__version__}"
TOPIC = "events"

Got = Item | Refusal  # what a feed gives: the link's items, or the refusal that ended it


class Feed(Protocol):
    """One link to the board's `events` topic: `drain` gives what came since the last call,
    without waiting; `close` ends it."""

    def drain(self) -> list[Got]: ...

    def close(self) -> None: ...


class LinkFeed:
    """A `Link` read in a daemon thread into a queue. The thread ends at the link's first loss
    (a `Linked` with no transport) or refusal, which it passes on: the watcher decides what
    comes next (the same board again, or a board started), and links again from its cursor."""

    def __init__(self, link: Link, project: str, after: int) -> None:
        self.link = link
        self.queue: queue.Queue[Got] = queue.Queue()
        self.closed = threading.Event()
        link.want([(TOPIC, TOPIC, {"project": project, "after": after})])
        self.thread = threading.Thread(target=self._run, name="chantier-watch-link", daemon=True)
        self.thread.start()

    def _pass(self, item: Item) -> bool:
        """Queue one item (an `Idle` says nothing); whether the thread goes on."""
        if self.closed.is_set():
            return False
        if not isinstance(item, Idle):
            self.queue.put(item)
        return not (isinstance(item, Linked) and item.transport is None)

    def _run(self) -> None:
        try:
            with contextlib.closing(self.link.items()) as items:
                all(map(self._pass, items))  # up to the first item that ends the thread
        except Refusal as e:
            self.queue.put(e)
        except Exception as e:  # anything else that ends the link is a loss
            self.queue.put(Linked(None, None, " ".join(str(e).split()) or type(e).__name__))

    def drain(self) -> list[Got]:
        out: list[Got] = []
        with contextlib.suppress(queue.Empty):
            while True:
                out.append(self.queue.get_nowait())
        return out

    def close(self) -> None:
        self.closed.set()


def board_argv(repo: Repo, session: str) -> list[str]:
    """The board a watcher starts: this CLI's `board --seat <session> --stop-idle`."""
    return [*shlex.split(cli_command(repo)), "board", "--seat", session, "--stop-idle"]


def spawn(argv: list[str], cwd: Path) -> None:
    """Start the board detached, never waited on: it outlives the watcher, its output goes
    nowhere. Windows: a new process group and a hidden console of its own, which its children
    (`git`, `gh`) inherit; never `DETACHED_PROCESS`, under which Windows ignores
    `CREATE_NO_WINDOW` and each child would open a console window."""
    if sys.platform == "win32":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        subprocess.Popen(
            argv,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=flags,
        )
    else:
        subprocess.Popen(
            argv,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )


class Board:
    """The watcher's every reach outside itself: the recorded server, its probe, the seat's
    registration, the link, the detached start, the clock and the wait."""

    def recorded(self, git_dir: Path) -> tuple[dict[str, Any], str] | None:
        return state.live_server(git_dir)

    def probe(self, host: str, port: int, key: str) -> dict[str, Any] | str | None:
        return address.probe(host, port, key)

    def register(self, entry: dict[str, Any], key: str, project: str, session: str) -> bool:
        return address.register_seat(entry["host"], entry["port"], key, project, session)

    def link(self, entry: dict[str, Any], key: str, project: str, after: int) -> Feed:
        base = address.loopback_base(str(entry["host"]), int(entry["port"]))
        link = Link(base, key)
        link.client = CLIENT
        return LinkFeed(link, project, after)

    def spawn(self, argv: list[str], cwd: Path) -> None:
        spawn(argv, cwd)

    def clock(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


def passed_on(repo: Repo, entry: dict[str, Any]) -> list[str]:
    """The lines of the board's start that the Chief of Staff passes on, which a board started
    detached cannot print itself: its exposure beyond this machine, or the local network it did
    not find, then its file watch's mode."""
    host = str(entry.get("host"))
    lines: list[str] = []
    if not address.is_loopback(host):
        lines.append(BEYOND.format(host=host))
    elif load_board(repo)[0].get("host") == address.NETWORK:
        lines.append(NO_NETWORK)
    if found := files_line(entry.get("files")):
        lines.append(found)
    return lines
