"""The PRs page for a batch other than the one in `4-batch/`: `?batch=<id>`, a closed batch read
once from its record, no batch running, an unknown id, and the forge read kept per batch shown.
No test reaches a forge (`Board` replaces the one seam)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import changes, record
from conftest import Chantier
from test_board_prs import FIRST, HTTP_OK, LINK, TWO_CALLS, Board, served

from chantier.board.context import Request
from chantier.board.routes import handle

ROW_COUNT = 4
CLOSED = "batch-3"
CRS: list[dict[str, Any]] = [
    {"cr": "CR-7", "title": "Seven", "result": "merged", "pr": LINK.format(70), "order": 1},
    {"cr": "CR-5", "title": "Five", "result": "cancelled", "pr": LINK.format(71), "order": 0},
    {"cr": "CR-9", "title": "No PR", "result": "merged"},
]


@pytest.fixture
def board(repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch) -> Board:
    return served(repo, chantier, monkeypatch)


def archive(repo: Path, number: int, crs: list[dict[str, Any]] | None = None) -> None:
    """A closed batch's record, as `5-archives/batches/` keeps it."""
    folder = changes(repo) / "5-archives" / "batches"
    folder.mkdir(parents=True, exist_ok=True)
    data = {"batch": f"batch-{number}", "state": "closed", "crs": CRS if crs is None else crs}
    (folder / f"batch-{number}.json").write_text(json.dumps(data), encoding="utf-8")


def ask(b: Board, batch: str | None = None) -> dict[str, Any]:
    query = {"batch": batch} if batch else {}
    path = f"/api/projects/{b.id}/prs"
    reply = handle(b.ctx, Request("GET", path, query, {"x-chantier-board-key": b.key}))
    assert reply.status == HTTP_OK
    body: dict[str, Any] = json.loads(reply.body or b"{}")
    return body


def test_a_closed_batch_answers_its_record_in_its_order_and_signals_nothing(board: Board) -> None:
    archive(board.repo, 3)
    board.forge = {71: {"state": "merged", "base": "main", "merged_at": "2026-11-01T00:00:00Z"}}
    before = board.planning()
    got = ask(board, CLOSED)
    assert (got["batch"], got["closed"], got["paused"]) == (CLOSED, True, False)
    assert [r["cr"] for r in got["rows"]] == ["CR-5", "CR-7"]
    for r in got["rows"]:
        assert (r["ready_now"], r["why"], r["disagrees"], r["kind"]) == (False, None, None, None)
    assert got["rows"][0]["merged_into"] == {"branch": "main", "cr": None}
    assert board.planning() == before
    assert not (changes(board.repo) / "forge-journal.jsonl").exists()


@pytest.mark.parametrize("asked", [None, "running"])
def test_no_batch_or_the_running_one_is_todays_answer(board: Board, asked: str | None) -> None:
    archive(board.repo, 3)
    got = ask(board, record(board.repo)["id"] if asked else None)
    assert (got["batch"], got["closed"]) == (record(board.repo)["id"], False)
    assert len(got["rows"]) == ROW_COUNT and "last_batch" not in got


def test_with_no_batch_running_the_newest_closed_one_is_shown_read_once(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert chantier("file", "Something")[0] == 0
    archive(repo, 2, [CRS[0]])
    archive(repo, 3)
    b = Board(repo, [], monkeypatch)
    got = ask(b)
    assert (got["batch"], got["closed"], len(got["rows"])) == (CLOSED, True, 2)
    assert len(b.calls) == 1


@pytest.mark.parametrize(("asked", "error"), [(None, None), ("batch-9", "unknown batch batch-9")])
def test_no_history_or_an_unknown_id_is_the_no_batch_shape_with_no_forge_call(
    board: Board, asked: str | None, error: str | None
) -> None:
    (changes(board.repo) / "4-batch" / "batch.json").unlink()
    got = ask(board, asked)
    assert (got["batch"], got["rows"], got["error"], got["closed"]) == (None, [], error, False)
    assert board.calls == []


def test_two_batches_read_in_turn_each_call_the_forge_once_within_ten_seconds(board: Board) -> None:
    archive(board.repo, 3)
    for batch in (None, CLOSED, None, CLOSED):
        board.now += 1.0
        ask(board, batch)
    assert len(board.calls) == TWO_CALLS


def test_a_row_carries_the_dates_the_forge_gave(board: Board) -> None:
    board.forge = {
        FIRST: {"opened_at": "2026-11-01T00:00:00Z", "updated_at": "2026-11-02T00:00:00Z"}
    }
    rows = ask(board)["rows"]
    assert (rows[0]["opened_at"], rows[0]["updated_at"]) == (
        "2026-11-01T00:00:00Z",
        "2026-11-02T00:00:00Z",
    )
    assert (rows[1]["opened_at"], rows[1]["updated_at"]) == (None, None)
