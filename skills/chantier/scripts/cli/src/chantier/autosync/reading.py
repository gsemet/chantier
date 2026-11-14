"""Reading the group live: the files, the processes, and the sessions that name a participant
(the seat's Chief of Staff and the batch's Foreman, from the projects given)."""

from __future__ import annotations

from collections.abc import Iterable

from chantier.autosync.records import read_group
from chantier.autosync.site import AutosyncSite
from chantier.autosync.view import AutosyncView, Names, classify
from chantier.core.errors import ChantierError
from chantier.core.records import read_batch_json
from chantier.core.repo import Repo
from chantier.core.seat import read_seat
from chantier.procs import alive


def _sessions(repo: Repo) -> tuple[set[str], set[str]]:
    """(seat sessions, foreman sessions) of one project; an unreadable record names nobody."""
    chief: set[str] = set()
    foreman: set[str] = set()
    try:
        seat = read_seat(repo)
        if seat and seat.session:
            chief.add(seat.session)
        for folder in repo.batch_folders():
            batch = read_batch_json(folder / "batch.json")
            if batch.foreman:
                foreman.add(batch.foreman)
    except (ChantierError, OSError):
        pass
    return chief, foreman


def names_of(repos: Iterable[Repo], server_pid: int | None = None) -> Names:
    chief: set[str] = set()
    foreman: set[str] = set()
    for repo in repos:
        seats, foremen = _sessions(repo)
        chief |= seats
        foreman |= foremen
    return Names(server_pid, frozenset(chief), frozenset(foreman))


def read_view(site: AutosyncSite, names: Names | None = None) -> AutosyncView:
    """The group now: its files read, its participants' processes checked. Writes nothing."""
    return classify(read_group(site.state_dir), alive, names)
