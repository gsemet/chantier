"""The board's PRs page: its route (`GET /api/projects/<id>/prs`) on a prepared batch, the
judgement of a PR against the record, the forge read's query and its failures.

No test reaches a forge: the route's one seam, `forge_read.read`, is replaced, and the runner's
own failures are tried with `subprocess.run` replaced."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from batch_helpers import changes, open_batch, record, write_record
from conftest import Chantier

from chantier.board import forge_read, prs, routes
from chantier.board.context import Context, Request
from chantier.board.key import KeyFile, key_path, load_or_create
from chantier.board.projects import Projects
from chantier.board.seats import Seats
from chantier.commands.forge_stack_gh import pr_parts
from chantier.commands.forge_stack_shared import NOT_ONE_REPOSITORY
from chantier.core.errors import ChantierError
from chantier.core.repo import Repo

LINK = "https://github.com/acme/demo/pull/{}"
FIRST = 40
HTTP_OK, HTTP_NO_KEY = 200, 401
CRS, TWO_CALLS, THREE_CALLS, NEW_PR = 4, 2, 3, 99
OPEN: dict[str, Any] = {
    "state": "open",
    "conflicting": False,
    "checking": False,
    "checks": "green",
    "base": "main",
    "merged_at": None,
    "closed_at": None,
}


class Board:
    """A served project with four CRs whose PRs are 40 to 43, all ready in the record; the forge
    answers what `forge` holds (a PR number to the fields that differ from `OPEN`)."""

    def __init__(self, repo: Path, ids: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
        self.repo, self.ids = repo, ids
        self.forge: dict[int, dict[str, Any]] = {}
        self.calls: list[list[str]] = []
        self.failure: Exception | None = None
        self.now = 0.0
        found = Repo.find(readonly=True)
        projects = Projects(found, None, [])
        self.key = load_or_create(found)
        self.id = projects.home_id
        self.ctx = Context(projects, KeyFile(key_path(found)), Seats(projects), "t", lambda: None)
        self.ctx.reads = prs.ForgeReads(now=lambda: self.now)
        monkeypatch.setattr(forge_read, "read", self.read)

    def read(self, links: list[str]) -> dict[int, dict[str, Any]]:
        self.calls.append(links)
        if self.failure:
            raise self.failure
        return {n: {**OPEN, **self.forge.get(n, {})} for n in (int(pr_parts(x)[3]) for x in links)}

    def get(self, key: bool = True) -> tuple[int, dict[str, Any]]:
        headers = {"x-chantier-board-key": self.key} if key else {}
        reply = routes.handle(self.ctx, Request("GET", f"/api/projects/{self.id}/prs", {}, headers))
        return reply.status, json.loads(reply.body or b"{}") if reply.status == HTTP_OK else {}

    def rows(self) -> dict[str, dict[str, Any]]:
        return {r["cr"]: r for r in self.get()[1]["rows"]}

    def edit(self, **batch: Any) -> None:
        data = record(self.repo)
        data.update(batch)
        write_record(self.repo, data)

    def planning(self) -> dict[str, bytes]:
        root = changes(self.repo)
        return {p.as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


@pytest.fixture
def board(repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch) -> Board:
    ids = open_batch(repo, chantier, monkeypatch, "Alpha", "Beta", "Gamma", "Delta")
    data = record(repo)
    for i, c in enumerate(data["crs"]):
        c.update(pr=LINK.format(FIRST + i), pr_draft=False, pr_base="main", status="ready")
        c["branch"] = f"chantier/b/cr-{i}"
    write_record(repo, data)
    return Board(repo, ids, monkeypatch)


def test_the_route_needs_the_key_and_with_no_batch_asks_no_forge(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert chantier("file", "Something")[0] == 0
    old = changes(repo) / "5-archives" / "batches"
    old.mkdir(parents=True, exist_ok=True)
    (old / "batch-7.json").write_text(json.dumps({"id": "batch-7"}), encoding="utf-8")
    board = Board(repo, [], monkeypatch)
    assert board.get(key=False)[0] == HTTP_NO_KEY
    status, body = board.get()
    assert (status, body["batch"], body["last_batch"], body["rows"]) == (
        HTTP_OK,
        None,
        "batch-7",
        [],
    )
    assert (body["all_done"], body["error"], board.calls) == (False, None, [])


def test_the_four_crs_are_read_in_one_call_and_judged_against_the_record(board: Board) -> None:
    a, b, c, d = board.ids
    board.forge = {
        FIRST + 1: {"conflicting": True},
        FIRST + 2: {"checking": True, "checks": "running"},
        FIRST + 3: {"state": "merged", "base": "chantier/b/cr-0", "merged_at": "t"},
    }
    data = record(board.repo)
    data["crs"][3]["status"] = "working"  # the record does not hold the fourth as ready or merged
    write_record(board.repo, data)
    before = board.planning()
    status, body = board.get()
    rows = board.rows()
    assert status == HTTP_OK and len(board.calls) == 1 and len(board.calls[0]) == CRS
    assert [r["cr"] for r in body["rows"]] == board.ids
    assert [rows[x]["ready_now"] for x in (a, b, c, d)] == [True, False, False, False]
    assert (rows[b]["conflicting"], rows[b]["disagrees"]) == (
        True,
        "ready in the record, conflicting on the forge",
    )
    assert (rows[c]["checking"], rows[c]["disagrees"]) == (True, None)
    assert rows[d]["state"] == "merged" and rows[d]["merged_into"] == {
        "branch": "chantier/b/cr-0",
        "cr": a,
    }
    assert rows[d]["disagrees"] == prs.MERGED_NOT_RECORDED
    assert board.planning() == before  # a read writes nothing


def test_a_paused_batch_is_read_as_a_running_one(board: Board) -> None:
    board.edit(status="paused")
    body = board.get()[1]
    assert (body["paused"], len(body["rows"]), len(board.calls)) == (True, 4, 1)


def test_a_cr_not_ready_in_the_record_is_never_ready_now(board: Board) -> None:
    data = record(board.repo)
    data["crs"][0]["status"] = "working"
    write_record(board.repo, data)
    assert board.rows()[board.ids[0]]["ready_now"] is False


def test_two_reads_within_ten_seconds_are_one_forge_call_and_a_new_pr_reads_again(
    board: Board,
) -> None:
    board.get()
    board.now = 9.0
    board.get()
    assert len(board.calls) == 1
    board.now = 10.5
    board.get()
    assert len(board.calls) == TWO_CALLS
    data = record(board.repo)
    data["crs"][3]["pr"] = LINK.format(NEW_PR)
    write_record(board.repo, data)
    board.now = 11.0
    assert board.get()[1]["rows"][3]["number"] == NEW_PR and len(board.calls) == THREE_CALLS


@pytest.mark.parametrize(
    "failure",
    [
        ChantierError("gh: not found on PATH (the user's own `gh` login is needed)"),
        ChantierError("gh api graphql: HTTP 403: rate limited"),
        ChantierError(NOT_ONE_REPOSITORY),
    ],
)
def test_a_forge_failure_shows_its_text_and_keeps_the_last_good_read(
    board: Board, failure: Exception
) -> None:
    first = board.get()[1]
    board.failure, board.now = failure, 11.0
    body = board.get()[1]
    assert body["error"] == str(failure)
    assert body["rows"] == first["rows"] and body["read_at"] == first["read_at"]
    board.now = 22.0
    board.failure = None
    assert board.get()[1]["error"] is None


def test_a_failure_before_any_good_read_invents_no_row(board: Board) -> None:
    board.failure = ChantierError("gh: not found on PATH")
    body = board.get()[1]
    assert (body["rows"], body["read_at"], body["all_done"]) == ([], None, False)
    assert body["error"] == "gh: not found on PATH"


@pytest.mark.parametrize(
    ("states", "done"),
    [
        (["merged"] * 4, True),
        (["merged", "merged", "merged", "closed"], True),
        (["merged", "merged", "open", "closed"], False),
        (["draft", "merged", "merged", "merged"], False),
    ],
)
def test_all_done_is_every_pr_merged_or_closed(board: Board, states: list[str], done: bool) -> None:
    board.forge = {FIRST + i: {"state": s} for i, s in enumerate(states)}
    assert board.get()[1]["all_done"] is done


GH_NODE = {
    "state": "OPEN",
    "isDraft": False,
    "mergeable": "MERGEABLE",
    "baseRefName": "main",
    "mergedAt": None,
    "closedAt": None,
}


def rollup(state: str | None, total: int = 1) -> dict[str, Any]:
    found = {"state": state, "contexts": {"totalCount": total}} if state else None
    return {"commits": {"nodes": [{"commit": {"statusCheckRollup": found}}]}}


@pytest.mark.parametrize(
    ("node", "workflows", "checking", "checks", "ready"),
    [
        ({**rollup("SUCCESS")}, True, False, "green", True),
        (
            {**rollup(None)},
            True,
            True,
            "running",
            False,
        ),  # checks not started, a repo that has them
        ({**rollup(None)}, False, False, "none", True),  # the forge says the repository has none
        ({**rollup("SUCCESS", 0)}, False, False, "none", True),
        ({**rollup("SUCCESS", 0)}, True, True, "running", False),
        ({**rollup("PENDING")}, True, False, "running", False),
        ({**rollup("FAILURE")}, True, False, "failing", False),
        ({**rollup("SUCCESS"), "mergeable": "UNKNOWN"}, True, True, "green", False),
        ({**rollup("SUCCESS"), "mergeable": "CONFLICTING"}, True, False, "green", False),
        ({**rollup("SUCCESS"), "isDraft": True}, True, False, "green", False),
        ({**rollup(None), "state": "MERGED"}, True, False, "none", False),  # done: never running
        ({**rollup(None), "state": "CLOSED"}, True, False, "none", False),
        (
            {"commits": None},
            True,
            True,
            "running",
            False,
        ),  # a read that cannot tell is never "none"
    ],
)
def test_github_checks_not_started_are_being_checked_and_none_needs_the_forge_to_say_so(
    node: dict[str, Any], workflows: bool, checking: bool, checks: str, ready: bool
) -> None:
    found = forge_read.github_state({**GH_NODE, **node}, workflows)
    assert (found["checking"], found["checks"]) == (checking, checks)
    assert prs.ready_now({"to_review": True, "state": "ready"}, found) is ready


@pytest.mark.parametrize(
    ("node", "checking", "checks", "state"),
    [
        (
            {"headPipeline": {"status": "SUCCESS"}, "detailedMergeStatus": "MERGEABLE"},
            False,
            "green",
            "open",
        ),
        ({"headPipeline": None, "detailedMergeStatus": "MERGEABLE"}, True, "running", "open"),
        (
            {"headPipeline": {"status": "SUCCESS"}, "detailedMergeStatus": "CHECKING"},
            True,
            "green",
            "open",
        ),
        ({"headPipeline": {"status": "FAILED"}, "draft": True}, False, "failing", "draft"),
        ({"state": "merged", "headPipeline": None}, False, "none", "merged"),
    ],
)
def test_gitlab_reads_the_same_words_and_never_says_none_for_an_open_mr_it_cannot_tell(
    node: dict[str, Any], checking: bool, checks: str, state: str
) -> None:
    found = forge_read.gitlab_state({"state": "opened", "targetBranch": "main", **node})
    assert (found["state"], found["checking"], found["checks"]) == (state, checking, checks)


def test_the_forge_argv_is_a_read_and_its_variables_are_not_in_the_query() -> None:
    for gitlab in (False, True):
        call = forge_read.argv("h.example", "own'er", 'na"me', [3, 12], gitlab)
        query = next(a for a in call if a.startswith("query=")).lower()
        assert call[:3] == ["api", "--hostname", "h.example"] and call[3] == "graphql"
        assert query.startswith("query=query") and "mutation" not in query
        assert not {"-X", "--method", "POST", "PATCH", "PUT", "DELETE"} & set(call)
        assert "own'er" not in query and 'na"me' not in query


def test_the_batch_must_sit_in_one_repository_and_nothing_is_read_otherwise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def never(*a: object, **k: object) -> None:
        raise AssertionError("the forge was called")

    monkeypatch.setattr(forge_read, "run", never)
    with pytest.raises(ChantierError, match=NOT_ONE_REPOSITORY):
        forge_read.read([LINK.format(1), "https://github.com/acme/other/pull/2"])


@pytest.mark.parametrize(
    ("ran", "text"),
    [
        (None, "gh: not found on PATH"),
        (subprocess.TimeoutExpired("gh", 20), "no answer in"),
        (
            SimpleNamespace(returncode=1, stdout="", stderr="HTTP 401\nbad  credentials"),
            "HTTP 401 bad credentials",
        ),
        (SimpleNamespace(returncode=0, stdout="<html>", stderr=""), "not JSON"),
        (
            SimpleNamespace(
                returncode=0, stdout='{"errors": [{"message": "no such PR"}]}', stderr=""
            ),
            "no such PR",
        ),
    ],
)
def test_the_runner_turns_every_failure_into_one_line(
    monkeypatch: pytest.MonkeyPatch, ran: Any, text: str
) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: None if ran is None else "/bin/gh")

    def run(*a: object, **k: object) -> Any:
        if isinstance(ran, Exception):
            raise ran
        return ran

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(ChantierError) as raised:
        forge_read.read([LINK.format(5)])
    assert text in str(raised.value) and "\n" not in str(raised.value)
    assert "query" not in str(raised.value)
