"""`chantier serve`: the surface server (the web board, the watch of the planning files and the
forge hub loop in the same process). The options, the key, the start lines and the probe of a
server already running; `starlette`, `uvicorn` and `watchfiles` load only once the board serves."""

from __future__ import annotations

import argparse
import contextlib
import os
import socket
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from chantier import __version__
from chantier.board import claim, running
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
from chantier.board.binding import bind as _bind
from chantier.board.binding import not_started as _not_started
from chantier.board.context import Context
from chantier.board.griller import Registry
from chantier.board.idle import IdleStop, IdleThread
from chantier.board.key import KeyFile, load_or_create, public_key
from chantier.board.options import extra_of, options_of
from chantier.board.projects import Projects, check_planning, open_projects
from chantier.board.restart import restart_with_key
from chantier.board.seats import Seats
from chantier.board.start_lines import (
    BEYOND,
    CHECKS,
    FORGE_WHEN_OBSERVED,
    NO_NETWORK,
    NOT_APPLIED,
    READ_ONLY,
    STOPS_IDLE,
    WATCHES,
    files_line,
    read_only_lines,
)
from chantier.board.start_lines import running_lines as _running_lines
from chantier.board.watch_files import FileWatchThread
from chantier.core.errors import ChantierError
from chantier.declare.serve import SHIPPED_UI
from chantier.hub import lock, state
from chantier.hub.lines import foreign_build_clause
from chantier.hub.loop import HubLoop, HubThread
from chantier.playbook.layers import load_board
from chantier.writer import lines as writer_lines
from chantier.writer import record as writer_record
from chantier.writer.loop import WriterLoop, WriterThread

# the start lines moved to `start_lines`; what other modules and the tests read here stays here
__all__ = [
    "BEYOND",
    "CHECKS",
    "FORGE_WHEN_OBSERVED",
    "NOT_APPLIED",
    "NO_NETWORK",
    "READ_ONLY",
    "STOPS_IDLE",
    "WATCHES",
    "_running_lines",
    "files_line",
    "read_only_lines",
]
T = TypeVar("T")
WAY_OUT = "pass --port <n> (0: any free port)"


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


def _holder(host: str, port: int, key: str, served: str) -> str:
    """What holds the default port, as far as the probe tells."""
    found = probe(host, port, key)
    if isinstance(found, dict) and found.get("served") != served:
        return f"another chantier board ({found.get('served')})"
    if found == "another-key":
        return "another chantier board (another project's key)"
    return "another program"


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


class _Stopper:
    """The board's stop (Ctrl-C's path): the server, once made, exits its loop."""

    def __init__(self) -> None:
        self.server: Any = None

    def __call__(self) -> None:
        if self.server is not None:
            self.server.should_exit = True


def _context(projects: Projects, seats: Seats, sock: socket.socket, ui: Path | None) -> Context:
    ctx = Context(
        projects,
        KeyFile(state.path(projects.home.git_dir)),
        seats,
        __version__,
        _Stopper(),
        ui,
        sock.getsockname()[:2],
    )
    ctx.griller = Registry(lambda: ctx.push.wake() if ctx.push is not None else None)
    return ctx


def _watch_files(ctx: Context) -> FileWatchThread:
    """Each project's first fingerprint (so the first page walks nothing), then the watch of the
    planning files, its mode known when this returns."""
    for project in ctx.projects.all():
        ctx.settle(project)
    git_dir = ctx.projects.home.git_dir
    files = FileWatchThread(ctx, lambda mode: state.set_server_files(git_dir, mode))
    files.start()
    return files


def _observer(args: argparse.Namespace, loop: PushLoop) -> Callable[[], bool]:
    """What the forge hub asks before a cycle: a client observes the server, or always with
    `--forge-always` (a host that cannot run the watcher)."""
    return (lambda: True) if args.forge_always else loop.observed


def _run(
    ctx: Context, sock: socket.socket, files: FileWatchThread, args: argparse.Namespace
) -> None:
    """Serve until Ctrl-C, or, for a board started with `--seat`, until its seats leave, or, with
    `--stop-idle`, after `IDLE_STOP_S` with no client. The forge hub reads only while a client
    observes, or always with `--forge-always`."""
    projects, stop = ctx.projects, ctx.stop
    assert isinstance(stop, _Stopper)
    stop.server = make_server(ctx)
    ctx.seats.arm(stop)
    loop = ctx.push = PushLoop(ctx)
    observed = _observer(args, loop)
    hub = HubThread(HubLoop(projects.home, held=ctx.claim), stop, observed)
    hub.start()
    git_dir = projects.home.git_dir
    push = PushThread(
        loop,
        stop,
        claim.tick(git_dir, ctx, stop),
    )
    push.start()

    def watched() -> bool:  # a client observes, or a client's command runs
        return loop.observed() or ctx.runs.busy()

    idle = IdleThread(IdleStop(watched, stop, time.monotonic())) if args.stop_idle else None
    if idle is not None:
        idle.start()
    writer = _start_writer(projects)
    try:
        stop.server.run(sockets=[sock])
    except KeyboardInterrupt:
        pass
    finally:
        if ctx.griller is not None:  # a running turn ends before the server does
            ctx.griller.stop_all("the board stopped")
        if idle is not None:
            idle.stop()
        if writer is not None:
            writer.stop()  # its final cycle, before the server's entry goes
        files.stop()
        push.stop()
        hub.stop()
        sock.close()
        with contextlib.suppress(OSError):  # an entry left behind names a dead process
            state.remove_entry(projects.home.git_dir, state.SERVER, os.getpid())


