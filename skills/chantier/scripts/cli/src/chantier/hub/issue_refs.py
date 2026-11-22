"""The provider `issues`: the issues the CRs' `issue:` lines name, as interests of kind `issue`.

Only an outside poller reads them (`chantier interests`, then `chantier journal add`): the forge
hub never collects this provider. It reads the CR folders of every stage but `5-archives` and
`6-trash`, writes nothing, takes no lock and needs no network."""

from __future__ import annotations

from typing import Any

from chantier.connectors.base import Facts
from chantier.core.repo import Repo
from chantier.hub.interest import ISSUE, Interest
from chantier.lifecycle.stages import cr_folders, stage_layout
from chantier.summaries.origin import issue_url, tracker_of

EVENTS = frozenset({"events"})


class Issues:
    name = "issues"
    kinds = frozenset({ISSUE})

    def collect(self, repo: Repo) -> list[Interest]:
        """One interest per CR folder with an `issue:` line, in the lifecycle's order. A file it
        cannot read (`OSError`) is a failure of the provider."""
        found: list[Interest] = []
        changes = repo.changes.resolve()
        for folder in cr_folders(repo.store, stage_layout(repo)):
            url = issue_url(repo.store, folder)
            if url is None:
                continue
            by = folder.relative_to(changes).as_posix()
            found.append(Interest(ISSUE, url, EVENTS, by, self.name, tracker_of(url) or "other"))
        return found

    def judge(
        self, repo: Repo, interests: list[Interest], facts: dict[str, Facts]
    ) -> list[dict[str, Any]]:
        return []


PROVIDER = Issues()
