"""The board's own forge read, for its PRs page: one GraphQL query for all of a batch's PRs.

It only reads: the argv is `gh api graphql` or `glab api graphql` with a query text, never a
mutation. The forge is chosen from the shape of the links (`pr_parts`, `GITLAB_LINK`), as
`forge_base.py` does. `read` is the seam the tests replace; everything else is a pure function of
the forge's answer. When the answer cannot tell whether the checks have started, the PR is "being
checked", never "no checks"."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from chantier.commands.forge_stack_gh import pr_parts
from chantier.commands.forge_stack_gitlab import GITLAB_LINK
from chantier.commands.forge_stack_shared import NOT_ONE_REPOSITORY
from chantier.core.errors import EXIT_EXTERNAL, EXIT_PRECONDITION, ChantierError

TIMEOUT_S = 20  # a hung `gh` or `glab` holds one worker and the project's lock for this long
SHOWN_CHARS = 300

GITHUB_FIELDS = (
    "state isDraft mergeable baseRefName mergedAt closedAt "
    "commits(last: 1) { nodes { commit { statusCheckRollup { state contexts(first: 1) "
    "{ totalCount } } } } }"
)
GITLAB_FIELDS = (
    "state draft conflicts detailedMergeStatus targetBranch mergedAt closedAt "
    "headPipeline { status }"
)
# the rollup states of GitHub and the pipeline statuses of GitLab, as the page words them
GITHUB_CHECKS = {
    "SUCCESS": "green",
    "FAILURE": "failing",
    "ERROR": "failing",
    "PENDING": "running",
    "EXPECTED": "running",
}
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
Forge = dict[str, Any]


def github_query(numbers: list[int]) -> str:
    """One query for every PR: the numbers are integers (aliases `p<N>`); the owner and the name
    travel as variables. The workflow folder of the default branch says whether the repository
    has checks."""
    prs = " ".join(f"p{n}: pullRequest(number: {n}) {{ {GITHUB_FIELDS} }}" for n in numbers)
    return (
        "query($owner: String!, $name: String!) { repository(owner: $owner, name: $name) { "
        'wf: object(expression: "HEAD:.github/workflows") { ... on Tree { entries { name } } } '
        f"{prs} }} }}"
    )


def gitlab_query(numbers: list[int]) -> str:
    prs = " ".join(f'm{n}: mergeRequest(iid: "{n}") {{ {GITLAB_FIELDS} }}' for n in numbers)
    return f"query($path: ID!) {{ project(fullPath: $path) {{ {prs} }} }}"


def argv(host: str, owner: str, name: str, numbers: list[int], gitlab: bool) -> list[str]:
    """The call after the program's name: `api graphql`, the query and its variables."""
    if gitlab:
        tail = ["-f", f"query={gitlab_query(numbers)}", "-f", f"path={owner}"]
        default = "gitlab.com"
    else:
        tail = [
            "-f",
            f"query={github_query(numbers)}",
            "-f",
            f"owner={owner}",
            "-f",
            f"name={name}",
        ]
        default = "github.com"
    return ["api", *(["--hostname", host] if host != default else []), "graphql", *tail]


def _line(text: str) -> str:
    return " ".join(text.split())[:SHOWN_CHARS]


