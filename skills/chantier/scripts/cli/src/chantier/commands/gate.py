"""`chantier gate`: the long gate, as many at once as the project allows."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chantier import procs
from chantier.commands.crs import batch_cr, cr_worktree, dirty_files, short_head, work
from chantier.commands.gate_lock import LongGateLock
from chantier.commands.gate_queue import move_first
from chantier.commands.gate_run import run_write, stop_asked, stop_gate
from chantier.commands.gate_slots import Slot, running_crs, slot_of
from chantier.core.batch import check_epoch
from chantier.core.errors import EXIT_EXTERNAL, EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.git import git
from chantier.core.records import RunRecord
from chantier.core.repo import Repo
from chantier.lifecycle.convert import open_repo
from chantier.lifecycle.session import RenderedBatch
from chantier.playbook.config import FILE, load_long_gate


def _gate_stop(args: argparse.Namespace, repo: Repo, batch: str, wt: Path) -> tuple[list[str], int]:
    """`gate <cr> --stop`: stop this CR's running long gate (its suite, its slot's lock) and
    record the run `stopped`: no pass, no failure. Nothing else of the CR changes, and no other
    slot is touched."""
    v = slot_of(repo, args.cr)
    if v is None or v.holder is None:
        running = running_crs(repo)
        if not running:
            return [f"no long gate running for {args.cr}: nothing to stop"], 0
        return [
            f"no long gate of {args.cr} running (running: {', '.join(running)}): not stopped"
        ], EXIT_PRECONDITION
    with RenderedBatch(repo, batch, actor="driver") as b:
        s = stop_gate(v.slot, v.holder, b, git("rev-parse", "HEAD", cwd=wt))
    where = f" (pg{s.pg})" if s.pg is not None else ""
    return [f"stopped the long gate of {args.cr} at {short_head(s.head)}{where}"], 0


def _gate_first(args: argparse.Namespace, repo: Repo, batch: str) -> tuple[list[str], int]:
    """`gate <cr> --first --epoch <n>`: the steering session puts the CR's waiting long gate at
    the head of the queue. It orders the queue only: a running gate is not touched."""
    if args.stop or args.command:
        raise ChantierError(f"gate {args.cr} --first takes no command and no --stop", EXIT_USAGE)
    if args.epoch is None:
        raise ChantierError(
            f"gate {args.cr} --first --epoch <n>: the steering session's command to put a "
            "critical-path CR's long gate first; a Driver never moves its own gate",
            EXIT_PRECONDITION,
        )
    with RenderedBatch(repo, batch, actor="foreman") as b:
        check_epoch(b, args.epoch)
        ahead = move_first(repo, args.cr)
        if ahead is None:
            return [f"no long gate of {args.cr} waiting: nothing to move"], 0
        b.log("gate-first", args.cr)
    where = f"ahead of: {', '.join(ahead)}" if ahead else "it was first"
    return [f"moved the long gate of {args.cr} to the head of the queue ({where})"], 0


def _parallel(repo: Repo) -> int:
    """How many long gates may run at once, from the project's `chantier.yaml`, read at each run."""
    parallel, problems = load_long_gate(repo.root / FILE)
    if problems:
        raise ChantierError(problems[0])
    return parallel


@dataclass
class _Gate:
    """One run of the long gate: where it runs, what it binds to, where it logs."""

    repo: Repo
    cr: str
    batch: str
    wt: Path
    log: Path
    run: str
    start: str  # the full SHA, before the first command

    def note(self, text: str) -> None:
        with open(self.log, "a", encoding="utf-8") as f:
            f.write(text)

    def record(self, **fields: Any) -> RunRecord:
        return RunRecord(cr=self.cr, run=self.run, head=self.start, log=str(self.log), **fields)


def _spawn(cmd: str, g: _Gate) -> subprocess.Popen[bytes]:
    """Start one command in its own process group, its output in the log. The log is closed
    while the gate runs: a `cancel` must be able to move the CR's folder on Windows."""
    with open(g.log, "a", encoding="utf-8") as f:
        f.write(f"$ {cmd}\n")
        f.flush()
        group: dict[str, Any]
        if sys.platform == "win32":
            group = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        else:
            group = {"start_new_session": True}
        return subprocess.Popen(
            cmd, shell=True, cwd=g.wt, stdout=f, stderr=subprocess.STDOUT, **group
        )


def _run_commands(
    g: _Gate, cmds: list[str], lock: LongGateLock
) -> tuple[list[tuple[str, int]], str]:
    """Run the commands in order until one fails or a stop is asked: what ran, and the command
    that was running when a `--stop` came (empty if none)."""
    ran: list[tuple[str, int]] = []
    s: Slot = lock.slot  # the slot this gate took: its run file, its stop marker
    for cmd in cmds:
        if stop_asked(s):  # stopped between two commands: none starts
            # the record names the previous command (the one that last ran), or the first
            return ran, ran[-1][0] if ran else cmd
        p = _spawn(cmd, g)
        lock.holding(f"{g.cr} pid {os.getpid()} pg{p.pid}")
        run_write(s, g.record(command=cmd, pg=p.pid))
        if stop_asked(s):  # asked before the stopper could see this group: stop it here
            procs.stop_group(p.pid)
        rc = p.wait()
        if stop_asked(s):  # stopped: no pass, and no failure of the code
            return ran, cmd
        ran.append((cmd, rc))
        if rc:
            break  # the commands after a failure are not run
    return ran, ""


