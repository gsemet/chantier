"""`order merged`, before its record: check, then stop the CR's running gate and wait for it."""

from __future__ import annotations

import argparse

from chantier.commands.gate_run import stop_and_wait, stopped_line
from chantier.commands.orders_apply import check_merged
from chantier.core.batch import check_epoch, resolve_batch
from chantier.core.files import LOCK_TIMEOUT_S
from chantier.core.repo import Repo
from chantier.gate_slots import slot_of
from chantier.lifecycle.session import RenderedBatch
from chantier.lifecycle.stages import changes_lock

STOP_WAIT_S: float = LOCK_TIMEOUT_S  # how long the order waits for a stopped gate to end


def stop_before_merge(repo: Repo, args: argparse.Namespace, actor: str) -> list[str]:
    """Steps 1 and 2 of `order merged <cr>`: under the locks, the order's refusals, changing
    nothing; then, with the locks released (the stopped gate needs the batch lock to log its
    `stopped`), stop the CR's running gate and wait for its command to end, so the folder moves
    with no process on it. Returns the line of the gate it stopped, none when it stopped none."""
    cr_id = args.cr
    with (
        changes_lock(repo),
        RenderedBatch(repo, resolve_batch(repo, args.batch), actor=actor) as b,
    ):
        check_epoch(b, args.epoch)
        if check_merged(b, b.cr(cr_id)):
            return []
    v = slot_of(repo, cr_id)
    if v is None or v.holder is None:
        return []
    s = stop_and_wait(repo.store, v.slot, v.holder, STOP_WAIT_S)
    if s is None:
        return []
    return [stopped_line(cr_id, s.pg)]
