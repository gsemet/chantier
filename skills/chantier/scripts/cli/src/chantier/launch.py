"""The launch text of the CLI and the allow rule text that covers it: one source for what the
agents type and what P10 recommends (`plugin_files` picks the form by the mode: the install and
the session's project). Standard library only: the plugin's launcher (`launcher.py`) imports it
before any dependency is installed."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chantier.core.repo import Repo

LAUNCHER = Path("skills/chantier/scripts/chantier.py")  # the launcher, from the plugin root


def _manifest_names_chantier(root: Path) -> bool:
    """Whether `root` holds a plugin manifest (`.claude-plugin/plugin.json` or
    `.github/plugin/plugin.json`) whose `name` is `chantier`; one that cannot be read or parsed
    does not."""
    for manifest in (
        root / ".claude-plugin" / "plugin.json",
        root / ".github" / "plugin" / "plugin.json",
    ):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("name") == "chantier":
            return True
    return False


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
    return _manifest_names_chantier(repo.root)


def _git_out(cwd: Path, *args: str) -> str | None:
    """A read-only git call's output, stripped; None when it fails or prints nothing."""
    try:
        done = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except OSError:
        return None
    out = done.stdout.strip()
    return out if done.returncode == 0 and out else None


def _surface_projects(root: Path) -> list[str]:
    """The projects of a planning surface at `root` (as `core.repo.surface_projects`): the folders
    of `projects/` that hold `checkout.yml` or `changes/`."""
    base = root / "projects"
    if not base.is_dir():
        return []
    return sorted(
        d.name for d in base.iterdir() if (d / "checkout.yml").is_file() or (d / "changes").is_dir()
    )


def session_project(cwd: Path, project: str | None) -> tuple[bool, Path | None]:
    """The launcher's reading of the session's project, with no `Repo`: whether it is chantier
    (what `is_chantier_project(Repo.find(cwd, project))` answers) and the project's folder in a
    planning surface (None in-project, or when no single project is found). `CHANTIER_ROOT`, when
    set, replaces `cwd`, as in `Repo.find`. Read-only git calls only."""
    cwd = Path(os.environ.get("CHANTIER_ROOT") or cwd)
    if project:
        folder = Path(project).expanduser()
        if not folder.is_absolute():
            if len(folder.parts) == 1:  # a bare name, in the surface the session is in
                top = _git_out(cwd, "rev-parse", "--show-toplevel")
                folder = Path(top or cwd) / "projects" / folder
            else:
                folder = cwd / folder
        folder = folder.resolve()
        return folder.name == "chantier", folder
    common = _git_out(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if common is None:
        return False, None
    root = Path(common).resolve().parent
    names = [] if (root / ".agents" / "changes").is_dir() else _surface_projects(root)
    if len(names) > 1:  # the CLI refuses with its `--project` line
        return False, None
    if names:
        return names[0] == "chantier", (root / "projects" / names[0]).resolve()
    return _manifest_names_chantier(root), None


def project_is_chantier(cwd: Path, project: str | None) -> bool:
    """The launcher's half of the mode rule: whether the session's project, from the working
    folder `cwd` and the `--project` value, is chantier (see `session_project`)."""
    return session_project(cwd, project)[0]


def launcher_line(root: Path) -> str:
    """The launcher's form, `uv run --script "<root>/skills/chantier/scripts/chantier.py"`."""
    return f'uv run --script "{(root / LAUNCHER).as_posix()}"'


def launcher_rule(root: Path) -> str:
    """The allow rule text of the launcher, `uv run --script "<launcher>" *`."""
    return f"{launcher_line(root)} *"


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


def sync_check_line(root: Path) -> str:
    """The dev mode's check line, `uv sync --locked --check --project "<root>"`: it writes nothing,
    exits 0 when the environment is in sync and 1 when it is outdated (or `uv.lock` stale)."""
    return f'uv sync --locked --check --project "{root.as_posix()}"'


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


def sync_check_rule(root: Path) -> str:
    """The allow rule text of the check line, `uv sync --locked --check --project "<root>"`."""
    return sync_check_line(root)
