"""The board's Griller: the conversations and the runs of the headless host CLI the surface server
starts for a CR of the inbox, the backlog or `3-ready` (AGENTS.md, the fourth exception of the
surface server). One conversation per (project, item), kept in memory; one run per message, resumed
from the run before; at most one running turn on the server.

The host side (`Run`, `HEADLESS`, the seam `command(run)` and `environment(run)` that a test
replaces, `availability`) is in `griller_host.py`; the child process, its standard input, the exit
code and the kill of its tree run for real."""

from __future__ import annotations

import re
import socket
import subprocess
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chantier import plugin_files
from chantier.board import griller_files as files
from chantier.board.griller_host import (
    CLEARED_ENV,
    HEADLESS,
    NO_HOST,
    NOT_PROVED,
    NOT_PROVED_COPILOT,
    ROLE,
    Refused,
    Run,
    availability,
    command,
    end_tree,
    environment,
    item_folder,
    result,
)
from chantier.board.projects import Project
from chantier.commands.writer_line import line as writer_line
from chantier.core import clock
from chantier.core.errors import ChantierError
from chantier.hub import journal
from chantier.playbook import config
from chantier.writer import lines as writer_lines

__all__ = [  # the host side's names, which the API and the tests reach here
    "CLEARED_ENV",
    "NOT_PROVED",
    "NOT_PROVED_COPILOT",
    "NO_HOST",
    "Refused",
    "availability",
    "command",
    "environment",
]

TURN_LIMIT_S = 600.0  # a turn's time, under the test seam
MOVE_CHECK_S = 1.0  # the CR's path is looked at least this often during a turn
TEXT_MAX = 8000
FROM_MAX = 64
STATES = ("running", "done", "stopped", "timed-out", "failed")

_BUSY = "a Griller turn runs on {project}/{item}: wait for it or stop it"
GRILLED = re.compile(r"\[griller→board\] grilled enough: (next batch|running batch)\s*$")
BRIEF = """\
chantier board-griller for the board, in the project {root}.
Your card: {skill}/references/griller.md, its section "Started from the board" first.
The CLI: {cli}.
The CR's folder: {folder}. You write only there.
The user speaks to you from the web board; their words follow.
"""


# --- the conversations ------------------------------------------------------------------------


@dataclass
class Turn:
    n: int
    sender: str  # the client id (`from`)
    user: str
    state: str = "running"
    answer: str | None = None
    error: str | None = None
    wrote: list[str] = field(default_factory=list[str])
    started: str = ""
    ended: str | None = None
    grilled: str | None = None  # the destination, when the answer ends with the board's line

    def value(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "from": self.sender,
            "user": self.user,
            "answer": self.answer,
            "state": self.state,
            "error": self.error,
            "wrote": list(self.wrote),
            "started": self.started,
            "ended": self.ended,
            "grilled": self.grilled,
        }


@dataclass
class Conversation:
    session: str = field(default_factory=lambda: str(uuid.uuid4()))
    started: str = field(default_factory=clock.now)
    turns: list[Turn] = field(default_factory=list[Turn])
    resumable: bool = False  # a run's result was read: the next one resumes the id
    stopping: str | None = None  # a stop asked: `stopped`, or the reason of a stop by the server
    proc: Any = None


