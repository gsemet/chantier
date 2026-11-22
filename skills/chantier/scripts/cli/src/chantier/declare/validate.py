"""The parser of the `validate` command; the handler loads when it runs."""

from __future__ import annotations

from chantier.commands.registry import NO_BATCH, Subparsers, add_command


def register(sub: Subparsers) -> None:
    """Declare `validate`."""
    add_command(
        sub,
        "validate",
        "chantier.commands.validate:validate",
        "check the whole planning folder: stages, CR folders, outside archives' names, "
        "summary.json's format, missing or "
        "late summaries, broken links, a planning surface's chantier.yaml naming a long gate's "
        "command (ignored: a gap); exit 0 with gaps, 3 on errors, 1 when it cannot run",
        NO_BATCH,
    )
