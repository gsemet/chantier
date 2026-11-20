"""The external planning folder (`projects/<name>/changes/` of a planning surface), as a store."""

from __future__ import annotations

from pathlib import Path

from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.files import write_bytes
from chantier.store.base import (
    CONFIG_FILES,
    LOCAL_FILES,
    PUBLISHES,
    REFUSES_WITHOUT_PUBLISHER,
    is_published,
)
from chantier.store.folder import FolderStore
from chantier.writer import lines


class SurfaceStore(FolderStore):
    """The same files as `FolderStore`, the project's configuration file beside them, and the
    refusal of a published write while the surface's writer does not run (its `writer` entry in
    the surface's git folder)."""

    features = frozenset({PUBLISHES, LOCAL_FILES, REFUSES_WITHOUT_PUBLISHER})

    def __init__(self, changes: Path, project: Path, git_dir: Path):
        super().__init__(changes)
        self.project = project
        self.git_dir = git_dir

    def check_publish(
        self, rels: list[str], *, config: bool = False, command: str | None = None
    ) -> None:
        """The paths stay in the folder; a published path, or the configuration, needs a live
        writer: with none, exit 2 and nothing changes. One look at the entry per call."""
        super().check_publish(rels, config=config, command=command)
        if not (config or any(is_published(rel) for rel in rels)):
            return
        if lines.refused(self.git_dir):
            raise ChantierError(
                lines.refusal(command or "chantier", self.git_dir), EXIT_PRECONDITION
            )
        lines.wrote(self.git_dir)  # the command's output says whether the writer pushed it

    @property
    def config_path(self) -> Path:
        """`chantier.yaml`, or `chantier.yml` when only that one exists."""
        yaml, yml = (self.project / n for n in CONFIG_FILES)
        return yml if yml.is_file() and not yaml.is_file() else yaml

    def write_config(self, data: bytes) -> None:
        write_bytes(self.config_path, data)
