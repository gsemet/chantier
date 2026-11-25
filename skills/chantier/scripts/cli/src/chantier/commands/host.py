"""`chantier host`: how the host does a capability, read-only. It writes nothing and reads no
network."""

from __future__ import annotations

import argparse
import os

from chantier.core.batch import read_batch, resolve_batch
from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.repo import Repo
from chantier.host_rows import load_rows, row_lines
from chantier.plugin_files import detect_host


def _batch_host(args: argparse.Namespace) -> tuple[str, str]:
    """The host and its label: the batch's recorded host when a batch resolves, else the
    session's."""
    try:
        repo = Repo.find(readonly=True)
    except ChantierError:
        return detect_host(), "this session"
    named = args.batch or os.environ.get("CHANTIER_BATCH")
    if not named and not repo.open_batches() and not repo.paused_batches():
        return detect_host(), "this session"
    batch = resolve_batch(repo, args.batch, paused=True)
    record = read_batch(repo, batch)
    if record.host:
        return record.host, batch
    return detect_host(), batch


def host(args: argparse.Namespace) -> list[str]:
    name, label = _batch_host(args)
    rows = load_rows(name)
    out = [f"host: {name} ({label})"]
    if args.capability:
        found = [r for r in rows if r.capability == args.capability]
        if not found:
            raise ChantierError(
                f"unknown capability `{args.capability}` on {name}: one of "
                + ", ".join(r.capability for r in rows),
                EXIT_PRECONDITION,
            )
        return out + row_lines(found[0])
    for i, r in enumerate(rows):
        if i:
            out.append("")
        out += row_lines(r)
    return out
