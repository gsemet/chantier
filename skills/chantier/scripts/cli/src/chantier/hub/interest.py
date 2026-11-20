"""What an interest and a provider are (see `interests.py`, the registry that holds them)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from chantier.connectors.base import Facts
from chantier.core.repo import Repo

PR = "pr"  # a review request, read by the hub through its connector


@dataclass(frozen=True)
class Interest:
    kind: str  # `pr`
    ref: str  # the PR or MR link
    facts: frozenset[str]  # `state` and `checks` (always read), optionally `review`
    by: str  # who waits, as a person reads it: `batch-29 CR-3`
    provider: str  # the name of the provider that declared it


class Provider(Protocol):
    name: str
    kinds: frozenset[str]  # the kinds of interest it declares

    def collect(self, repo: Repo) -> list[Interest]: ...

    def judge(
        self, repo: Repo, interests: list[Interest], facts: dict[str, Facts]
    ) -> list[dict[str, Any]]:
        """The journal events its interests show, from the facts read (by link)."""
        ...
