"""The line that tells the Chief of Staff to start its watcher, and the command it names.

The CLI never starts the watcher: its end must wake the Chief of Staff's session, so it is that
session's background task. A running batch whose session holds no watcher lock gets one line, the
last of the output."""

from __future__ import annotations

import re

from chantier.board.projects import project_name
from chantier.core.errors import ChantierError
from chantier.core.repo import Repo
from chantier.hub import journal, lock
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


def watch_command(repo: Repo, n: int) -> str:
    return f"{cli_command(repo)} watch --after {n}"


def other_sessions(repo: Repo, project: str) -> list[str]:
    """The sessions other than this one that hold a watcher of the project now."""
    me = session_key()
    return [s for s in lock.watchers(repo.git_dir, project) if s != me]


def not_running_line(repo: Repo, status: str) -> list[str]:
    """The line for a running batch when no watcher of this session runs, else nothing."""
    if status != "running" or session_key() in lock.watchers(repo.git_dir, project_name(repo)):
        return []
    n = journal.last_seq(journal.read(repo.changes)[0])
    return [
        "watch: not running: for the Chief of Staff, start in the background: "
        + watch_command(repo, n)
    ]
