"""The board's data for typed waits: `open_waits` on a batch row and on a backlog item, with the
older `waits` field (what a queued CR waits for) unchanged."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_world import World, crs_of, write_batch

from chantier.board.backlog import backlog_items
from chantier.board.crs import cr_rows
from chantier.core import waits
from chantier.core.batch import read_batch
from chantier.store import FolderStore

LINK = "https://github.com/acme/alpha/pull/10"


def _w(wait_id: str, cleared: bool = False) -> dict[str, Any]:
    return waits.make(wait_id, "merge", LINK, LINK, "n") | (
        {"cleared_at": "t", "cleared_by": "hand"} if cleared else {}
    )


def test_a_batch_row_carries_the_open_waits_of_a_counted_cr_and_keeps_its_waits_field(
    world: World,
) -> None:
    crs = crs_of("alpha", "blocked", 3)
    crs[0]["waits"] = [_w("w1", cleared=True), _w("w2")]
    crs[1]["status"] = "queued"
    crs[2].update(status="cancelled", waits=[_w("w1")])
    write_batch(world.project("alpha"), "running", crs)
    repo = world.repo("alpha")
    rows = cr_rows(repo, read_batch(repo, "batch-01"), [])
    assert [[w["id"] for w in r["open_waits"]] for r in rows] == [["w2"], [], []]
    assert all(isinstance(r["waits"], list) for r in rows)  # the older field, untouched


def test_a_backlog_item_carries_the_open_waits_of_its_file(tmp_path: Path) -> None:
    folder = tmp_path / "1-inbox" / "a"
    folder.mkdir(parents=True)
    (folder / "01-intent.md").write_text("# A\n", encoding="utf-8")
    (folder / waits.FILE).write_text(waits.file_text([_w("w1", True), _w("w2")]), encoding="utf-8")
    row = {"item": "a", "title": "A", "path": "1-inbox/a", "priority": "inbox"}
    (item,) = backlog_items(FolderStore(tmp_path), tmp_path, [row])["inbox"]
    assert [w["id"] for w in item["open_waits"]] == ["w2"]
