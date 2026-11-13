"""`chantier gate`: the long gate, run alone in the repository."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chantier import procs
from chantier.commands.crs import batch_cr, cr_worktree, dirty_files, short_head, work
from chantier.commands.gate_lock import LongGateLock, lock_holder
from chantier.commands.registry import BATCH, Subparsers, add_command
from chantier.core.errors import EXIT_EXTERNAL, EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.git import git
from chantier.core.records import RunRecord
from chantier.core.repo import Repo
from chantier.lifecycle.convert import open_repo
from chantier.lifecycle.session import RenderedBatch


# The run file `.long-gate.run` (planning folder, ignored like the lock) tells a `gate <cr> --stop`
# what the running gate is (run id, head, command, log, suite group) and tells the running gate it
# was stopped. The ask is a separate marker, `.long-gate.stop`, that the stopper creates and the
# gate never rewrites (the gate removes it when it starts and ends), so no write of the run file
# can lose it: the gate checks it before and right after each start, and after each wait, and
# then records `stopped`, never `fail`.
def _run_file(repo: Repo) -> Path:
    return repo.changes / ".long-gate.run"


def _stop_file(repo: Repo) -> Path:
    return repo.changes / ".long-gate.stop"


def _stop_asked(repo: Repo) -> bool:
    return _stop_file(repo).exists()


def _run_read(repo: Repo) -> RunRecord | None:
    for _ in range(5):  # the other side may be writing it
        try:
            return RunRecord.model_validate_json(_run_file(repo).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            time.sleep(0.05)
    return None


REPLACE_TRIES = 5


def _run_write(repo: Repo, record: RunRecord) -> None:
    tmp = _run_file(repo).with_name(".long-gate.run.tmp")
    tmp.write_text(json.dumps(record.to_data()), encoding="utf-8")
    for i in range(REPLACE_TRIES):  # atomic: the stopper never reads half a file
        try:
            os.replace(tmp, _run_file(repo))
            return
        except PermissionError:  # Windows: a reader holds the file
            if i == REPLACE_TRIES - 1:
                raise
            time.sleep(0.05)


def _gate_stop(args: argparse.Namespace, repo: Repo, batch: str, wt: Path) -> tuple[list[str], int]:
    """`gate <cr> --stop`: stop this CR's running long gate (its suite, the lock) and record the
    run `stopped`: no pass, no failure. Nothing else of the CR changes."""
    holder = lock_holder(repo)
    m = re.fullmatch(r"(\S+) pid (\d+)(?: pg(\d+))?", holder)
    if not m:
        return [f"no long gate running for {args.cr}: nothing to stop"], 0
    if m[1] != args.cr:
        return [f"the long gate running is {m[1]}'s: not stopped"], EXIT_PRECONDITION
    run = _run_read(repo)
    head = (run.head if run else "") or git("rev-parse", "HEAD", cwd=wt)
    pg = int(m[3]) if m[3] else None
    gate_alive = procs.alive(int(m[2]))
    if gate_alive:
        _stop_file(repo).write_text("stop", encoding="utf-8")  # the running gate records it
    if pg is not None:
        procs.stop_group(pg)
    if not gate_alive:  # the gate is gone: the stopper records the run
        if run and run.log and Path(run.log).exists():
            with open(run.log, "a", encoding="utf-8") as f:
                f.write(f"result: stopped at {head}: no pass\n")
        if run is not None:  # with no run record there is no run to record: the lock was stale
            with RenderedBatch(repo, batch, actor="driver") as b:
                b.log(
                    "gate",
                    args.cr,
                    result="stopped",
                    head=head,
                    command=run.command,
                    run=run.run,
                )
        _run_file(repo).unlink(missing_ok=True)
    where = f" (pg{pg})" if pg is not None else ""
    return [f"stopped the long gate of {args.cr} at {short_head(head)}{where}"], 0


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
        group: dict[str, Any] = (
            {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
            if sys.platform == "win32"
            else {"start_new_session": True}
        )
        return subprocess.Popen(
            cmd, shell=True, cwd=g.wt, stdout=f, stderr=subprocess.STDOUT, **group
        )


def _run_commands(
    g: _Gate, cmds: list[str], lock: LongGateLock
) -> tuple[list[tuple[str, int]], str]:
    """Run the commands in order until one fails or a stop is asked: what ran, and the command
    that was running when a `--stop` came (empty if none)."""
    ran: list[tuple[str, int]] = []
    for cmd in cmds:
        if _stop_asked(g.repo):  # stopped between two commands: none starts
            # the record names the previous command (the one that last ran), or the first
            return ran, ran[-1][0] if ran else cmd
        p = _spawn(cmd, g)
        lock.holding(f"{g.cr} pid {os.getpid()} pg{p.pid}")
        _run_write(g.repo, g.record(command=cmd, pg=p.pid))
        if _stop_asked(g.repo):  # asked before the stopper could see this group: stop it here
            procs.stop_group(p.pid)
        rc = p.wait()
        if _stop_asked(g.repo):  # stopped: no pass, and no failure of the code
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
    """The long gate: the command the project's rules name, run in the CR's worktree, alone in
    the repository (a second one waits), logged in the work folder, recorded with its head.
    `--stop` stops this CR's running gate (its suite and the lock): recorded `stopped`, no pass,
    no failure; the stopped gate exits 4; nothing else of the CR changes."""
    repo = open_repo()
    batch, _, c = batch_cr(repo, args.cr, args.batch)
    wt = cr_worktree(c)
    cmds = _commands(args)
    if args.stop:
        return _gate_stop(args, repo, batch, wt)
    if dirty_files(wt):  # a gate binds to a commit: nothing runs, nothing is logged
        raise ChantierError(
            f"{c['id']}: the worktree has uncommitted changes or untracked files: "
            "a gate binds to a commit, commit first",
            EXIT_PRECONDITION,
        )
    start = git("rev-parse", "HEAD", cwd=wt)  # the full SHA, before the first command
    logdir = work(repo, c) / "gates"
    logdir.mkdir(parents=True, exist_ok=True)
    stamped = time.strftime("%Y%m%d-%H%M%S")
    log = logdir / f"{stamped}.log"
    # the events of this invocation share the run id
    g = _Gate(repo, args.cr, batch, wt, log, f"{stamped}-{os.getpid()}", start)
    g.note(f"gate {c['id']} branch {c['branch']} head {start}\n")  # before any waiting note
    with LongGateLock(repo, args.cr, log) as lock:
        _stop_file(repo).unlink(missing_ok=True)  # a stale ask is not this gate's
        _run_write(repo, g.record(command=""))
        ran, stopped = _run_commands(g, cmds, lock)
        _run_file(repo).unlink(missing_ok=True)
        _stop_file(repo).unlink(missing_ok=True)
    return _finish_stopped(g, ran, stopped) if stopped else _finish(g, ran)


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "gate",
        gate,
        "run the long gate in the CR worktree, alone in the repository, "
        "a second one waits its turn, first come first served; --stop stops this CR's running one",
        BATCH,
    )
    s.add_argument("cr")
    s.add_argument(
        "command",
        nargs="*",
        help="the long gate's commands, from the project's rules: "
        "one per argument, never chained with ; or &&; they stop at the first failure",
    )
    s.add_argument(
        "--stop",
        action="store_true",
        help="stop this CR's running long gate: its suite, the gate lock; recorded "
        "`stopped`, no pass; nothing else changes",
    )
