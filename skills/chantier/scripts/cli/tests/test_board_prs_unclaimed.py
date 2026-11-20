"""The PRs page and a PR link no connector claims: its row is not read, the error line names it,
and the batch's other rows are read."""

from __future__ import annotations

from pathlib import Path

import pytest
from batch_helpers import record, write_record
from conftest import Chantier
from test_board_prs import CRS, Board, served

from chantier import connectors


@pytest.fixture
def board(repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch) -> Board:
    return served(repo, chantier, monkeypatch)


def test_a_link_no_connector_claims_is_named_in_the_error_line_and_the_other_rows_are_read(
    board: Board,
) -> None:
    odd = "https://example.org/acme/demo/issues/7"
    data = record(board.repo)
    data["crs"][1]["pr"] = odd
    write_record(board.repo, data)
    body = board.get()[1]
    assert body["error"] == connectors.UNCLAIMED.format(link=odd)
    assert len(board.calls) == 1 and odd not in board.calls[0] and len(board.calls[0]) == CRS - 1
    assert [r["cr"] for r in body["rows"]] == [x for x in board.ids if x != board.ids[1]]
    assert body["read_at"] and not body["all_done"]
