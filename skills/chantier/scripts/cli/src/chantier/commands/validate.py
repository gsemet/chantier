"""`validate`: check a whole planning folder, read-only. Errors are what chantier or the board
misreads (exit 3); gaps are to fix and pass (exit 0); a folder it cannot find is exit 1."""

from __future__ import annotations

import argparse

from chantier.core.errors import EXIT_CONFLICT, EXIT_USAGE, ChantierError
from chantier.core.repo import Repo
from chantier.lifecycle.layout_check import Finding, Severity, placement, shape, stage_crs
from chantier.lifecycle.links import broken_links
from chantier.lifecycle.stages import PRIORITIES, stage_layout
from chantier.summaries.format import summary_findings
from chantier.summaries.gaps import gap_line, gap_of
from chantier.summaries.title import title_findings


def _planning_folder() -> Repo:
    """The planning folder's repository, written nowhere; whatever stops it is exit 1, so a
    caller never takes a refusal for a pass or a gap."""
    try:
        repo = Repo.find(readonly=True)
    except ChantierError as e:
        raise ChantierError(str(e), EXIT_USAGE) from e
    if not repo.changes.is_dir():
        raise ChantierError(f"no planning folder at {repo.changes}", EXIT_USAGE)
    return repo


def findings(repo: Repo) -> tuple[list[Finding], int]:
    """Every finding, and the number of CR folders found in every stage."""
    live, closed = stage_crs(repo)
    paths = stage_layout(repo)
    trash = paths["trash"]
    found = [*placement(repo), *shape(repo), *broken_links(repo)]
    unbatched = {paths["inbox"], paths["ready"], *(paths["backlog"] / p for p in PRIORITIES)}
    for cr in [*live, *closed]:
        found += summary_findings(repo.store, repo.rel(cr), cr, cr.parent == trash)
        # a CR not yet in a batch must have a short title; later ones are history
        severity: Severity = "error" if cr.parent in unbatched else "gap"
        for f in title_findings(repo, cr, severity):
            # `summary set` and the files' edits are refused in `6-trash`: no closing hint there
            text = f.text.partition(" → ")[0] if cr.parent == trash else f.text
            found.append(Finding(f.severity, f.path, text))
    for cr in live:
        gap = gap_of(repo.store, cr)  # None for a folder with no covered file
        if gap and gap.kind not in ("unreadable", "no heading", "long title"):
            path, _, text = gap_line(repo, gap).partition(": ")
            found.append(Finding("gap", path, text))
    return found, len(live) + len(closed)


def validate(args: argparse.Namespace) -> tuple[list[str], int]:
    """The counts line, then every error and every gap, each group sorted by path."""
    found, crs = findings(_planning_folder())
    errors = sorted((f for f in found if f.severity == "error"), key=lambda f: (f.path, f.text))
    gaps = sorted((f for f in found if f.severity == "gap"), key=lambda f: (f.path, f.text))
    if errors:
        head = f"{len(errors)} error(s), {len(gaps)} gap(s) in {crs} CRs"
    elif gaps:
        head = f"{len(gaps)} gap(s) in {crs} CRs"
    else:
        head = f"no error, no gap ({crs} CRs)"
    return [head, *(f.line() for f in [*errors, *gaps])], EXIT_CONFLICT if errors else 0
