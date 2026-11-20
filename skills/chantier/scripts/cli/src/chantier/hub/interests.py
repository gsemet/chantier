"""The interest registry: who waits for what on a forge, so the hub reads only that.

An interest names its subject (`ref`, a PR or MR link), the facts wanted and who waits. The
registry is derived, never stored: `collect` reads the record again at each call and writes
nothing. A provider declares the interests of one kind of waiter and judges them against the facts
the hub read. Adding a kind of waiter is one module that implements `Provider` and one line in
`PROVIDERS`."""

from __future__ import annotations

import argparse
import json
from typing import Any

from chantier import connectors
from chantier.board.projects import project_name
from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.repo import Repo
from chantier.hub import batch_prs, issue_refs
from chantier.hub.interest import ISSUE, PR, Interest, Provider

__all__ = ["ISSUE", "PR", "PROVIDERS", "Interest", "Provider", "collect", "collect_each", "show"]

PROVIDERS: tuple[Provider, ...] = (batch_prs.PROVIDER, issue_refs.PROVIDER)


def collect(repo: Repo, kinds: set[str] | frozenset[str]) -> list[Interest]:
    """The interests of the providers whose kinds meet `kinds`, in order. Two interests on one
    link stay two (their `by` differ); the link is read once."""
    found: list[Interest] = []
    for provider in PROVIDERS:
        if provider.kinds & kinds:
            found.extend(i for i in provider.collect(repo) if i.kind in kinds)
    return found


def collect_each(
    repo: Repo, kinds: set[str] | frozenset[str]
) -> tuple[list[Interest], list[tuple[str, str]]]:
    """`collect`'s interests, in its order, and one `(provider name, first line of the error)` per
    provider that raised `ChantierError` or `OSError`, whose interests are then absent. Any other
    exception is a code fault and propagates."""
    found: list[Interest] = []
    failed: list[tuple[str, str]] = []
    for provider in PROVIDERS:
        if not provider.kinds & kinds:
            continue
        try:
            found.extend(i for i in provider.collect(repo) if i.kind in kinds)
        except (ChantierError, OSError) as e:
            failed.append((provider.name, (str(e).splitlines() or [type(e).__name__])[0]))
    return found, failed


def _line(i: Interest) -> str:
    """The text line of one interest."""
    if i.kind == ISSUE:
        return f"issue {i.ref} ({i.tracker or 'other'}): events for {i.by}"
    connector = connectors.connector_for(i.ref)
    return (
        f"pr {i.ref} ({connector.name if connector else 'no connector'}): "
        f"{', '.join(sorted(i.facts))} for {i.by}"
    )


def _record(i: Interest) -> dict[str, Any]:
    """The JSON form of one interest."""
    out: dict[str, Any] = {
        "kind": i.kind,
        "ref": i.ref,
        "facts": sorted(i.facts),
        "by": i.by,
        "read_by": "outside" if i.kind == ISSUE else "hub",
    }
    if i.kind == ISSUE:
        out["tracker"] = i.tracker or "other"
    else:
        connector = connectors.connector_for(i.ref)
        out["connector"] = connector.name if connector else None
    return out


def show(args: argparse.Namespace) -> tuple[list[str], int]:
    """`chantier interests`: what the CRs wait for, read-only. Exit 2 when a provider failed,
    after printing the others (the list is incomplete)."""
    repo = Repo.find(readonly=True)
    kinds = {args.kind} if args.kind else {PR, ISSUE}
    found, failed = collect_each(repo, kinds)
    code = EXIT_PRECONDITION if failed else 0
    project = project_name(repo)
    if args.json:
        data = {
            "schema": 1,
            "project": project,
            "interests": [_record(i) for i in found],
            "errors": [{"provider": n, "text": t} for n, t in failed],
        }
        return [json.dumps(data, sort_keys=True, ensure_ascii=False)], code
    nothing = " (nothing awaited)" if not found and not failed else ""
    return [
        f"interests of {project}: {len(found)}{nothing}",
        *map(_line, found),
        *(f"interests: {n} not read: {t}" for n, t in failed),
    ], code
