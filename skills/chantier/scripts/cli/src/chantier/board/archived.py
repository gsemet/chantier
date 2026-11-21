"""What a batch closed before `close` kept each CR's `order` and `after` still gives: the
`depends.json` its archived CR folders hold. Reads only."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from chantier.board.backlog import depends_of
from chantier.core.files import rel_in

if TYPE_CHECKING:
    from chantier.store import PlanStore

_SLUG = re.compile(r"^\d{6}-\d{4}-\d+-(.+)$")  # <YYMMDD-HHMM>-<number>-<slug>


def _slug_of(archive: str | None) -> str | None:
    name = (archive or "").rstrip("/").rsplit("/", 1)[-1]
    found = _SLUG.match(name)
    return found[1] if found else None


def recovered_after(store: PlanStore, changes: Path, record: dict[str, Any]) -> dict[str, Any]:
    """A closed record with each CR's `after` and the record's `after_source`: "record" (the
    CRs carry `after`: untouched), "archives" (read from at least one archived folder) or
    "none" (no folder could be read)."""
    crs = record.get("crs") or []
    if any("after" in c for c in crs):
        return {**record, "after_source": "record"}
    ids = {c.get("cr") for c in crs}
    by_slug = {s: c["cr"] for c in crs if (s := _slug_of(c.get("archive")))}
    read = False
    out = []
    for c in crs:
        archive = c.get("archive")
        folder = changes / archive if archive else None
        names: list[str] = []
        if folder is not None and store.is_dir(rel_in(store.root, folder)):
            read = True
            names = depends_of(store, folder)
        found = [n if n in ids else by_slug.get(n) for n in names]
        after = list(dict.fromkeys(x for x in found if x and x != c.get("cr")))
        out.append({**c, "after": after})
    return {**record, "crs": out, "after_source": "archives" if read else "none"}