class Registry:
    """The server's conversations and its one running turn. `wake` is called at each change (the
    push loop's `wake`): a latency gain only."""

    def __init__(self, wake: Callable[[], None] | None = None) -> None:
        self._wake = wake or (lambda: None)
        self._lock = threading.Lock()
        self._chats: dict[tuple[str, str], Conversation] = {}
        self._turn: tuple[str, str, str, threading.Thread] | None = None  # project, item, since

    # reads

    def running(self) -> dict[str, str] | None:
        with self._lock:
            if self._turn is None:
                return None
            return {"project": self._turn[0], "item": self._turn[1], "since": self._turn[2]}

    def busy(self, project: str, item: str) -> bool:
        """Whether a turn runs on this item (the board's own writes on it are refused)."""
        with self._lock:
            return self._turn is not None and self._turn[:2] == (project, item)

    def get(self, project: Project, item: str) -> dict[str, Any]:
        """What `griller.get` answers: the availability, the machine, the running turn, the
        conversation (None before the first message)."""
        value = availability(project) | {"machine": socket.gethostname(), "running": self.running()}
        with self._lock:
            chat = self._chats.get((project.id, item))
            value["conversation"] = (
                {"started": chat.started, "turns": [t.value() for t in chat.turns]}
                if chat
                else None
            )
        return value

    def join(self, timeout: float = 30.0) -> None:
        """Wait for the running turn's thread (a test's wait)."""
        with self._lock:
            thread = self._turn[3] if self._turn else None
        if thread is not None:
            thread.join(timeout)

    # writes

    def send(self, project: Project, item: str, text: str, sender: str) -> Turn:
        """Start a turn: the refusals in their order, then the thread. Raises `Refused`."""
        repo = project.repo
        folder = item_folder(project, item)
        avail = availability(project)
        if not avail["available"]:
            raise Refused(409, str(avail["reason"]))
        if repo.external and writer_lines.refused(repo.git_dir):
            raise Refused(409, writer_line(repo))
        if (held := self.running()) is not None:  # `_start` checks again, under its lock
            raise Refused(409, _BUSY.format(**held))
        if not text.strip() or len(text) > TEXT_MAX:
            raise Refused(400, f"'text' is 1 to {TEXT_MAX} characters")
        if len(sender) > FROM_MAX:
            raise Refused(400, f"'from' is {FROM_MAX} characters at most")
        run_data = _Start(project, item, folder, avail, text, sender)
        return self._start(run_data)

    def stop(self, project: str, item: str, why: str | None = None) -> bool:
        """Stop the item's running turn (its process tree); False when none ran."""
        with self._lock:
            if self._turn is None or self._turn[:2] != (project, item):
                return False
            chat = self._chats[(project, item)]
            chat.stopping = chat.stopping or why or "stopped"
            proc = chat.proc
        if proc is not None and proc.poll() is None:  # not one that exited meanwhile
            end_tree(proc)
        return True

    def stop_all(self, why: str) -> None:
        """The server's stop: end the running turn (`failed` is not its state: `stopped`), then
        wait for its thread."""
        with self._lock:
            held = self._turn
        if held is not None:
            self.stop(held[0], held[1], why)
            held[3].join(10.0)

    def end(self, project: str, item: str) -> None:
        """Forget the conversation (the files stay). Raises `Refused` while a turn runs."""
        if self.busy(project, item):
            raise Refused(409, "stop the turn first")
        with self._lock:
            self._chats.pop((project, item), None)
        self._wake()

    # the turn

    def _saved(self, s: _Start) -> bool:
        """Whether the host saved a conversation for a cut first run's id: asked of the host's own
        state outside the registry's lock (the turn that decides is checked under it)."""
        with self._lock:
            chat = self._chats.get((s.project.id, s.item))
            asked = chat is not None and not chat.resumable and bool(chat.turns)
            session = chat.session if chat else ""
        return asked and HEADLESS[s.avail["host"]].saved(session)

    def _start(self, s: _Start) -> Turn:
        saved = self._saved(s)
        with self._lock:
            if self._turn is not None:  # the check and the set are one lock: two sends, one turn
                raise Refused(409, _BUSY.format(project=self._turn[0], item=self._turn[1]))
            chat = self._chats.setdefault((s.project.id, s.item), Conversation())
            first = _first(chat, saved)
            turn = Turn(len(chat.turns) + 1, s.sender, s.text, started=clock.now())
            chat.turns.append(turn)
            chat.stopping = None
            run = _run_of(s, chat.session, first)
            thread = threading.Thread(
                target=self._work, args=(s, chat, turn, run), name="board-griller", daemon=True
            )
            self._turn = (s.project.id, s.item, turn.started, thread)
        thread.start()
        self._wake()
        return turn

    def _work(self, s: _Start, chat: Conversation, turn: Turn, run: Run) -> None:
        where = s.folder
        try:
            try:
                s.before, s.began = files.listing(s.folder), time.time_ns()
                where = _drive(s, chat, turn, run)
            except Exception as e:  # a code fault never leaves a turn running for ever
                turn.state, turn.error = "failed", f"{type(e).__name__}: {e}"
            turn.wrote = files.changed(s.before, files.listing(where)) if where.is_dir() else []
            turn.ended = clock.now()
            _record(s, turn)
        finally:
            with self._lock:
                chat.proc = None
                self._turn = None
            self._wake()


@dataclass
class _Start:
    project: Project
    item: str
    folder: Path
    avail: dict[str, Any]
    text: str
    sender: str
    before: files.Listing = field(default_factory=files.Listing)  # the folder at the turn's start
    began: int = 0  # the turn's start, ns


