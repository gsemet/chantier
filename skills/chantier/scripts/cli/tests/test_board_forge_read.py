"""The forge read of the PRs page: GitHub's and GitLab's answers turned into one state, the
query, and the runner's failures. No test reaches a forge."""

from __future__ import annotations

import shutil
import subprocess
from types import SimpleNamespace
from typing import Any

import pytest

from chantier.board import forge_read, prs
from chantier.commands.forge_stack_shared import NOT_ONE_REPOSITORY
from chantier.core.errors import ChantierError

LINK = "https://github.com/acme/demo/pull/{}"


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


def test_both_queries_ask_for_the_dates_and_both_states_return_them() -> None:
    assert "createdAt updatedAt" in forge_read.GITHUB_FIELDS
    assert "createdAt updatedAt" in forge_read.GITLAB_FIELDS
    dates = {"createdAt": "2026-11-01T00:00:00Z", "updatedAt": "2026-11-02T00:00:00Z"}
    for found in (
        forge_read.github_state({**GH_NODE, **dates}, True),
        forge_read.gitlab_state({"state": "opened", **dates}),
    ):
        assert (found["opened_at"], found["updated_at"]) == tuple(dates.values())


def test_both_queries_ask_for_the_head_commit_and_both_states_carry_it() -> None:
    assert "headRefOid" in forge_read.GITHUB_FIELDS
    assert "diffHeadSha" in forge_read.GITLAB_FIELDS
    assert forge_read.github_state({**GH_NODE, "headRefOid": "abc123"}, True)["head"] == "abc123"
    found = forge_read.gitlab_state({"state": "opened", "diffHeadSha": "def456"})
    assert found["head"] == "def456"


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
