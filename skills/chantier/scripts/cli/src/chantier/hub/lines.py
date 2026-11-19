"""The watcher's lines of `status`: the forge hub's, and the watchers of this project."""

from __future__ import annotations

from chantier import __version__
from chantier.board.projects import project_name
from chantier.core.records import BatchRecord
from chantier.core.repo import Repo
from chantier.hub import autostart, journal, lock


def watch_lines(repo: Repo, d: BatchRecord) -> list[str]:
    """With a running batch, the hub's line, then the watcher's: this session's own command when
    it runs, one line per watcher of another session (its end wakes that session, not this
    one). When none of this session runs, `status` ends with `not_running_line`."""
    if d.status != "running":
        return []
    lines = [hub_line(repo)]
    project = project_name(repo)
    if autostart.session_key() in lock.watchers(repo.git_dir, project):
        last = journal.last_seq(journal.read(repo.changes)[0])
        lines.append(f"watch: chantier watch --after {last}")
    lines += [
        f"watch: session {s} runs a watcher too; its end wakes that session, not this one"
        for s in autostart.other_sessions(repo, project)
    ]
    return lines


def hub_line(repo: Repo) -> str:
    """The forge hub of this surface on this machine: its PID and its last read of this project."""
    record = lock.live(repo.git_dir)
    if record is None:
        return "forge hub: none running"
    mine = (record.get("projects") or {}).get((repo.project_dir or repo.root).name) or {}
    line = f"forge hub: PID {record['pid']}, last read {mine.get('read_at') or 'none yet'}"
    if mine.get("error"):
        line += (
            f"; last read failed at {mine.get('error_at') or 'an unknown time'}: {mine['error']}"
        )
    other = lock.other_version(record, __version__)
    return f"{line}; hub is chantier {other}" if other else line
