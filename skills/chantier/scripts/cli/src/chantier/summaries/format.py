"""`validate`'s reading of a `summary.json`'s format: what the board cannot read (an error) and
what is outside the limits `summary set` enforces (a gap). Each rule is the existing helper's."""

from __future__ import annotations

import re
from pathlib import Path

from chantier.core.errors import ChantierError
from chantier.core.records import (
    GROUP_MAX,
    LABEL_PATTERN,
    SUMMARY_MAX,
    SUMMARY_SCHEMA,
    TITLE_MAX,
    CrSummary,
)
from chantier.lifecycle.layout_check import Finding
from chantier.summaries import store
from chantier.summaries.edit import LABEL_RULE, one_line


def _limit(value: str | None, field: str, limit: int, always: bool = False) -> str:
    """What `summary set` says of a value outside its limits; empty when it is within them. An
    empty title or summary is the missing summary's gap, not this one's."""
    if value is None or not (value or always):
        return ""
    try:
        one_line(value, field, limit)
    except ChantierError as e:
        return str(e)
    return ""


def _gaps(summary: CrSummary, cr: str) -> list[tuple[str, str]]:
    """The (message, closing hint) of each limit the summary is outside of."""
    set_hint = f"summary set {cr} --title/--summary …"
    found = [
        (_limit(summary.title, "title", TITLE_MAX), set_hint),
        (_limit(summary.summary, "summary", SUMMARY_MAX), set_hint),
        (_limit(summary.group, "group", GROUP_MAX, True), f"summary group {cr} --name/--clear"),
    ]
    found += [
        (f"label {label!r}: {LABEL_RULE}", f"summary label {cr} --remove {label}")
        for label in summary.labels
        if not re.fullmatch(LABEL_PATTERN, label)
    ]
    found = [(message, hint) for message, hint in found if message]
    if summary.schema_version != SUMMARY_SCHEMA:
        found.append((f"schema {summary.schema_version}, this chantier reads {SUMMARY_SCHEMA}", ""))
    return found


def summary_findings(cr: str, folder: Path, in_trash: bool) -> list[Finding]:
    """The findings of one CR folder's `summary.json`; `cr` is its path in the planning folder.
    In `6-trash` no finding carries a closing hint: `summary set` refuses there."""
    path = f"{cr}/summary.json"
    try:
        summary = store.read(folder)
    except store.UnreadableSummary as e:
        hint = "" if in_trash else f", then summary set {cr} …"
        return [Finding("error", path, f"unreadable ({e.why}) → repair or remove it{hint}")]
    if summary is None:
        return []
    return [
        Finding("gap", path, f"{message} → {hint}" if hint and not in_trash else message)
        for message, hint in _gaps(summary, cr)
    ]
