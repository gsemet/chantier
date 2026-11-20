"""The Driver's `note` and `phase`: what it records in its CR's state between rounds."""

from __future__ import annotations

import argparse
from pathlib import Path

from chantier.commands.driver import context_line
from chantier.core import leases
from chantier.core.batch import find_cr_batch
from chantier.core.clock import now
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.phases import PHASE_DETAIL_MAX
from chantier.core.records import LIVE
from chantier.core.repo import Repo
from chantier.lifecycle.session import RenderedBatch


def note(args: argparse.Namespace) -> list[str]:
    """A Driver's or worker's line in the CR's state: what was done or found, shown in its
    STATUS.md. `--draft <path>` names a file the user reviews and edits in place."""
    repo = Repo.find()
    text = " ".join(args.text).strip()
    if not text and not args.draft:
        raise ChantierError("note <cr> <text> | note <cr> --draft <path>", EXIT_USAGE)
    with RenderedBatch(repo, find_cr_batch(repo, args.cr, args.batch), actor="driver") as b:
        c = b.cr(args.cr)
        leases.claim(b, c.id, args.lease, what=f"note {c.id}", required=False)
        if args.draft:
            path = Path(args.draft).expanduser()
            if not path.is_file():
                raise ChantierError(
                    f"note --draft <path of an existing file>, not {args.draft!r}", EXIT_USAGE
                )
            draft = path.resolve().as_posix()
            if draft not in c.drafts:
                c.append("drafts", draft)
            text = text or f"draft: {draft}"
        c.append("notes", text)
        b.touch(c)
        b.log("note", args.cr, note=text)
        context = context_line(repo, b.record, c.agent)
    return ["ok", context]


def phase(args: argparse.Namespace) -> list[str]:
    """A Driver records the step its CR is at, shown by the status, the board and the pane."""
    repo = Repo.find()
    detail = " ".join(args.detail).strip()
    if len(detail) > PHASE_DETAIL_MAX:
        raise ChantierError(
            f"phase: the detail is at most {PHASE_DETAIL_MAX} characters", EXIT_PRECONDITION
        )
    if args.phase == "review" and not detail:
        raise ChantierError("phase <cr> review <the review step's name>", EXIT_PRECONDITION)
    with RenderedBatch(repo, find_cr_batch(repo, args.cr, args.batch), actor="driver") as b:
        c = b.cr(args.cr)
        if c.status not in LIVE:
            raise ChantierError(
                f"{c.id} is {c.status}: no Driver to record a step", EXIT_PRECONDITION
            )
        leases.claim(b, c.id, args.lease, what=f"phase {c.id}", required=False)
        keeps = args.phase in {"review", "gate", "release"}
        b.touch(c, phase=args.phase, phase_at=now())
        if keeps and detail:
            c.phase_detail = detail
        else:
            c.unset("phase_detail")
        b.log("phase", c.id, phase=args.phase, note=detail or None)
        context = context_line(repo, b.record, c.agent)
    return ["ok", context]
