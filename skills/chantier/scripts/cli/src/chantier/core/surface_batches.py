"""The other batches of a planning surface, read from the projects' folders: no lock, no git
call, nothing written. A session sees them, with the Drivers each runs; none is refused."""

from __future__ import annotations

from chantier.core.errors import ChantierError
from chantier.core.files import rel_in
from chantier.core.repo import Repo, surface_projects
from chantier.store import SurfaceStore


def _one(name: str, repo: Repo) -> str | None:
    from chantier import rails  # noqa: PLC0415 - lazy pydantic
    from chantier.core.records import read_batch_json  # noqa: PLC0415
    from chantier.status.words import steering_word  # noqa: PLC0415

    folder = repo.surface_root / "projects" / name
    store = SurfaceStore(folder / "changes", folder, repo.git_dir)  # building creates no file
    path = store.root / "4-batch" / "batch.json"
    if not store.is_file(rel_in(store.root, path)):
        return None
    try:
        d = read_batch_json(store, path)
    except (ChantierError, OSError, ValueError):
        return f"{name}: batch.json unreadable"
    state = "closing" if d.closing else d.status
    drivers = len(rails.held(d)) + (1 if d.stack_agent else 0)
    return (
        f"{name} {d.id} {state}, steering {steering_word(d.steering)}, "
        f"{drivers} Driver{'' if drivers == 1 else 's'}" + (", factory on" if d.factory else "")
    )


def other_batches(repo: Repo) -> str | None:
    """`other batches on this surface: ...`, one line, by project; None in-project or when no
    other project holds a batch."""
    if not repo.external:
        return None
    own = repo.project_folder.name
    found = [
        line
        for name in surface_projects(repo.surface_root)
        if name != own and (line := _one(name, repo))
    ]
    return f"other batches on this surface: {'; '.join(found)}" if found else None
