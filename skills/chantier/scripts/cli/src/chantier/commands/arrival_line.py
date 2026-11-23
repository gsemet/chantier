"""The arrivals no watcher told, for the commands that start a session's reading (`seat`, `status`):
the `arrived@1` lines past the told mark (`arrivals-told.json`), printed only when no watcher of
the project runs, after which the mark moves, so a line is told once."""

from __future__ import annotations

from chantier.board.projects import project_name
from chantier.core.repo import Repo
from chantier.hub import arrival_mark, journal, lock
from chantier.hub.autostart import not_running_line
from chantier.plugin_files import cli_command


def arrival_lines(repo: Repo) -> list[str]:
    """The untold arrivals, none while a watcher of the project runs (it tells them at its end).
    `seat` and `status` print in full (`cli.FULL_OUTPUT`): the cut drops no line marked told."""
    if lock.watchers(repo.git_dir, project_name(repo)):
        return []
    entries = journal.read(repo.store, repo.changes)[0]
    out, mark = arrival_mark.arrival_lines(entries, arrival_mark.told_mark(repo), cli_command(repo))
    if mark:
        arrival_mark.move_told_mark(repo, mark)
    return out


def closing_lines(repo: Repo) -> list[str]:
    """What `status` ends with: the untold arrivals (the one write of `status`, the told mark of
    the lines listed), then the `watch: not running` line."""
    return arrival_lines(repo) + not_running_line(repo)
