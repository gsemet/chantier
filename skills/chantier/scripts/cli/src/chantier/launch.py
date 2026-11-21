"""The launch text of the CLI and the allow rule text that covers it: one source for what the
agents type and what P10 recommends (`plugin_files` picks the form by the mode: the install and
the session's project)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chantier.core.repo import Repo


def is_chantier_project(repo: Repo | None) -> bool:
    """Whether the session's project is chantier itself: in a planning surface, the project's
    folder is named `chantier` (no clone needed); in-project, the repository's root holds a plugin
    manifest (`.claude-plugin/plugin.json` or `.github/plugin/plugin.json`) whose `name` is
    `chantier`. No project found (None) is not chantier; neither is a manifest that cannot be read
    or parsed. A second clone or a worktree of chantier is chantier too."""
    if repo is None:
        return False
    if repo.external:
        return repo.project_folder.name == "chantier"
    for manifest in (
        repo.root / ".claude-plugin" / "plugin.json",
        repo.root / ".github" / "plugin" / "plugin.json",
    ):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("name") == "chantier":
            return True
    return False


def plugin_launch(root: Path, skill: Path) -> str:
    """The plugin form of the launch, `uvx --from "<root>" chantier --skill "<skill>"`, whatever
    the mode: a host's plugin copy runs the plugin's own folder."""
    return f'uvx --from "{root.as_posix()}" chantier --skill "{skill.as_posix()}"'


def dev_launch(root: Path) -> str:
    """The dev form of the launch, `uv run --no-sync --project "<root>" chantier`, whatever the
    mode: chantier's own checkout runs the local code."""
    return f'uv run --no-sync --project "{root.as_posix()}" chantier'


def sync_line(root: Path) -> str:
    """The dev mode's sync line, `uv sync --locked --project "<root>"`."""
    return f'uv sync --locked --project "{root.as_posix()}"'


def plugin_rule(root: Path) -> str:
    """The allow rule text of the plugin form, `uvx --from "<root>" chantier *`: the launch
    without `--skill`, then ` *`. P10 prints it and the trial proved it."""
    return f'uvx --from "{root.as_posix()}" chantier *'


def dev_rule(root: Path) -> str:
    """The allow rule text of the dev form, `uv run --no-sync --project "<root>" chantier *`."""
    return f"{dev_launch(root)} *"


def sync_rule(root: Path) -> str:
    """The allow rule text of the sync line, `uv sync --locked --project "<root>"`."""
    return sync_line(root)
