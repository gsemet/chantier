"""The board's seats: the Chief of Staff sessions it serves, and when it stops."""

from __future__ import annotations

import threading
from collections.abc import Callable

from chantier.board.projects import Projects
from chantier.core.errors import ChantierError
from chantier.core.seat import read_seat

SEAT_CHECK_S = 10  # the board looks at its seats at least this often, and at each request


class Seats:
    """The pairs (project, session) that registered. A board with none stops on Ctrl-C only; one
    that had some stops when none of them is still named by its project's `seat.json`."""

    def __init__(self, projects: Projects) -> None:
        self._projects = projects
        self._seats: set[tuple[str, str]] = set()
        self._lock = threading.Lock()
        self._stop: Callable[[], None] | None = None
        self._watching = False

    def add(self, project_id: str, session: str) -> bool:
        """Register a seat; False for a project the board does not serve."""
        if self._projects.get(project_id) is None or not session:
            return False
        with self._lock:
            self._seats.add((project_id, session))
        self._start()
        return True

    def arm(self, stop: Callable[[], None]) -> None:
        """Say how to stop the board; the watch starts with the first seat, whenever it comes."""
        self._stop = stop
        if self.count():
            self._start()

    def _start(self) -> None:
        with self._lock:
            if self._stop is None or self._watching:
                return
            self._watching = True
        threading.Thread(target=self._loop, args=(self._stop,), daemon=True).start()

    def _loop(self, stop: Callable[[], None]) -> None:
        """Look at the seats every `SEAT_CHECK_S` seconds and stop the board."""
        while not threading.Event().wait(SEAT_CHECK_S):
            if self.gone():
                stop()
                return

    def count(self) -> int:
        with self._lock:
            return len(self._seats)

    def _held(self, project_id: str, session: str) -> bool:
        """The seat file still names the session; an unreadable file counts as held."""
        project = self._projects.get(project_id)
        if project is None:
            return False
        try:
            seat = read_seat(project.repo)
        except (ChantierError, OSError):
            return True
        return bool(seat and seat.session == session)

    def gone(self) -> bool:
        """Seats were registered and none is held any more."""
        with self._lock:
            seats = sorted(self._seats)
        return bool(seats) and not any(self._held(p, s) for p, s in seats)
