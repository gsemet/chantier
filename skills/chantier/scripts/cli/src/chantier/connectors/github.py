"""The GitHub connector: one `gh api graphql` query for every PR of a repository.

`head` is the PR's head commit (`PullRequest.headRefOid`). `merged_on_default` is, for a merged
PR, whether its merge commit (`mergeCommit.oid`) is among the default branch's last
`DEFAULT_HISTORY` commits, read in the same query: the window inside which a stacked merge can be
read as landed (None for a PR not merged). When the answer cannot tell whether the checks have
started, the PR is "being checked", never "no checks". `review`, only when asked, is
`reviewDecision`: null is `unknown`, never "approved"."""

from __future__ import annotations

from typing import Any

from chantier.commands.forge_stack_gh import PR_LINK
from chantier.connectors.base import Facts, Place
from chantier.connectors.run import node, run

DEFAULT_HOST = "github.com"
DEFAULT_HISTORY = 100  # the default branch's commits read, to tell a merge landed on it
GITHUB_FIELDS = (
    "state isDraft mergeable baseRefName headRefOid mergedAt closedAt createdAt updatedAt "
    "mergeCommit { oid } commits(last: 1) { nodes { commit { statusCheckRollup { state "
    "contexts(first: 1) { totalCount } } } } }"
)
REVIEW_FIELD = "reviewDecision"
GITHUB_CHECKS = {
    "SUCCESS": "green",
    "FAILURE": "failing",
    "ERROR": "failing",
    "PENDING": "running",
    "EXPECTED": "running",
}
REVIEWS = {
    "APPROVED": "approved",
    "CHANGES_REQUESTED": "changes-requested",
    "REVIEW_REQUIRED": "required",
}


def github_query(numbers: list[int], facts: frozenset[str] = frozenset()) -> str:
    """One query for every PR: the numbers are integers (aliases `p<N>`); the owner and the name
    travel as variables. The workflow folder of the default branch says whether the repository
    has checks."""
    fields = f"{GITHUB_FIELDS} {REVIEW_FIELD}" if "review" in facts else GITHUB_FIELDS
    prs = " ".join(f"p{n}: pullRequest(number: {n}) {{ {fields} }}" for n in numbers)
    return (
        "query($owner: String!, $name: String!) { repository(owner: $owner, name: $name) { "
        'wf: object(expression: "HEAD:.github/workflows") { ... on Tree { entries { name } } } '
        'dh: object(expression: "HEAD") { ... on Commit { '
        f"history(first: {DEFAULT_HISTORY}) {{ nodes {{ oid }} }} }} }} "
        f"{prs} }} }}"
    )


def argv(
    host: str, owner: str, name: str, numbers: list[int], facts: frozenset[str] = frozenset()
) -> list[str]:
    """The call after the program's name: `api graphql`, the query and its variables."""
    return [
        "api",
        *(["--hostname", host] if host != DEFAULT_HOST else []),
        "graphql",
        "-f",
        f"query={github_query(numbers, facts)}",
        "-f",
        f"owner={owner}",
        "-f",
        f"name={name}",
    ]


def _github_checks(n: dict[str, Any], has_workflows: bool) -> str | None:
    """The checks' word, or None when they have not started in a repository that has checks."""
    nodes = (n.get("commits") or {}).get("nodes") or [{}]
    rollup = ((nodes[0] or {}).get("commit") or {}).get("statusCheckRollup")
    if not rollup or not (rollup.get("contexts") or {}).get("totalCount"):
        return None if has_workflows else "none"
    return GITHUB_CHECKS.get(str(rollup.get("state")))


def github_state(
    n: dict[str, Any],
    has_workflows: bool,
    default_oids: set[str],
    facts: frozenset[str] = frozenset(),
) -> Facts:
    """One PR as the page judges it, from GitHub's fields."""
    state = str(n.get("state"))
    live = state == "OPEN"
    word = state.lower()
    if live:
        word = "draft" if n.get("isDraft") else "open"
    checks = _github_checks(n, has_workflows)
    oid = (n.get("mergeCommit") or {}).get("oid")
    found: Facts = {
        "state": word,
        "conflicting": live and n.get("mergeable") == "CONFLICTING",
        "checking": live and (n.get("mergeable") == "UNKNOWN" or checks is None),
        "checks": checks or ("running" if live else "none"),
        "base": n.get("baseRefName"),
        "head": n.get("headRefOid"),
        "merged_on_default": (oid in default_oids) if state == "MERGED" else None,
        "merged_at": n.get("mergedAt"),
        "closed_at": n.get("closedAt"),
        "opened_at": n.get("createdAt"),
        "updated_at": n.get("updatedAt"),
    }
    if "review" in facts:
        found["review"] = REVIEWS.get(str(n.get(REVIEW_FIELD)), "unknown")
    return found


def _github_rows(
    got: dict[str, Any], numbers: list[int], facts: frozenset[str] = frozenset()
) -> dict[int, Facts]:
    repo = (got.get("data") or {}).get("repository") or {}
    has_workflows = bool((repo.get("wf") or {}).get("entries"))
    history = ((repo.get("dh") or {}).get("history") or {}).get("nodes") or []
    oids = {h["oid"] for h in history if h and h.get("oid")}
    return {n: github_state(node(repo, "p", n), has_workflows, oids, facts) for n in numbers}


class GitHub:
    name = "github"
    program = "gh"
    word = "PR"

    def claims(self, link: str) -> bool:
        return PR_LINK.match(link) is not None

    def _parts(self, link: str) -> tuple[str, ...]:
        found = PR_LINK.match(link)
        assert found is not None, link
        return found.groups()

    def place(self, link: str) -> Place:
        host, owner, name, _ = self._parts(link)
        return Place(self.name, host, f"{owner}/{name}")

    def number(self, link: str) -> int:
        return int(self._parts(link)[3])

    def read(self, place: Place, numbers: list[int], facts: frozenset[str]) -> dict[int, Facts]:
        owner, name = place.repository.split("/", 1)
        got = run(self.program, argv(place.host, owner, name, numbers, facts))
        return _github_rows(got, numbers, facts)


CONNECTOR = GitHub()
