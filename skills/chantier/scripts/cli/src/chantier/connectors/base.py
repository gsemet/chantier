"""What a forge connector is: the shapes it reads into and the interface it implements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

# One PR or MR as the board judges it: `state`, `conflicting`, `checking`, `checks`, `base`,
# `head`, `merged_on_default`, `merged_at`, `closed_at`, `opened_at`, `updated_at`, and `review`
# when it was asked.
Facts = dict[str, Any]

OPTIONAL_FACTS = frozenset({"review"})  # the facts a read adds only when asked


@dataclass(frozen=True)
class Place:
    """One forge repository: the unit of one query."""

    connector: str
    host: str
    repository: str


class Connector(Protocol):
    """A module that reads one forge, read-only."""

    name: str  # `github`, `gitlab`
    program: str  # `gh`, `glab`: the user's own, on PATH
    word: str  # `PR`, `MR`

    def claims(self, link: str) -> bool:
        """Whether the link is one of this forge's review requests."""
        ...

    def place(self, link: str) -> Place: ...

    def number(self, link: str) -> int: ...

    def read(self, place: Place, numbers: list[int], facts: frozenset[str]) -> dict[int, Facts]:
        """Exactly one call of the program, read-only, for every number; `facts` is the set of
        optional facts asked."""
        ...
