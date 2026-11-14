"""Where a CR's request came from, read from the `issue:` line of its intent or specification."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

from chantier.core.errors import EXIT_USAGE, ChantierError
from chantier.core.files import read_text
from chantier.core.records import Origin

ISSUE_FILES = ("01-intent.md", "03-change-spec.md")
ISSUE_LINE = re.compile(r"^issue:\s*(\S+)", re.MULTILINE)
JIRA_KEY = re.compile(r"/browse/([A-Za-z][A-Za-z0-9_]*-\d+)")
NUMBER = re.compile(r"\d+")


def issue_url(folder: Path) -> str | None:
    """The link of the CR's `issue:` line: the first one in the intent, else in the
    specification."""
    for name in ISSUE_FILES:
        path = folder / name
        if path.is_file():
            found = ISSUE_LINE.search(read_text(path, errors="replace"))
            if found:
                return found[1]
    return None


def _kind_of(host: str, path: str) -> str | None:
    """The tracker a URL names, by these rules in order: a Jira `/browse/` key, a GitLab path or
    host, a GitHub host or path."""
    if JIRA_KEY.search(path):
        return "jira"
    if "/-/issues/" in path or "gitlab" in host:
        return "gitlab"
    if host == "github.com" or host.endswith(".github.com"):
        return "github"
    if "github" in host and re.search(r"/issues/\d+", path):
        return "github"
    return None


def _ref_of(kind: str, path: str) -> str | None:
    """The issue's short reference: a Jira key, or `#<last number of the path>`."""
    if kind == "jira":
        found = JIRA_KEY.search(path)
        return found[1] if found else None
    numbers = NUMBER.findall(path)
    return f"#{numbers[-1]}" if numbers else None


def origin_of(url: str | None, tracker: str | None = None) -> Origin:
    """The origin of a CR from its `issue:` link: verbal with no link. A link the rules cannot
    place needs `tracker`; `tracker` with no link is refused."""
    if url is None:
        if tracker:
            raise ChantierError(
                "--tracker needs an `issue:` line: write the line in the CR's intent first",
                EXIT_USAGE,
            )
        return Origin(kind="verbal")
    parts = urlsplit(url)
    host, path = (parts.hostname or "").lower(), parts.path
    kind = tracker or _kind_of(host, path)
    if kind is None:
        raise ChantierError(
            "the issue: line's tracker is not known from its URL: add --tracker github|gitlab|jira",
            EXIT_USAGE,
        )
    ref = _ref_of(kind, path)
    if ref is None:
        raise ChantierError(f"no {kind} issue number or key in the issue: URL {url}", EXIT_USAGE)
    return Origin(kind=kind, ref=ref, url=url)
