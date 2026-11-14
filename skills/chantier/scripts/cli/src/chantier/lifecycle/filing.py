"""Filing a request: a path as shown to the user, a slug from a title, a new inbox folder."""

from __future__ import annotations

import re
from pathlib import Path

from chantier.core.errors import EXIT_EXTERNAL, EXIT_PRECONDITION, ChantierError
from chantier.core.repo import Repo
from chantier.lifecycle.stages import stage_layout


def shown(repo: Repo, path: Path) -> str:
    try:
        return path.relative_to(repo.session_root).as_posix()
    except ValueError:
        return path.as_posix()


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "cr"


def new_request(
    repo: Repo, slug: str, raw: bytes, hint: str = "file it again with --slug <other>"
) -> Path:
    """A new inbox folder, the request kept as received. The caller holds `changes_lock`."""
    folder = stage_layout(repo)["inbox"] / slug
    folder.parent.mkdir(parents=True, exist_ok=True)
    try:
        folder.mkdir()
    except FileExistsError as e:
        raise ChantierError(
            f"CR folder already exists: {shown(repo, folder)}; {hint}", EXIT_PRECONDITION
        ) from e
    try:
        (folder / "intake").mkdir()
        (folder / "intake" / "request.md").write_bytes(raw)
    except OSError as e:
        raise ChantierError(
            f"could not finish filing {folder}; preserve it for recovery: {e}", EXIT_EXTERNAL
        ) from e
    return folder
