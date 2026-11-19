"""Running git, and the remote's default branch."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from chantier.core.errors import EXIT_EXTERNAL, EXIT_PRECONDITION, ChantierError


def git(*args: str, cwd: Path | str | None = None, check: bool = True) -> str:
    env = {**os.environ, "GIT_EDITOR": "true", "GIT_PAGER": "cat", "GIT_TERMINAL_PROMPT": "0"}
    if cwd is not None and not Path(cwd).is_dir():
        raise ChantierError(f"no folder {cwd}: git cannot run there", EXIT_PRECONDITION)
    p = subprocess.run(
        ["git", "--no-pager", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )
    if check and p.returncode != 0:
        raise ChantierError(
            f"git {' '.join(args)}: {p.stderr.strip() or p.stdout.strip()}", EXIT_EXTERNAL
        )
    return p.stdout.strip()


def default_branch(root: Path, remote: str = "origin") -> str | None:
    """The remote's recorded HEAD branch, if Git knows it."""
    head = git("symbolic-ref", "--short", f"refs/remotes/{remote}/HEAD", cwd=root, check=False)
    return head.removeprefix(f"{remote}/") if head else None


def branch_exists(branch: str, cwd: Path | str | None = None) -> bool:
    """A read: whether the local branch exists."""
    if not branch:
        return False
    return bool(
        git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", cwd=cwd, check=False)
    )


def refusal(*args: str, cwd: Path | str | None = None) -> str | None:
    """Run git; None when it succeeded, else its message on one line (nothing is forced)."""
    try:
        git(*args, cwd=cwd)
    except ChantierError as e:
        return " ".join(str(e).removeprefix(f"git {' '.join(args)}: ").split())
    return None