def _first(chat: Conversation, saved: bool) -> bool:
    """Whether the next run is the conversation's first: no run's result was read and the host
    saved no conversation for the id (a cut first run that the host kept is resumed)."""
    return not chat.resumable and not (chat.turns and saved)


def _run_of(s: _Start, session: str, first: bool) -> Run:
    repo = s.project.repo
    host = s.avail["host"]
    skill = plugin_files.skill_dir()
    cwd = repo.session_root.resolve()
    readable = [cwd]
    for extra in ([repo.clone] if repo.external else []) + [skill]:
        if not any(extra.resolve().is_relative_to(r) for r in readable):
            readable.append(extra.resolve())
    cli = plugin_files.cli_command(repo)
    brief = BRIEF.format(
        root=repo.root.as_posix(),
        skill=skill.as_posix(),
        cli=cli,
        folder=s.folder.resolve().as_posix(),
    )
    return Run(
        s.project,
        s.item,
        s.folder.resolve(),
        host,
        HEADLESS[host].cli,
        s.avail["model"],
        config.default_agent(host, ROLE),
        session,
        first,
        f"{brief}\n{s.text}" if first else s.text,
        cwd,
        readable,
        skill,
        skill.parents[1],
        cli,
    )


def _drive(s: _Start, chat: Conversation, turn: Turn, run: Run) -> Path:
    """The process of one turn, to its end; the folder `wrote` is read from. Sets the turn's state,
    answer and error."""
    repo = s.project.repo
    try:
        argv = command(run)
        proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=run.cwd,
            env=environment(run),
        )
    except (OSError, ChantierError) as e:
        turn.state, turn.error = "failed", str(e)
        return s.folder
    chat.proc = proc
    if chat.stopping:  # a Stop that came before the process existed
        end_tree(proc)
    limit = time.monotonic() + TURN_LIMIT_S
    data: bytes | None = run.prompt.encode("utf-8")
    gone = False
    while True:
        remaining = limit - time.monotonic()
        try:
            out, err = proc.communicate(data, timeout=max(0.01, min(MOVE_CHECK_S, remaining)))
            break
        except subprocess.TimeoutExpired:
            data = None  # the input is sent once
        if not chat.stopping and time.monotonic() >= limit:
            chat.stopping = "timed-out"
        elif not chat.stopping:
            if files.has_moved(repo, s.item, run.folder, s.before, gone):
                chat.stopping = "moved"
            gone = not run.folder.is_dir()
        if chat.stopping:
            end_tree(proc)
    return _settle(s, chat, turn, run, (out, err, proc.returncode))


def _settle(
    s: _Start,
    chat: Conversation,
    turn: Turn,
    run: Run,
    done: tuple[bytes, bytes, int],
) -> Path:
    repo = s.project.repo
    out, err, code = done
    stopped = chat.stopping
    if stopped == "moved":
        elsewhere = [p for p in files.locate(repo, s.item) if p != run.folder]
        left = files.clean(run.folder, s.before, s.began)
        turn.state = "failed"
        turn.error = files.moved_text(repo, s.item, elsewhere) + (
            f"; left at the old path: {', '.join(left)}" if left else ""
        )
        return elsewhere[0] if elsewhere else run.folder
    if stopped == "timed-out":
        turn.state, turn.error = "timed-out", f"cut at {TURN_LIMIT_S / 60:g} minutes"
    elif stopped:
        turn.state = "stopped"
        turn.error = None if stopped == "stopped" else stopped
    else:
        turn.answer, turn.error = result(out, err, code)
        turn.state = "done" if turn.error is None else "failed"
        chat.resumable = chat.resumable or turn.answer is not None
        last = (turn.answer or "").strip().splitlines()[-1:] or [""]
        found = GRILLED.search(last[0])
        turn.grilled = found.group(1) if found else None
    return run.folder


def _record(s: _Start, turn: Turn) -> None:
    """The one waking `board@1` line of a turn that wrote (whatever its end), through the one
    append function."""
    if not turn.wrote:
        return
    text = f"the board's Griller wrote {s.item} ({', '.join(turn.wrote)})"
    if turn.state != "done":
        text += "; cut"
    if turn.grilled:
        text += (
            f"; grilled enough, destination {turn.grilled}, already recorded in 02-answers.md "
            "by the Griller: nothing to write"
        )
    journal.append(s.project.repo, [journal.board_event("grill", [s.item], text)], "board")
