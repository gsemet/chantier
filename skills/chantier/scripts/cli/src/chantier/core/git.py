"""Running git, and the remote's default branch."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from chantier.core.errors import EXIT_EXTERNAL, EXIT_PRECONDITION, ChantierError


def git(
    *args: str,
    cwd: Path | str | None = None,
    check: bool = True,
    env: dict[str, str] | None = None,
    input: str | None = None,
    raw: bool = False,
) -> str:
    """Run git and return its standard output, stripped (`raw`: as git printed it). `env` is
    merged over the environment; `input` is passed on standard input as text."""
    env = {
        **os.environ,
        "GIT_EDITOR": "true",
        "GIT_PAGER": "cat",
        "GIT_TERMINAL_PROMPT": "0",
        **(env or {}),
    }
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
        input=input,
        check=False,
    )
    if check and p.returncode != 0:
        raise ChantierError(
            f"git {' '.join(args)}: {p.stderr.strip() or p.stdout.strip()}", EXIT_EXTERNAL
        )
    return p.stdout if raw else p.stdout.strip()


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


def is_ancestor(older: str, newer: str, cwd: Path | str | None = None) -> bool | None:
    """A read: whether `older` is an ancestor of `newer` (`git merge-base --is-ancestor`): True on
    exit 0, False on exit 1, None on any other exit (a commit or a ref git cannot read)."""
    if cwd is not None and not Path(cwd).is_dir():
        raise ChantierError(f"no folder {cwd}: git cannot run there", EXIT_PRECONDITION)
    env = {**os.environ, "GIT_EDITOR": "true", "GIT_PAGER": "cat", "GIT_TERMINAL_PROMPT": "0"}
    p = subprocess.run(
        ["git", "--no-pager", "merge-base", "--is-ancestor", older, newer],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )
    return {0: True, 1: False}.get(p.returncode)


def _env() -> dict[str, str]:
    return {**os.environ, "GIT_EDITOR": "true", "GIT_PAGER": "cat", "GIT_TERMINAL_PROMPT": "0"}


def run(*args: str, cwd: Path | str | None = None) -> tuple[int, str, str]:
    """A read that tells its exit code: (code, stdout, stderr), git's own failures included
    (`git` raises on any non-zero exit, which cannot tell exit 1 from a refusal)."""
    if cwd is not None and not Path(cwd).is_dir():
        raise ChantierError(f"no folder {cwd}: git cannot run there", EXIT_PRECONDITION)
    p = subprocess.run(
        ["git", "--no-pager", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_env(),
        check=False,
    )
    return p.returncode, p.stdout, p.stderr


def version_text() -> str | None:
    """What `git --version` prints, stripped; None when git is absent or refuses."""
    try:
        code, out, _ = run("--version")
    except (OSError, ChantierError):
        return None
    return out.strip() if code == 0 else None


def parse_version(text: str | None) -> tuple[int, int, int] | None:
    """`git version 2.56.0.windows.4` -> (2, 56, 0); None when the text does not parse."""
    found = re.match(r"git version (\d+)\.(\d+)(?:\.(\d+))?", text or "")
    return None if found is None else (int(found[1]), int(found[2]), int(found[3] or 0))


def version() -> tuple[int, int, int] | None:
    """The installed git's version; None when git is absent or the text does not parse."""
    return parse_version(version_text())
