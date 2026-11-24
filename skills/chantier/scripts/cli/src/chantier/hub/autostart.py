"""The line that tells the Chief of Staff to start its watcher, and the command it names.

The CLI never starts the watcher: each block it tells (streaming) or its end must wake the Chief of
Staff's session, so it is that session's background task. A running batch whose session holds no
watcher lock gets one line, the last of the output."""

from __future__ import annotations

import json
import os
import re

from chantier.board.projects import project_name
from chantier.core.errors import ChantierError
from chantier.core.remote_wire import VIA_SERVER
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


DEV_PROJECT = "chantier"  # the project folder of chantier's own project in a planning surface


def dev_build(repo: Repo) -> tuple[str, str] | None:
    """The chantier dev session that holds its seat on this planning surface now, as (its session,
    its build): the surface's `chantier` project's `seat.json` names a session and a `build`, and
    that session's watcher lock is held now (a seat an ended session left behind claims nothing).
    None off a planning surface, and with no such seat."""
    if not repo.external:
        return None
    try:
        data = json.loads(
            (repo.surface_root / "projects" / DEV_PROJECT / "changes" / "seat.json").read_text(
                encoding="utf-8"
            )
        )
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    session, build = data.get("session"), data.get("build")
    transcript = re.sub(r"[^A-Za-z0-9-]", "", str(data.get("transcript") or ""))
    if not (isinstance(session, str) and session and isinstance(build, str) and build):
        return None
    if not transcript or transcript not in lock.watchers(repo.git_dir, DEV_PROJECT):
        return None
    return session, build


def other_dev_build(repo: Repo, own: str) -> tuple[str, str] | None:
    """`dev_build` when its build is not `own` (this process's `state.build_source()`): the guard
    that keeps another build from serving a surface a chantier dev session holds."""
    found = dev_build(repo)
    return found if found is not None and found[1] != own else None


STREAM_HOSTS = frozenset({"claude"})  # the hosts whose reference runs the watcher streaming


def watch_command(repo: Repo, n: int) -> str:
    """The watcher's command from cursor `n`: streaming (`--stream`) on a host whose reference
    runs it so (Claude Code, through `Monitor`), the plain form on Copilot and with no host."""
    try:
        stream = detect_host() in STREAM_HOSTS
    except ChantierError:  # no host known (a bare terminal): the plain form
        stream = False
    return f"{cli_command(repo)} watch --after {n}" + (" --stream" if stream else "")


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
    running, paused or none), else nothing. A command that runs for a client of the surface
    server (`CHANTIER_VIA_SERVER`) prints none: this machine's watcher says nothing of that
    client's Chief of Staff."""
    if os.environ.get(VIA_SERVER):
        return []
    if session_key() in lock.watchers(repo.git_dir, project_name(repo)):
        return []
    n = journal.last_seq(journal.read(repo.store, repo.changes)[0])
    return [
        "watch: not running: for the Chief of Staff, start in the background: "
        + watch_command(repo, n)
        + "; after the user's no, at each user message: "
        + pull_command(repo, n)
    ]
