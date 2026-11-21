"""The repository's Chief of Staff seat (`seat.json`)."""

from __future__ import annotations

import json

from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.files import rel_in
from chantier.core.records import SeatRecord
from chantier.core.repo import Repo


def read_seat(repo: Repo) -> SeatRecord | None:
    store = repo.store
    path = repo.changes / "seat.json"
    rel = rel_in(store.root, path)
    if not store.is_file(rel):
        return None
    try:
        data = json.loads(store.read_text(rel))
    except ValueError as e:
        raise ChantierError(f"{path} is not valid JSON: {e}", EXIT_PRECONDITION) from e
    seat = SeatRecord.model_validate(data)
    return seat if seat.session else None