def _another_version(version: object, pid: object, link: str, stop: str) -> ChantierError:
    return _not_started(
        f"chantier serve {version} (PID {pid}) already serves this surface at {link}; this is "
        f"chantier {__version__}: to replace it, stop it ({stop}), then run serve again"
    )


def _silent(run: dict[str, Any]) -> ChantierError:
    return _not_started(running.silent_text(run))


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


def _announce(  # noqa: PLR0913, PLR0917 - the address, the link's keys, then what to print
    host: str, bound: int, key: str, served: str, after: list[str], read_key: str = ""
) -> None:
    """The start lines: the private link, this machine's link, the read-only link(s), the
    exposure, then `after` (the `NO_NETWORK` line, the file watch's)."""
    print(f"board on {url(host, bound, key)} over {served}", flush=True)
    if local := local_url(host, bound, key):
        print(f"on this machine: {local}", flush=True)
    for line in read_only_lines(host, bound, read_key):
        print(line, flush=True)
    if not is_loopback(host):
        print(BEYOND.format(host=host), flush=True)
    for line in after:
        print(line, flush=True)


def _listen(
    args: argparse.Namespace, projects: Projects, host: str, port: int, key: str
) -> socket.socket:
    """The bound socket: a named port held refuses; the default port held walks up to a free one."""
    from_config = args.port is None and "port" in load_board(projects.home)[0]
    served = projects.served.as_posix()
    default = args.port is None and not from_config
    holder = (lambda: _holder(host, port, key, served)) if default else None
    return _bind(host, port, lambda: _held_by(host, port, key, from_config), holder)


def _migrated(projects: Projects, args: argparse.Namespace, host: str, port: int) -> None:
    """The record migrated; with `--restart`, the board that runs stopped first."""
    _writing(lambda: state.migrate(projects.home.git_dir))
    if args.restart:
        restart_with_key(projects, host, port)


def _joined(projects: Projects, args: argparse.Namespace, key: str, won: bool) -> list[str] | None:
    """The lines of the board that already serves this surface, this start's seat registered on
    it; None when none does. A start that did not win the claim waits for the winner's board."""
    host, port, _ = settings(projects.home, args.host, args.port)
    git_dir = projects.home.git_dir
    run = state.live_entry(git_dir, state.SERVER)
    if run is None and not won:
        run = claim.wait_for_board(git_dir, key)
    there = _recorded(projects, run, key) if run else _answering(projects, host, port, key)
    if there is None:
        return None
    if args.seat and not register_seat(*there, key, projects.home_id, args.seat):
        raise _not_started("the board already running there did not take the seat")
    ui_given, read = args.ui != SHIPPED_UI, public_key(projects.home)
    lines = _running_lines(there, key, ui_given, run, args.forge_always, read)
    if run and projects.chosen and (found := foreign_build_clause(projects.home, __version__, run)):
        lines.append(found)
    return lines


def board(args: argparse.Namespace) -> list[str]:
    ui = options_of(args)
    projects = open_projects()
    try:
        check_planning(projects)
    except ChantierError as e:
        raise _not_started(e) from e
    host, port, _ = settings(projects.home, args.host, args.port)
    _migrated(projects, args, host, port)
    key = _writing(lambda: load_or_create(projects.home, args.new_key))
    held = lock.HubLock(projects.home.git_dir)
    try:  # the claim: held for the whole life of the serving process (the hub loop keeps it)
        return _start(args, projects, key, held, ui)
    finally:
        held.release()


def _start(
    args: argparse.Namespace, projects: Projects, key: str, held: lock.HubLock, ui: Path | None
) -> list[str]:
    host, port, no_network = settings(projects.home, args.host, args.port)
    git_dir = projects.home.git_dir
    seats = Seats(projects, follows=bool(args.seat))
    if args.seat:
        seats.add(projects.home_id, args.seat)
    if (joined := _joined(projects, args, key, held.acquire())) is not None:
        return joined
    _writing(lambda: state.check_writable(git_dir))  # a refused write: known before any bind
    sock = _listen(args, projects, host, port, key)
    bound, served = sock.getsockname()[1], projects.served.as_posix()
    ctx = _context(projects, seats, sock, ui)
    ctx.claim = held
    files = _watch_files(ctx)  # the mode is known before the start line
    try:
        extra = extra_of(args, files)
        _writing(lambda: state.write_server(git_dir, host, bound, __version__, served, **extra))
    except ChantierError:
        files.stop()
        sock.close()
        raise
    _announce(
        host,
        bound,
        key,
        served,
        [NO_NETWORK] * no_network + [files_line(files.mode) or WATCHES],
        public_key(projects.home),
    )
    _run(ctx, sock, files, args)
    return []
