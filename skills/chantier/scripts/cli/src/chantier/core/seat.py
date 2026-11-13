"""The repository's Chief of Staff seat (`seat.json`)."""

from __future__ import annotations

import json

from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.files import read_text
from chantier.core.records import SeatRecord
from chantier.core.repo import Repo


def read_seat(repo: Repo) -> SeatRecord | None:
    path = repo.changes / "seat.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(read_text(path))
    except ValueError as e:
        raise ChantierError(f"{path} is not valid JSON: {e}", EXIT_PRECONDITION) from e
    seat = SeatRecord.model_validate(data)
    return seat if seat.session else None
