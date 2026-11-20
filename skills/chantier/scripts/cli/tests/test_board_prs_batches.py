"""The PRs page for a batch other than the one in `4-batch/`: `?batch=<id>`, a closed batch read
once from its record, no batch running, an unknown id, and the forge read kept per batch shown.
No test reaches a forge (`Board` replaces the one seam)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from api_client import call_route
from batch_helpers import changes, record, write_record
from conftest import Chantier
from test_board_prs import FIRST, HTTP_OK, LINK, MERGED_AT, TWO_CALLS, Board, seen_lines, served

from chantier.hub import journal as hub_journal

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
    status, body = call_route(b.ctx, b.key, "GET", b.id, "prs", {"batch": batch} if batch else {})
    assert status == HTTP_OK
    answer: dict[str, Any] = body
    return answer


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


@pytest.mark.parametrize("written", ["Change Specification: X", "CHANGE SPECIFICATION: X"])
def test_a_closed_title_is_shown_without_its_change_specification_lead(
    board: Board, written: str
) -> None:
    archive(
        board.repo, 3, [{"cr": "CR-1", "title": written, "result": "merged", "pr": LINK.format(70)}]
    )
    board.forge = {70: {"state": "merged", "base": "main", "merged_at": "2026-11-01T00:00:00Z"}}
    assert [r["title"] for r in ask(board, CLOSED)["rows"]] == ["X"]


@pytest.mark.parametrize("written", ["Change Specification: X", "change specification: X", "X"])
def test_a_title_is_shown_without_its_change_specification_lead(board: Board, written: str) -> None:
    data = record(board.repo)
    data["crs"][0]["title"] = written
    write_record(board.repo, data)
    assert board.rows()[board.ids[0]]["title"] == "X"


def test_a_merged_event_its_model_refuses_is_set_aside_and_the_page_keeps_its_rows(
    board: Board, monkeypatch: pytest.MonkeyPatch
) -> None:
    # a prepared refusal: an event builder patched to add a field its model does not hold
    build = hub_journal.merged_events

    def with_a_bad_one(batch: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        good = build(batch, rows)
        return [*good, {**good[0], "cr": "x"}]

    monkeypatch.setattr(hub_journal, "merged_events", with_a_bad_one)
    board.forge = {FIRST + 1: {"state": "merged", "base": "main", "merged_at": MERGED_AT}}
    code, answer = board.get()
    assert code == HTTP_OK and answer["rows"]
    assert answer["error"].startswith("skipped: journal payload merged@1: cr")
    assert [e["cr"] for e in seen_lines(board)] == [board.ids[1]]
