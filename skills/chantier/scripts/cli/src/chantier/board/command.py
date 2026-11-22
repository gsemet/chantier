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
from chantier.board import running
from chantier.board.address import (
    is_loopback,
    local_url,
    probe,
    register_seat,
    settings,
    url,
)
from chantier.board.api import times
from chantier.board.api.push import PushLoop, PushThread
from chantier.board.app import make_server
from chantier.board.binding import bind as _bind
from chantier.board.binding import not_started as _not_started
from chantier.board.context import Context
from chantier.board.griller import Registry
from chantier.board.idle import IdleStop, IdleThread
from chantier.board.key import KeyFile, load_or_create
from chantier.board.projects import Projects, check_planning, open_projects
from chantier.board.seats import Seats
from chantier.board.watch_files import NOTIFY, FileWatchThread
from chantier.core import clock
from chantier.core.errors import EXIT_USAGE, ChantierError
from chantier.declare.serve import SHIPPED_UI
from chantier.hub import state
from chantier.hub.lines import foreign_build_clause
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
NO_NETWORK = "board: no local network address found; on this machine only"
WATCHES = "board: watches the planning files"
CHECKS = "board: no file notifications here; checks every 5 s"
STOPS_IDLE = "board: stops by itself after 30 min with no client (a watcher started it)"
FORGE_WHEN_OBSERVED = (
    "board: the running board reads the forge only while a client is subscribed (a watcher "
    "started it); the pull path gets no forge event until one is"
)
BOTH_FLAGS = (
    "--stop-idle and --forge-always do not go together: a board the pull path relies on for the "
    "forge must not stop by itself; pass one"
)


def files_line(mode: object) -> str | None:
    """The start line of the file watch's mode (`server.json`'s `files`); None for none."""
    return WATCHES if mode == NOTIFY else CHECKS if mode else None


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


def _other_board(host: str, port: int, key: str, served: str) -> str | None:
    """What names another surface's board that holds the port: its served folder, or "another
    project's key"; None for a board of this folder or for anything else."""
    found = probe(host, port, key)
    if isinstance(found, dict):
        other = found.get("served")
        return str(other) if other != served else None
    return "another project's key" if found == "another-key" else None


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
    hub = HubThread(HubLoop(projects.home), stop, observed)
    hub.start()
    git_dir = projects.home.git_dir
    push = PushThread(loop, stop, lambda: state.reassert_server(git_dir, ctx.key.current()))
    push.start()
    idle = IdleThread(IdleStop(loop.observed, stop, time.monotonic())) if args.stop_idle else None
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


def _announce(host: str, bound: int, key: str, served: str, after: list[str]) -> None:
    """The start lines: the link, this machine's link, the exposure, then `after` (the
    `NO_NETWORK` line, the file watch's)."""
    print(f"board on {url(host, bound, key)} over {served}", flush=True)
    if local := local_url(host, bound, key):
        print(f"on this machine: {local}", flush=True)
    if not is_loopback(host):
        print(BEYOND.format(host=host), flush=True)
    for line in after:
        print(line, flush=True)


def _running_lines(
    there: tuple[str, int],
    key: str,
    ui_given: bool,
    entry: dict[str, Any] | None = None,
    forge_always: bool = False,
) -> list[str]:
    """The lines of a board already running: its link, its exposure, its file watch (from its
    `server` entry), what this start could not apply, and last its idle stop."""
    entry = entry or {}
    lines = [f"board already running at {url(*there, key)}"]
    if local := local_url(*there, key):
        lines.append(f"on this machine: {local}")
    if not is_loopback(there[0]):
        lines.append(BEYOND.format(host=there[0]))
    if found := files_line(entry.get("files")):
        lines.append(found)
    if ui_given:
        lines.append(NOT_APPLIED)
    if forge_always and entry.get("forge") != "always":
        lines.append(FORGE_WHEN_OBSERVED)
    if entry.get("stop_idle"):
        lines.append(STOPS_IDLE)
    return lines


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


def _extra(args: argparse.Namespace, files: FileWatchThread) -> dict[str, Any]:
    """The `server` entry's fields beyond the address: the file watch's mode, the idle stop, the
    forge always."""
    extra: dict[str, Any] = {"files": files.mode}
    if args.stop_idle:
        extra["stop_idle"] = int(times.IDLE_STOP_S)
    if args.forge_always:
        extra["forge"] = "always"
    return extra


def _options(args: argparse.Namespace) -> None:
    """The options checked before anything is read: the two flags that do not go together, the
    clock."""
    if args.stop_idle and args.forge_always:
        raise ChantierError(BOTH_FLAGS, EXIT_USAGE)
    if args.clock:
        try:
            clock.fix(args.clock)
        except ValueError as e:
            raise ChantierError(
                f"--clock {args.clock!r}: use YYYY-MM-DDTHH:MM:SSZ", EXIT_USAGE
            ) from e


def _listen(
    args: argparse.Namespace, projects: Projects, host: str, port: int, key: str
) -> socket.socket:
    """The bound socket: a port held refuses, but a default port held by another surface's board
    takes a free one."""
    from_config = args.port is None and "port" in load_board(projects.home)[0]
    served = projects.served.as_posix()
    default = args.port is None and not from_config
    other = (lambda: _other_board(host, port, key, served)) if default else None
    return _bind(host, port, lambda: _held_by(host, port, key, from_config), other)


def board(args: argparse.Namespace) -> list[str]:
    _options(args)
    ui = _ui(args.ui)
    projects = open_projects()
    try:
        check_planning(projects)
    except ChantierError as e:
        raise _not_started(e) from e
    host, port, no_network = settings(projects.home, args.host, args.port)
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
        lines = _running_lines(there, key, args.ui != SHIPPED_UI, run, args.forge_always)
        if (
            run
            and projects.chosen
            and (found := foreign_build_clause(projects.home, __version__, run))
        ):
            lines.append(found)
        return lines
    _writing(lambda: state.check_writable(git_dir))  # a refused write: known before any bind
    sock = _listen(args, projects, host, port, key)
    bound, served = sock.getsockname()[1], projects.served.as_posix()
    ctx = _context(projects, seats, sock, ui)
    files = _watch_files(ctx)  # the mode is known before the start line
    extra = _extra(args, files)
    try:
        _writing(lambda: state.write_server(git_dir, host, bound, __version__, served, **extra))
    except ChantierError:
        files.stop()
        sock.close()
        raise
    _announce(
        host, bound, key, served, [NO_NETWORK] * no_network + [files_line(files.mode) or WATCHES]
    )
    _run(ctx, sock, files, args)
    return []
