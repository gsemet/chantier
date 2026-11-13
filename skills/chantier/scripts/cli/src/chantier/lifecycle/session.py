"""The batch's record saved and its STATUS files rewritten: what every command that changes it
uses."""

from __future__ import annotations

from chantier.core.batch import Batch
from chantier.lifecycle.stages import stage_layout
from chantier.status.write import write_batch, write_dashboard


class RenderedBatch(Batch):
    """A `Batch` that rewrites its STATUS files and the dashboard after each saved change."""

    def after_save(self) -> None:
        write_batch(self.repo, self.record, self.dir)
        write_dashboard(self.repo, stage_layout(self.repo))
