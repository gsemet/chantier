"""The interest registry: who waits for what on a forge, so the hub reads only that.

An interest names its subject (`ref`, a PR or MR link), the facts wanted and who waits. The
registry is derived, never stored: `collect` reads the record again at each call and writes
nothing. A provider declares the interests of one kind of waiter and judges them against the facts
the hub read. Adding a kind of waiter is one module that implements `Provider` and one line in
`PROVIDERS`."""

from __future__ import annotations

from chantier.core.repo import Repo
from chantier.hub import batch_prs
from chantier.hub.interest import PR, Interest, Provider

__all__ = ["PR", "PROVIDERS", "Interest", "Provider", "collect"]

PROVIDERS: tuple[Provider, ...] = (batch_prs.PROVIDER,)


def collect(repo: Repo, kinds: set[str] | frozenset[str]) -> list[Interest]:
    """The interests of the providers whose kinds meet `kinds`, in order. Two interests on one
    link stay two (their `by` differ); the link is read once."""
    found: list[Interest] = []
    for provider in PROVIDERS:
        if provider.kinds & kinds:
            found.extend(i for i in provider.collect(repo) if i.kind in kinds)
    return found
