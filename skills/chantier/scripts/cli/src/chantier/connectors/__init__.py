"""Forge connectors: the modules that read a forge, read-only, through the user's own program.

`CONNECTORS` is the plugin table: a connector is one module that implements `base.Connector` and
one line here. `read` is the one test seam of every forge read (the forge hub, the PRs page)."""

from __future__ import annotations

from chantier.commands.forge_stack_shared import NOT_ONE_REPOSITORY
from chantier.connectors.base import OPTIONAL_FACTS, Connector, Facts
from chantier.connectors.github import CONNECTOR as GITHUB
from chantier.connectors.gitlab import CONNECTOR as GITLAB
from chantier.core.errors import EXIT_PRECONDITION, ChantierError

CONNECTORS: tuple[Connector, ...] = (GITHUB, GITLAB)
UNCLAIMED = "no connector reads {link}: chantier reads GitHub and GitLab"

__all__ = ["CONNECTORS", "OPTIONAL_FACTS", "UNCLAIMED", "Facts", "connector_for", "read"]


def connector_for(link: str) -> Connector | None:
    """The first connector that claims the link, else None."""
    return next((c for c in CONNECTORS if c.claims(link)), None)


def read(links: list[str], facts: frozenset[str] = frozenset()) -> dict[int, Facts]:
    """Every PR or MR of `links` in one forge call, by number. Every link must be claimed by a
    connector and all of one repository; no fallback. The one test seam of the forge reads."""
    found = [(link, connector_for(link)) for link in links]
    for link, connector in found:
        if connector is None:
            raise ChantierError(UNCLAIMED.format(link=link), EXIT_PRECONDITION)
    pairs = [(c, link) for link, c in found if c is not None]
    places = {c.place(link) for c, link in pairs}
    if len(places) != 1:
        raise ChantierError(NOT_ONE_REPOSITORY, EXIT_PRECONDITION)
    connector = pairs[0][0]
    numbers = sorted({connector.number(link) for _, link in pairs})
    return connector.read(next(iter(places)), numbers, facts)
