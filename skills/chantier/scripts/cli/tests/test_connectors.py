"""The forge connectors: GitHub's and GitLab's answers turned into one state, the query, the
argv, the read-only guard, the plugin table and the runner's failures. No test reaches a forge."""

from __future__ import annotations

import shutil
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import pytest

from chantier import connectors
from chantier.board import prs
from chantier.commands.forge_stack_shared import NOT_ONE_REPOSITORY
from chantier.connectors import github, gitlab, run
from chantier.connectors.base import Place
from chantier.core.errors import ChantierError

LINK = "https://github.com/acme/demo/pull/{}"
GH_LINK, GL_LINK = LINK.format(3), "https://gitlab.com/grp/sub/proj/-/merge_requests/3"
GHE_LINK = "https://ghe.example/acme/demo/pull/3"
GLS_LINK = "https://git.example/grp/proj/-/merge_requests/3"

# the queries as they were read before the connectors existed (no optional fact asked)
GITHUB_GOLD = (
    "query($owner: String!, $name: String!) { repository(owner: $owner, name: $name) { wf: "
    'object(expression: "HEAD:.github/workflows") { ... on Tree { entries { name } } } dh: '
    'object(expression: "HEAD") { ... on Commit { history(first: 100) { nodes { oid } } } } '
    "p3: pullRequest(number: 3) { state isDraft mergeable baseRefName headRefOid mergedAt "
    "closedAt createdAt updatedAt mergeCommit { oid } commits(last: 1) { nodes { commit { "
    "statusCheckRollup { state contexts(first: 1) { totalCount } } } } } } } }"
)
GITLAB_GOLD = (
    'query($path: ID!) { project(fullPath: $path) { m3: mergeRequest(iid: "3") { state draft '
    "conflicts detailedMergeStatus targetBranch diffHeadSha mergedAt closedAt createdAt "
    "updatedAt headPipeline { status } } } }"
)

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
    found = github.github_state({**GH_NODE, **node}, workflows, set())
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
    found = gitlab.gitlab_state({"state": "opened", "targetBranch": "main", **node})
    assert (found["state"], found["checking"], found["checks"]) == (state, checking, checks)


def test_both_queries_ask_for_the_dates_and_both_states_return_them() -> None:
    assert "createdAt updatedAt" in github.GITHUB_FIELDS
    assert "createdAt updatedAt" in gitlab.GITLAB_FIELDS
    dates = {"createdAt": "2026-11-01T00:00:00Z", "updatedAt": "2026-11-02T00:00:00Z"}
    for found in (
        github.github_state({**GH_NODE, **dates}, True, set()),
        gitlab.gitlab_state({"state": "opened", **dates}),
    ):
        assert (found["opened_at"], found["updated_at"]) == tuple(dates.values())


def test_both_queries_ask_for_the_head_commit_and_both_states_carry_it() -> None:
    assert "headRefOid" in github.GITHUB_FIELDS
    assert "diffHeadSha" in gitlab.GITLAB_FIELDS
    found = github.github_state({**GH_NODE, "headRefOid": "abc123"}, True, set())
    assert found["head"] == "abc123"
    assert gitlab.gitlab_state({"state": "opened", "diffHeadSha": "def456"})["head"] == "def456"


@pytest.mark.parametrize(
    ("node", "gitlab_mr", "want"),
    [
        ({"state": "MERGED", "mergeCommit": {"oid": "aaa"}}, False, True),  # in the history
        ({"state": "MERGED", "mergeCommit": {"oid": "zzz"}}, False, False),  # not in it
        ({"state": "MERGED", "mergeCommit": None}, False, False),  # no merge commit
        ({"state": "OPEN"}, False, None),
        ({"state": "merged"}, True, None),  # GitLab never says
    ],
)
def test_a_merged_pr_says_whether_its_merge_commit_is_on_the_default_branch(
    node: dict[str, Any], gitlab_mr: bool, want: bool | None
) -> None:
    history = {"history": {"nodes": [{"oid": "aaa"}, {"oid": "bbb"}]}}
    if gitlab_mr:
        found = gitlab.gitlab_state({"state": "merged", "targetBranch": "main"})
    else:
        got = {"data": {"repository": {"dh": history, "p1": {**GH_NODE, **node}}}}
        found = github._github_rows(got, [1])[1]
    assert found["merged_on_default"] is want


def test_the_github_query_reads_the_merge_commit_and_the_default_branch_history() -> None:
    assert "mergeCommit { oid }" in github.GITHUB_FIELDS
    query = github.github_query([1])
    assert 'object(expression: "HEAD")' in query
    assert "history(first: 100)" in query


@pytest.mark.parametrize(
    ("link", "other", "name"),
    [
        (GH_LINK, GL_LINK, "github"),
        (GL_LINK, GH_LINK, "gitlab"),
        (GHE_LINK, GL_LINK, "github"),
        (GLS_LINK, GH_LINK, "gitlab"),
    ],
)
def test_a_link_is_claimed_by_its_connector_and_by_no_other(
    link: str, other: str, name: str
) -> None:
    assert [c.name for c in connectors.CONNECTORS if c.claims(link)] == [name]
    found, wrong = connectors.connector_for(link), connectors.connector_for(other)
    assert found is not None and wrong is not None
    assert found.name == name and wrong.name != name


def test_a_link_no_connector_claims_is_not_read() -> None:
    odd = "https://example.org/acme/demo/issues/3"
    assert connectors.connector_for(odd) is None
    with pytest.raises(ChantierError) as raised:
        connectors.read([GH_LINK, odd])
    assert str(raised.value) == connectors.UNCLAIMED.format(link=odd)
    assert str(raised.value) == f"no connector reads {odd}: chantier reads GitHub and GitLab"


