"""Whether a planning surface names an autosync, and where its files are."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from chantier.core.files import read_text
from chantier.core.repo import Repo
from chantier.plugin_files import surface_instructions

GUIDELINES = ".agents/guidelines/autosync.guidelines.md"
SCRIPT = "scripts/ai-autosync-git.py"
STATE_FOLDER = "ai-autosync"


@dataclass(frozen=True)
class AutosyncSite:
    """The surface's autosync: its checkout, its script, and the folder its tool keeps state in."""

    surface: Path
    script: Path
    guidelines: str
    state_dir: Path
    script_missing: bool


def find_site(repo: Repo) -> AutosyncSite | None:
    """The surface's autosync, when the planning folder is external, the surface's rules name the
    tool's guidelines, and (else `script_missing`) its script is there. None otherwise."""
    rules = surface_instructions(repo)
    if rules is None:
        return None
    try:
        named = GUIDELINES in read_text(rules, errors="replace")
    except OSError:
        return None
    if not named:
        return None
    script = repo.surface_root / SCRIPT
    return AutosyncSite(
        surface=repo.surface_root,
        script=script,
        guidelines=GUIDELINES,
        state_dir=repo.git_dir / STATE_FOLDER,
        script_missing=not script.is_file(),
    )
