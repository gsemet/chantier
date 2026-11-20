"""The external planning folder (`projects/<name>/changes/` of a planning surface), as a store."""

from __future__ import annotations

from pathlib import Path

from chantier.core.files import write_bytes
from chantier.store.base import CONFIG_FILES, LOCAL_FILES, PUBLISHES
from chantier.store.folder import FolderStore


class SurfaceStore(FolderStore):
    """The same files as `FolderStore`, and the project's configuration file beside them."""

    features = frozenset({PUBLISHES, LOCAL_FILES})

    def __init__(self, changes: Path, project: Path):
        super().__init__(changes)
        self.project = project

    @property
    def config_path(self) -> Path:
        """`chantier.yaml`, or `chantier.yml` when only that one exists."""
        yaml, yml = (self.project / n for n in CONFIG_FILES)
        return yml if yml.is_file() and not yaml.is_file() else yaml

    def write_config(self, data: bytes) -> None:
        write_bytes(self.config_path, data)
