"""A CR's title and its request's heading, checked against the limit (`validate`, `lint`)."""

from __future__ import annotations

from pathlib import Path

from chantier.core.files import heading_of, read_text, title_source
from chantier.core.records import TITLE_MAX
from chantier.core.repo import Repo
from chantier.lifecycle.layout_check import Finding, Severity
from chantier.summaries import store

REQUEST = "intake/request.md"
WRITE = (
    f'write a short "# Title" line (at most {TITLE_MAX} characters) at its top, the text below it'
)


def short_heading(text: str) -> str | None:
    """The document's `#` heading when it has one of at most `TITLE_MAX` characters, else None."""
    found = heading_of(text)
    return found if found and len(found) <= TITLE_MAX else None


def title_findings(repo: Repo, cr: Path, severity: Severity) -> list[Finding]:
    """The title rules of one CR folder: a shown title over the limit, and a request with no `#`
    heading. Read-only; a summary that cannot be read is another check's finding."""
    path = repo.rel(cr)
    found: list[Finding] = []
    try:
        summary = store.read(repo.store, cr)
    except store.UnreadableSummary:
        summary = None
    title, source = (summary.title, "summary.json") if summary and summary.title else (None, None)
    if title is None:
        title, source = title_source(repo.store, cr)
    if source and len(title) > TITLE_MAX:
        hint = f'summary set {path} --title "<at most {TITLE_MAX} characters>"'
        if source != "summary.json":
            hint = WRITE
        found.append(
            Finding(
                severity,
                f"{path}/{source}",
                f"title is {len(title)} characters: the limit is {TITLE_MAX} → {hint}",
            )
        )
    request = cr / REQUEST
    if request.is_file() and heading_of(read_text(request, "replace")) is None:
        found.append(Finding(severity, f"{path}/{REQUEST}", f'no "# " heading → {WRITE}'))
    return found
