"""The edits of a CR's summary that need no agent: labels and group. The `summary` command and the
board's server both call these, with a `Repo` and the CR folders; none touches `sources` or
`summarized`, so a label or a group never makes a summary fresh or late."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from pathlib import Path

from chantier.core.errors import EXIT_USAGE, ChantierError
from chantier.core.records import GROUP_MAX, LABEL_PATTERN, CrSummary
from chantier.core.repo import Repo
from chantier.lifecycle.filing import shown
from chantier.lifecycle.stages import changes_lock
from chantier.summaries import store


def one_line(value: str, field: str, limit: int) -> str:
    """A value of one line of plain text, not empty, within its limit."""
    if any(unicodedata.category(c) == "Cc" for c in value):
        raise ChantierError(
            f"{field} is one line of plain text: no newline or other control character",
            EXIT_USAGE,
        )
    text = value.strip()
    if not text:
        raise ChantierError(f"{field} must not be empty", EXIT_USAGE)
    if len(text) > limit:
        raise ChantierError(f"{field} is {len(text)} characters: the limit is {limit}", EXIT_USAGE)
    return text


def label_set(raw: str) -> set[str]:
    """Comma-separated labels, lowercased and checked."""
    labels = {part.strip().lower() for part in raw.split(",") if part.strip()}
    bad = sorted(x for x in labels if not re.fullmatch(LABEL_PATTERN, x))
    if bad or not labels:
        raise ChantierError(
            f"a label is lowercase letters, digits and hyphens, 24 characters at most, "
            f"starting with a letter or digit: {', '.join(bad) or 'none given'}",
            EXIT_USAGE,
        )
    return labels


def edit_all(
    repo: Repo,
    folders: list[Path],
    edit: Callable[[CrSummary], None],
    show: Callable[[str, CrSummary], str],
) -> list[str]:
    """Apply one edit to several CRs' summaries under one lock: all are read before any is
    written."""
    folders = list(dict.fromkeys(folders))
    with changes_lock(repo):
        loaded = [(folder, store.read_or_new(folder)) for folder in folders]
        for folder, summary in loaded:
            edit(summary)
            store.write(folder, summary)
    return [show(shown(repo, folder), summary) for folder, summary in loaded]


def change_labels(
    repo: Repo, folders: list[Path], add: set[str], remove: set[str] | None = None
) -> list[str]:
    """Add and remove labels on CRs."""
    gone = remove or set()

    def edit(summary: CrSummary) -> None:
        summary.labels = sorted((set(summary.labels) | add) - gone)

    return edit_all(
        repo, folders, edit, lambda path, s: f"labels {path}: {', '.join(s.labels) or 'none'}"
    )


def change_group(repo: Repo, folders: list[Path], name: str | None) -> list[str]:
    """Put CRs in one group (checked), or take them out of theirs when `name` is None."""
    group = None if name is None else one_line(name, "group", GROUP_MAX)

    def edit(summary: CrSummary) -> None:
        if group is None:
            summary.unset("group")
        else:
            summary.group = group

    return edit_all(repo, folders, edit, lambda path, s: f"group {path}: {s.group or 'none'}")