@pytest.mark.parametrize(
    ("connector", "link", "host", "plain"),
    [
        (github.CONNECTOR, GHE_LINK, "ghe.example", GH_LINK),
        (gitlab.CONNECTOR, GLS_LINK, "git.example", GL_LINK),
    ],
)
def test_the_argv_is_a_graphql_query_and_names_a_host_other_than_the_forges_own(
    monkeypatch: pytest.MonkeyPatch, connector: Any, link: str, host: str, plain: str
) -> None:
    calls: list[list[str]] = []

    def fake(program: str, call: list[str]) -> dict[str, Any]:
        run.guard(call)  # the shipped argv passes the read-only guard
        calls.append(call)
        return {"data": {}}

    monkeypatch.setattr(sys.modules[type(connector).__module__], "run", fake)
    for url, other_host in ((link, True), (plain, False)):
        with pytest.raises(ChantierError, match="does not show"):
            connector.read(connector.place(url), [3], frozenset())
        call = calls[-1]
        query = next(a for a in call if a.startswith("query=")).lower()
        assert (call[:4] == ["api", "--hostname", host, "graphql"]) is other_host
        assert (call[:2] == ["api", "graphql"]) is not other_host
        assert query.startswith("query=query") and "mutation" not in query
        assert not {"-X", "--method", "POST", "PATCH", "PUT", "DELETE"} & set(call)


@pytest.mark.parametrize(
    "call",
    [
        ["api", "graphql", "-f", "query=mutation { x }"],
        ["api", "--hostname", "h", "graphql", "-f", "query=query { y } mutation { x }"],
        ["api", "graphql", "-f", "owner=a"],  # no query
        ["api", "graphql", "-f", "query=query { a }", "-f", "query=query { b }"],
        ["api", "-X", "POST", "graphql", "-f", "query=query { a }"],
        ["repo", "delete", "-f", "query=query { a }"],
        ["api", "--hostname", "graphql", "-f", "query=query { a }"],
    ],
)
def test_the_guard_refuses_what_is_not_a_read_only_graphql_query(call: list[str]) -> None:
    with pytest.raises(AssertionError):
        run.guard(call)


def test_the_query_with_no_optional_fact_is_the_one_read_before_the_connectors() -> None:
    assert github.github_query([3]) == GITHUB_GOLD
    assert gitlab.gitlab_query([3]) == GITLAB_GOLD


@pytest.mark.parametrize(
    ("decision", "word"),
    [
        ("APPROVED", "approved"),
        ("CHANGES_REQUESTED", "changes-requested"),
        ("REVIEW_REQUIRED", "required"),
        (None, "unknown"),
    ],
)
def test_review_is_asked_of_github_and_its_four_answers_map_to_words(
    decision: str | None, word: str
) -> None:
    asked = frozenset({"review"})
    assert "reviewDecision" in github.github_query([3], asked)
    assert "reviewDecision" not in github.github_query([3])
    got = {"data": {"repository": {"p3": {**GH_NODE, "reviewDecision": decision}}}}
    assert github._github_rows(got, [3], asked)[3]["review"] == word
    assert "review" not in github._github_rows(got, [3])[3]


def test_review_is_unproved_on_gitlab_with_the_same_query() -> None:
    got = {"data": {"project": {"m3": {"state": "opened"}}}}
    assert gitlab._gitlab_rows(got, [3], frozenset({"review"}))[3]["review"] == "unproved"
    assert "review" not in gitlab._gitlab_rows(got, [3])[3]
    assert gitlab.gitlab_query([3]) == GITLAB_GOLD


def test_the_places_name_one_repository_per_connector() -> None:
    assert github.CONNECTOR.place(GH_LINK) == Place("github", "github.com", "acme/demo")
    assert gitlab.CONNECTOR.place(GL_LINK) == Place("gitlab", "gitlab.com", "grp/sub/proj")
    assert (github.CONNECTOR.number(GH_LINK), gitlab.CONNECTOR.number(GL_LINK)) == (3, 3)


@pytest.mark.parametrize(
    "links",
    [
        [LINK.format(1), "https://github.com/acme/other/pull/2"],
        [LINK.format(1), "https://gitlab.com/acme/demo/-/merge_requests/2"],
    ],
)
def test_the_batch_must_sit_in_one_repository_and_nothing_is_read_otherwise(
    monkeypatch: pytest.MonkeyPatch, links: list[str]
) -> None:
    def never(*a: object, **k: object) -> None:
        raise AssertionError("the forge was called")

    monkeypatch.setattr(github, "run", never)
    monkeypatch.setattr(gitlab, "run", never)
    with pytest.raises(ChantierError, match=NOT_ONE_REPOSITORY):
        connectors.read(links)


@pytest.mark.parametrize(
    ("ran", "text"),
    [
        (None, "not found on PATH"),
        (subprocess.TimeoutExpired("x", 20), "no answer in"),
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
@pytest.mark.parametrize(("link", "program"), [(GH_LINK, "gh"), (GL_LINK, "glab")])
def test_the_runner_turns_every_failure_into_one_line(
    monkeypatch: pytest.MonkeyPatch, ran: Any, text: str, link: str, program: str
) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: None if ran is None else f"/bin/{name}")

    def fake_run(*a: object, **k: object) -> Any:
        if isinstance(ran, Exception):
            raise ran
        return ran

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(ChantierError) as raised:
        connectors.read([link])
    assert text in str(raised.value) and "\n" not in str(raised.value)
    assert str(raised.value).startswith(program) and "query" not in str(raised.value)
