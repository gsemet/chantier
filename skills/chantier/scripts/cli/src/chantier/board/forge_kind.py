"""Which forge a project uses, for the board's words ("PR" or "MR"): told from the shape of its
PR links, else from the host of its `origin` remote. No network, no write."""

from __future__ import annotations

from typing import Any

from chantier.commands.forge_stack_gitlab import GITLAB_LINK


def _links(state: dict[str, Any]) -> list[str]:
    """Every PR link of the record: the batch's CRs and every history record's CRs."""
    crs = list((state.get("batch") or {}).get("crs") or [])
    for record in state.get("history") or []:
        crs.extend(record.get("crs") or [] if isinstance(record, dict) else [])
    return [
        c["pr"] for c in crs if isinstance(c, dict) and isinstance(c.get("pr"), str) and c["pr"]
    ]


def forge_of(state: dict[str, Any], origin: str) -> str | None:
    """`gitlab` when a PR link of the record is a GitLab MR link; `github` when links are there
    and none is; with no link, `gitlab` or `github` when the `origin` URL's host says so, else
    None. The link's shape wins over the host."""
    links = _links(state)
    if links:
        return "gitlab" if any(GITLAB_LINK.match(link) for link in links) else "github"
    host = origin.lower()
    if "gitlab" in host:
        return "gitlab"
    return "github" if "github" in host else None