def run(program: str, call: list[str]) -> dict[str, Any]:
    """One call, answered as JSON; a failure comes back as the forge's own one line."""
    exe = shutil.which(program)
    if not exe:
        raise ChantierError(
            f"{program}: not found on PATH (the user's own `{program}` login is needed)",
            EXIT_EXTERNAL,
        )
    shown = f"{program} api graphql"
    try:
        p = subprocess.run(
            [exe, *call],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as e:
        raise ChantierError(f"{shown}: no answer in {TIMEOUT_S} s", EXIT_EXTERNAL) from e
    except OSError as e:
        raise ChantierError(f"{shown}: {_line(str(e))}", EXIT_EXTERNAL) from e
    if p.returncode != 0:
        raise ChantierError(f"{shown}: {_line(p.stderr or p.stdout)}", EXIT_EXTERNAL)
    try:
        got = json.loads(p.stdout)
    except ValueError as e:
        raise ChantierError(f"{shown}: not JSON: {_line(p.stdout)}", EXIT_EXTERNAL) from e
    if not isinstance(got, dict):
        raise ChantierError(f"{shown}: unexpected answer: {_line(p.stdout)}", EXIT_EXTERNAL)
    if got.get("errors"):
        said = "; ".join(
            str(e.get("message", e)) if isinstance(e, dict) else str(e) for e in got["errors"]
        )
        raise ChantierError(f"{shown}: {_line(said)}", EXIT_EXTERNAL)
    return got


def _github_checks(node: dict[str, Any], has_workflows: bool) -> str | None:
    """The checks' word, or None when they have not started in a repository that has checks."""
    nodes = (node.get("commits") or {}).get("nodes") or [{}]
    rollup = ((nodes[0] or {}).get("commit") or {}).get("statusCheckRollup")
    if not rollup or not (rollup.get("contexts") or {}).get("totalCount"):
        return None if has_workflows else "none"
    return GITHUB_CHECKS.get(str(rollup.get("state")))


def github_state(node: dict[str, Any], has_workflows: bool) -> Forge:
    """One PR as the page judges it, from GitHub's fields."""
    state = str(node.get("state"))
    live = state == "OPEN"
    word = state.lower()
    if live:
        word = "draft" if node.get("isDraft") else "open"
    checks = _github_checks(node, has_workflows)
    return {
        "state": word,
        "conflicting": live and node.get("mergeable") == "CONFLICTING",
        "checking": live and (node.get("mergeable") == "UNKNOWN" or checks is None),
        "checks": checks or ("running" if live else "none"),
        "base": node.get("baseRefName"),
        "merged_at": node.get("mergedAt"),
        "closed_at": node.get("closedAt"),
    }


def gitlab_state(node: dict[str, Any]) -> Forge:
    """One MR as the page judges it. No pipeline yet cannot be told from a project with no CI
    (no field says it): the MR is "being checked"."""
    state = {"merged": "merged", "closed": "closed"}.get(str(node.get("state")), "open")
    live = state == "open"
    pipeline = (node.get("headPipeline") or {}).get("status")
    checks = GITLAB_CHECKS.get(str(pipeline)) if pipeline else None
    uncomputed = str(node.get("detailedMergeStatus")) in GITLAB_UNCOMPUTED
    return {
        "state": "draft" if live and node.get("draft") else state,
        "conflicting": live and bool(node.get("conflicts")),
        "checking": live and (uncomputed or checks is None),
        "checks": checks or ("running" if live else "none"),
        "base": node.get("targetBranch"),
        "merged_at": node.get("mergedAt"),
        "closed_at": node.get("closedAt"),
    }


def _node(box: dict[str, Any], key: str, n: int) -> dict[str, Any]:
    node = box.get(f"{key}{n}")
    if not node:
        raise ChantierError(f"the forge does not show #{n}", EXIT_EXTERNAL)
    found: dict[str, Any] = node
    return found


def _github_rows(got: dict[str, Any], numbers: list[int]) -> dict[int, Forge]:
    repo = (got.get("data") or {}).get("repository") or {}
    has_workflows = bool((repo.get("wf") or {}).get("entries"))
    return {n: github_state(_node(repo, "p", n), has_workflows) for n in numbers}


def _gitlab_rows(got: dict[str, Any], numbers: list[int]) -> dict[int, Forge]:
    project = (got.get("data") or {}).get("project") or {}
    return {n: gitlab_state(_node(project, "m", n)) for n in numbers}


def read(links: list[str]) -> dict[int, Forge]:
    """Every PR of `links` in one forge call, by number. The one test seam of the page."""
    parts = [pr_parts(link) for link in links]
    places = {p[:3] for p in parts}
    if len(places) != 1:
        raise ChantierError(NOT_ONE_REPOSITORY, EXIT_PRECONDITION)
    host, owner, name = next(iter(places))
    numbers = sorted({int(p[3]) for p in parts})
    gitlab = bool(GITLAB_LINK.match(links[0]))
    got = run("glab" if gitlab else "gh", argv(host, owner, name, numbers, gitlab))
    return _gitlab_rows(got, numbers) if gitlab else _github_rows(got, numbers)
