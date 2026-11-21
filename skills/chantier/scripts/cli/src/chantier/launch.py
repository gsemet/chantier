"""The launch text of the CLI and the allow rule text that covers it: one source for what the
agents type and what P10 recommends (`plugin_files` picks the form by the mode of the install)."""

from __future__ import annotations

from pathlib import Path


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
