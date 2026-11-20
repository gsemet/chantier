"""The GitLab connector: one `glab api graphql` query for every MR of a project.

`review`, only when asked, is `unproved` and adds no field to the query: GitLab's approvals are
not proved on a real MR yet."""

from __future__ import annotations

from typing import Any

from chantier.commands.forge_stack_gitlab import GITLAB_LINK
from chantier.connectors.base import Facts, Place
from chantier.connectors.run import node, run

DEFAULT_HOST = "gitlab.com"
GITLAB_FIELDS = (
    "state draft conflicts detailedMergeStatus targetBranch diffHeadSha mergedAt closedAt "
    "createdAt updatedAt headPipeline { status }"
)
GITLAB_CHECKS = {
    "SUCCESS": "green",
    "SUCCESS_WITH_WARNINGS": "green",
    "FAILED": "failing",
    "CANCELED": "failing",
    "CANCELING": "failing",
    "RUNNING": "running",
    "PENDING": "running",
    "CREATED": "running",
    "PREPARING": "running",
    "SCHEDULED": "running",
    "WAITING_FOR_RESOURCE": "running",
}
GITLAB_UNCOMPUTED = {"CHECKING", "UNCHECKED"}


def gitlab_query(numbers: list[int]) -> str:
    prs = " ".join(f'm{n}: mergeRequest(iid: "{n}") {{ {GITLAB_FIELDS} }}' for n in numbers)
    return f"query($path: ID!) {{ project(fullPath: $path) {{ {prs} }} }}"


def argv(host: str, path: str, numbers: list[int]) -> list[str]:
    """The call after the program's name: `api graphql`, the query and its variable."""
    return [
        "api",
        *(["--hostname", host] if host != DEFAULT_HOST else []),
        "graphql",
        "-f",
        f"query={gitlab_query(numbers)}",
        "-f",
        f"path={path}",
    ]


def gitlab_state(n: dict[str, Any], facts: frozenset[str] = frozenset()) -> Facts:
    """One MR as the page judges it. No pipeline yet cannot be told from a project with no CI
    (no field says it): the MR is "being checked"."""
    state = {"merged": "merged", "closed": "closed"}.get(str(n.get("state")), "open")
    live = state == "open"
    pipeline = (n.get("headPipeline") or {}).get("status")
    checks = GITLAB_CHECKS.get(str(pipeline)) if pipeline else None
    uncomputed = str(n.get("detailedMergeStatus")) in GITLAB_UNCOMPUTED
    found: Facts = {
        "state": "draft" if live and n.get("draft") else state,
        "conflicting": live and bool(n.get("conflicts")),
        "checking": live and (uncomputed or checks is None),
        "checks": checks or ("running" if live else "none"),
        "base": n.get("targetBranch"),
        "head": n.get("diffHeadSha"),
        "merged_on_default": None,
        "merged_at": n.get("mergedAt"),
        "closed_at": n.get("closedAt"),
        "opened_at": n.get("createdAt"),
        "updated_at": n.get("updatedAt"),
    }
    if "review" in facts:
        found["review"] = "unproved"
    return found


def _gitlab_rows(
    got: dict[str, Any], numbers: list[int], facts: frozenset[str] = frozenset()
) -> dict[int, Facts]:
    project = (got.get("data") or {}).get("project") or {}
    return {n: gitlab_state(node(project, "m", n), facts) for n in numbers}


class GitLab:
    name = "gitlab"
    program = "glab"
    word = "MR"

    def claims(self, link: str) -> bool:
        return GITLAB_LINK.match(link) is not None

    def _parts(self, link: str) -> tuple[str, ...]:
        found = GITLAB_LINK.match(link)
        assert found is not None, link
        return found.groups()

    def place(self, link: str) -> Place:
        host, path, _ = self._parts(link)
        return Place(self.name, host, path)

    def number(self, link: str) -> int:
        return int(self._parts(link)[2])

    def read(self, place: Place, numbers: list[int], facts: frozenset[str]) -> dict[int, Facts]:
        got = run(self.program, argv(place.host, place.repository, numbers))
        return _gitlab_rows(got, numbers, facts)


CONNECTOR = GitLab()
