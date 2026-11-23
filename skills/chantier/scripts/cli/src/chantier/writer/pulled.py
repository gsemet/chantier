"""`arrived@1`: the CRs that an integration of the upstream brought into a project's inbox or
backlog, read from git's trees (see `hub/arrivals.py`)."""

from __future__ import annotations

from typing import Any

from chantier.hub import arrivals
from chantier.writer.git_ops import Git
from chantier.writer.surface import Surface


class Pulled(Surface):
    """A mixin of `Writer`, which sets `git`."""

    git: Git

    def _stages(
        self, rev: str, elsewhere: bool = False
    ) -> dict[str, tuple[dict[str, str], set[str]]]:
        """Each project's CR folders in the tree of `rev` (slug to stage), and with `elsewhere` the
        slugs of its `4-batch`, `5-archives` and `6-trash`: the reads of git's trees, never of the
        working tree, which holds this machine's uncommitted writes."""
        names = {
            name: p.changes.resolve().relative_to(self.root.resolve()).as_posix()
            for name, p in self.projects.items()
        }
        wanted = [*arrivals.STAGES, *(arrivals.ELSEWHERE if elsewhere else ())]
        found = self.git.subfolders(rev, [f"{c}/{s}" for c in names.values() for s in wanted])
        out: dict[str, tuple[dict[str, str], set[str]]] = {}
        for name, changes in names.items():
            stages: dict[str, str] = {}
            for stage in arrivals.STAGES:
                for slug in found[f"{changes}/{stage}"]:
                    stages.setdefault(slug, stage)
            other = [n for s in arrivals.ELSEWHERE for n in found.get(f"{changes}/{s}", [])]
            out[name] = (stages, arrivals.elsewhere_slugs(other))
        return out

    def _arrived(self, base: str, theirs: str, upstream: str, keep: str | None = None) -> None:
        """Tell, with `via: pull`, each CR that `theirs` holds in an inbox or a backlog row and
        `base` did not (see `hub/arrivals.py`); with `keep`, only those that this revision also
        holds in the same folder. Only commits that exist in `theirs` and not in this machine's
        history make a line: what this machine wrote is at or below `base`."""
        if not base or not self.projects:
            return
        before, after = self._stages(base, True), self._stages(theirs)
        kept = self._stages(keep) if keep else None
        for name, repo in self.projects.items():
            found = arrivals.arrivals(before[name][0], after[name][0], before[name][1])
            if kept is not None:
                found = [a for a in found if kept[name][0].get(a.slug) == a.stage]
            for a in found:
                self._tell(arrivals.event(name, a, "pull", upstream), [repo])

    def _conflict_arrivals(self, c: dict[str, Any]) -> None:
        """Q9: the conflict ended; the CRs that its recorded upstream brought, and that the
        resolution left in the same folder, are told."""
        if c.get("local") and c.get("upstream"):
            base = self.git.merge_base(c["local"], c["upstream"])
            self._arrived(base, c["upstream"], c["upstream"], keep="HEAD")