def _finish_stopped(g: _Gate, ran: list[tuple[str, int]], stopped: str) -> tuple[list[str], int]:
    if g.log.exists():
        g.note(f"result: stopped at {g.start}: no pass\n")
    with RenderedBatch(g.repo, g.batch, actor="driver") as b:
        for cmd, rc in ran:
            b.log(
                "gate",
                g.cr,
                result=("fail" if rc else "pass"),
                head=g.start,
                command=cmd,
                run=g.run,
            )
        b.log("gate", g.cr, result="stopped", head=g.start, command=stopped, run=g.run)
    return [f"STOPPED {stopped} at {short_head(g.start)}: no pass", f"log {g.log}"], EXIT_EXTERNAL


def _verdict_text(g: _Gate, ran: list[tuple[str, int]], end: str) -> str:
    failed = ran[-1][1]
    moved = end != g.start
    if failed:
        result = f"FAIL {ran[-1][0]} (exit {failed}) at {short_head(g.start)}"
    elif moved:
        result = f"head moved during the run, from {g.start} to {end}: no pass at either head"
    else:
        result = f"pass at {g.start}"
    if moved and failed:
        result += f"; head moved from {g.start} to {end}"
    return result


def _log_results(g: _Gate, ran: list[tuple[str, int]], end: str) -> None:
    moved = end != g.start
    with RenderedBatch(g.repo, g.batch, actor="driver") as b:
        for cmd, rc in ran:
            result = "fail" if rc else "moved" if moved else "pass"
            b.log("gate", g.cr, result=result, head=g.start, command=cmd, run=g.run)
        if moved:
            b.log("gate", g.cr, result="moved", head=end, command=ran[-1][0], run=g.run)


def _finish(g: _Gate, ran: list[tuple[str, int]]) -> tuple[list[str], int]:
    end = git("rev-parse", "HEAD", cwd=g.wt)
    moved = end != g.start  # a gate command committed: the run is no pass at either head
    failed = ran[-1][1]
    if g.log.exists():  # a `cancel` moves the CR's folder, log and all, while the gate runs
        g.note(f"result: {_verdict_text(g, ran, end)}\n")  # the log's last line
    _log_results(g, ran, end)
    lines = [
        f"{'pass' if rc == 0 and not moved else 'FAIL'} {cmd}"
        f"{'' if rc == 0 else f' (exit {rc})'} at {short_head(g.start)}"
        for cmd, rc in ran
    ]
    if moved:
        lines.append(
            f"head moved during the gate, from {short_head(g.start)} to {short_head(end)}: "
            "no pass at either head"
        )
    if failed or moved:
        # gates write in the console's code page: never fail on their bytes
        tail = (
            g.log.read_text(encoding="utf-8", errors="replace").splitlines()[-8:]
            if g.log.exists()
            else []
        )
        return [*lines, f"log {g.log}", *tail], EXIT_EXTERNAL
    return [*lines, f"log {g.log}"], 0


def _commands(args: argparse.Namespace) -> list[str]:
    cmds = [x.strip() for x in args.command]
    if args.stop and cmds:
        raise ChantierError(f"gate {args.cr} --stop takes no command", EXIT_USAGE)
    if not args.stop and (not cmds or not all(cmds)):
        raise ChantierError(
            'gate <cr> "<command>" ["<command>"...]: the long gate\'s commands '
            "from the project's rules, one per argument",
            EXIT_USAGE,
        )
    return cmds


def gate(args: argparse.Namespace) -> tuple[list[str], int]:
    """The long gate: the command the project's rules name, run in the CR's worktree, as many at
    once as `chantier.yaml` allows (the others wait), logged in the work folder, recorded with its
    head. `--first` (the steering session's) moves a waiting gate to the head of the queue.
    `--stop` stops this CR's running gate (its suite and the lock): recorded `stopped`, no pass,
    no failure; the stopped gate exits 4; nothing else of the CR changes."""
    repo = open_repo()
    batch, _, c = batch_cr(repo, args.cr, args.batch)
    wt = cr_worktree(c)
    if args.first:
        return _gate_first(args, repo, batch)
    cmds = _commands(args)
    if args.stop:
        return _gate_stop(args, repo, batch, wt)
    if dirty_files(wt):  # a gate binds to a commit: nothing runs, nothing is logged
        raise ChantierError(
            f"{c.id}: the worktree has uncommitted changes or untracked files: "
            "a gate binds to a commit, commit first",
            EXIT_PRECONDITION,
        )
    parallel = _parallel(repo)  # an invalid key: nothing runs, nothing is logged
    start = git("rev-parse", "HEAD", cwd=wt)  # the full SHA, before the first command
    logdir = work(repo, c) / "gates"
    logdir.mkdir(parents=True, exist_ok=True)
    stamped = time.strftime("%Y%m%d-%H%M%S")
    log = logdir / f"{stamped}.log"
    # the events of this invocation share the run id
    g = _Gate(repo, args.cr, batch, wt, log, f"{stamped}-{os.getpid()}", start)
    g.note(f"gate {c.id} branch {c.branch} head {start}\n")  # before any waiting note
    with LongGateLock(repo, args.cr, log, parallel) as lock:
        lock.slot.stop.unlink(missing_ok=True)  # a stale ask is not this gate's
        run_write(lock.slot, g.record(command=""))
        ran, stopped = _run_commands(g, cmds, lock)
        lock.slot.run.unlink(missing_ok=True)
        lock.slot.stop.unlink(missing_ok=True)
    return _finish_stopped(g, ran, stopped) if stopped else _finish(g, ran)
