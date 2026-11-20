"""The parser of the `interests` command; the handler loads when it runs."""

from __future__ import annotations

from chantier.commands.registry import NO_BATCH, Subparsers, add_command

HELP = (
    "what the CRs of this project wait for: the running batch's PRs or MRs, which the forge hub "
    "reads, and the issues the CRs' issue: lines name, which only an outside poller reads; "
    "--json is the poller's input"
)


def register(sub: Subparsers) -> None:
    """Declare `interests`."""
    s = add_command(sub, "interests", "chantier.hub.interests:show", HELP, NO_BATCH)
    s.add_argument("--kind", choices=("pr", "issue"), help="only this kind of interest")
    s.add_argument("--json", action="store_true", help="one JSON object, one line")
