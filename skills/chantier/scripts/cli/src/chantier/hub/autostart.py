"""The line that tells the Chief of Staff to start its watcher, and the command it names.

The CLI never starts the watcher: its end must wake the Chief of Staff's session, so it is that
session's background task. A running batch whose session holds no watcher lock gets one line, the
last of the output."""

from __future__ import annotations

import re

from chantier.board.projects import project_name
from chantier.core.errors import ChantierError
from chantier.core.repo import Repo
from chantier.hub import journal, lock, state
from chantier.plugin_files import cli_command, detect_host, own_transcript

NONE = "none"


def session_key() -> str:
    """This session's key for the watcher's lock: the host's session id kept to `[A-Za-z0-9-]`,
    else `none`. The writer (the watcher) and every reader use this one function."""
    try:
        host = detect_host()
    except ChantierError:  # no host known (a bare terminal): no session id either
        return NONE
    return re.sub(r"[^A-Za-z0-9-]", "", own_transcript(host) or "") or NONE


def holds_seat(transcript: str | None) -> bool:
    """The seat's transcript, kept as the watcher's key is, is this CLI run's own key."""
    kept = re.sub(r"[^A-Za-z0-9-]", "", transcript or "")
    return bool(kept) and kept == session_key()


def watch_command(repo: Repo, n: int) -> str:
    return f"{cli_command(repo)} watch --after {n}"


def other_sessions(repo: Repo, project: str) -> list[str]:
    """The sessions other than this one that hold a watcher of the project now."""
    me = session_key()
    return [s for s in lock.watchers(repo.git_dir, project) if s != me]


def board_clause(repo: Repo, version: str) -> str:
    """What the start line and `status` say of a live surface server of another version, else
    nothing."""
    return state.other_version(state.live_entry(repo.git_dir, state.SERVER), version) or ""


def pull_command(repo: Repo, n: int) -> str:
    """The pull path: the journal's lines past `n`, with no process and no forge read."""
    return f"{cli_command(repo)} watch --once --after {n}"


def not_running_line(repo: Repo) -> list[str]:
    """The line for a session whose watcher does not run, whatever the batch's status (a batch
    running, paused or none), else nothing."""
    if session_key() in lock.watchers(repo.git_dir, project_name(repo)):
        return []
    n = journal.last_seq(journal.read(repo.store, repo.changes)[0])
    return [
        "watch: not running: for the Chief of Staff, start in the background: "
        + watch_command(repo, n)
        + "; after the user's no, at each user message: "
        + pull_command(repo, n)
    ]
