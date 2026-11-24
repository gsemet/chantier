"""The watcher's lines of `status`: the forge hub's, and the watchers of this project."""

from __future__ import annotations

from typing import Any

from chantier import __version__
from chantier.board.projects import project_name
from chantier.core.records import BatchRecord
from chantier.core.repo import Repo
from chantier.hub import autostart, batch_prs, journal, lock, state
from chantier.launch import is_chantier_project
from chantier.plugin_files import is_dev_checkout


def watch_lines(repo: Repo, d: BatchRecord) -> list[str]:
    """The hub's line (for the batch the hub follows only: running, or paused with open PRs, as
    `batch_prs.followed_batch` tells), then the watcher's: this session's pull command when it
    runs, one line per watcher of another session (its end wakes that session, not this one), the
    board's version when it is not this CLI's. When none of this session runs, `status` ends with
    `not_running_line`."""
    followed = d.status == "running" or (d.status == "paused" and batch_prs.to_read(d))
    lines = [hub_line(repo)] if followed else []
    project = project_name(repo)
    if autostart.session_key() in lock.watchers(repo.git_dir, project):
        last = journal.last_seq(journal.read(repo.store, repo.changes)[0])
        pull = f"pull path: {autostart.pull_command(repo, last)}"
        if why := unsubscribed(repo):
            lines.append(
                f"watch: this session's watcher runs but is not subscribed to the forge hub "
                f"({why}); for the Chief of Staff: stop the stray server if one runs, run serve "
                f"--restart, then start the watcher again; {pull}"
            )
        else:
            lines.append(f"watch: this session's watcher runs; {pull}")
    if (f := foreman_line(repo, d)) is not None:
        lines.append(f)
    lines += [
        f"watch: session {s} runs a watcher too; its end wakes that session, not this one"
        for s in autostart.other_sessions(repo, project)
    ]
    return lines + board_lines(repo)


def unsubscribed(repo: Repo) -> str | None:
    """Why a watcher that runs is not what the forge hub observes, from the record alone: no hub
    runs, the hub sees no subscriber (the watcher is linked to another process), or the recorded
    server is not the hub's process. None when the hub observes."""
    hub = state.live_entry(repo.git_dir, state.HUB)
    if hub is None:
        return "no forge hub runs"
    server = state.live_entry(repo.git_dir, state.SERVER)
    if server is not None and server.get("pid") != hub.get("pid"):
        return f"the recorded server is PID {server.get('pid')}, the hub's is PID {hub.get('pid')}"
    if hub.get("idle"):
        return f"the hub, PID {hub.get('pid')}, sees no subscriber"
    return None


def foreman_line(repo: Repo, d: BatchRecord) -> str | None:
    """In the session of a running or paused batch in Foreman mode that is not the Foreman's
    (the Chief of Staff's): whether the Foreman's session holds a watcher of the project."""
    if d.status not in ("running", "paused") or not d.foreman_transcript:
        return None
    if d.steering == "direct":  # no Foreman's watcher in direct mode
        return None
    foreman = autostart.kept(d.foreman_transcript)
    if not foreman or foreman == autostart.session_key():
        return None
    runs = foreman in lock.watchers(repo.git_dir, project_name(repo))
    return "foreman watch: running" if runs else "foreman watch: not running"


def board_lines(repo: Repo) -> list[str]:
    """One line when the board that serves this surface is live and of another version."""
    found = autostart.board_clause(repo, __version__)
    if not found:
        return [c] if (c := foreign_build_clause(repo)) else []
    return [
        f"board: chantier {found} serves this surface, this is chantier {__version__}: it "
        "serves the watcher as that version; for the Chief of Staff: tell the user once to "
        "restart it"
    ]


def foreign_build_clause(
    repo: Repo, version: str = __version__, record: dict[str, Any] | None = None
) -> str:
    """In the dev mode only: what is said of the live `server` entry (or `record`) of this
    version that runs another build than this checkout's, else nothing. No advice."""
    if not (is_dev_checkout() and is_chantier_project(repo)):
        return ""
    if record is None:
        record = state.live_entry(repo.git_dir, state.SERVER)
    found = state.other_build(record, version, state.build_source())
    if not found:
        return ""
    if found == state.UNKNOWN:
        return (
            f"board runs a build of chantier {version} older than this notice "
            "(source unknown), not this checkout's"
        )
    return f"board runs another build of chantier {version} ({found}), not this checkout's"


def hub_line(repo: Repo) -> str:
    """The forge hub of this surface on this machine (the surface server): its PID, and its last
    read of this project, or `idle` while no client is subscribed to it."""
    record = state.live_entry(repo.git_dir, state.HUB)
    if record is None:
        return "forge hub: none running"
    mine = (record.get("projects") or {}).get((repo.project_dir or repo.root).name) or {}
    read = (
        "idle (no client subscribed)"
        if record.get("idle")
        else f"last read {mine.get('read_at') or 'none yet'}"
    )
    line = f"forge hub: PID {record['pid']}, the surface server, {read}"
    if mine.get("error"):
        line += (
            f"; last read failed at {mine.get('error_at') or 'an unknown time'}: {mine['error']}"
        )
    other = state.other_version(record, __version__)
    return f"{line}; hub is chantier {other}" if other else line
