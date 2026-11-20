"""What an interest and a provider are (see `interests.py`, the registry that holds them)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from chantier.connectors.base import Facts
from chantier.core.repo import Repo

PR = "pr"  # a review request, read by the hub through its connector
ISSUE = "issue"  # a tracker issue a CR's `issue:` line names, read by an outside poller only


@dataclass(frozen=True)
class Interest:
    kind: str  # `pr` or `issue`
    ref: str  # the PR or MR link, or the issue's link as the CR's `issue:` line writes it
    facts: frozenset[str]  # `state` and `checks` (always read), optionally `review`
    by: str  # who waits: `batch-29 CR-3`, or a CR folder's path under `changes/`
    provider: str  # the name of the provider that declared it
    tracker: str | None = None  # `jira`, `gitlab`, `github` or `other` for an issue; None for a pr


class Provider(Protocol):
    name: str
    kinds: frozenset[str]  # the kinds of interest it declares

    def collect(self, repo: Repo) -> list[Interest]: ...

    def judge(
        self, repo: Repo, interests: list[Interest], facts: dict[str, Facts]
    ) -> list[dict[str, Any]]:
        """The journal events its interests show, from the facts read (by link)."""
        ...
