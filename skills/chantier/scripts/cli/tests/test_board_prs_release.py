"""The PRs page and a release CR whose PR `order merged` moved to `merged_pr`: the row still
shows it, and a forge that sees it merged is no merge the record lacks."""

from __future__ import annotations

from pathlib import Path

import pytest
from batch_helpers import record, write_record
from conftest import Chantier
from test_board_prs import FIRST, LINK, Board, seen_lines, served

from chantier.board import prs


@pytest.fixture
def board(repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch) -> Board:
    return served(repo, chantier, monkeypatch)


@pytest.mark.parametrize("release", [True, False])
def test_a_release_pr_merged_in_the_record_is_not_a_merge_the_record_lacks(
    board: Board, release: bool
) -> None:
    data = record(board.repo)
    first = data["crs"][0]
    if release:  # `order merged` moved the link to `merged_pr`; the release goes on, queued
        first.update(kind="release", status="queued", merged_pr=first["pr"], pr=None)
    write_record(board.repo, data)
    board.forge = {FIRST: {"state": "merged"}}
    row = board.rows()[board.ids[0]]
    if release:
        assert (row["state"], row["pr"], row["why"], row["disagrees"]) == (
            "merged",
            LINK.format(FIRST),
            None,
            None,
        )
        assert seen_lines(board) == []
    else:
        assert (row["why"], row["disagrees"]) == ("merged", prs.MERGED_NOT_RECORDED)
        assert len(seen_lines(board)) == 1
