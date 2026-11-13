"""What `chantier open` records before any folder moves: the settings, the release grant, the
batch's record and the project's instruction files."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from chantier import __version__
from chantier.core.clock import now
from chantier.core.errors import EXIT_EXTERNAL, EXIT_USAGE, ChantierError
from chantier.core.git import default_branch, git
from chantier.core.repo import Repo
from chantier.plugin_files import INSTRUCTIONS
from chantier.rails_release import check_grant


def open_settings(repo: Repo, args: argparse.Namespace) -> dict[str, Any]:
    """The remote and default branch the batch opens with, checked against git."""
    if args.slots < 1 or (args.budget is not None and args.budget <= 0):
        raise ChantierError("slots and budget must be positive", EXIT_USAGE)
    if args.remote not in git("remote", cwd=repo.root).split():
        raise ChantierError(f"no remote {args.remote!r}: pass --remote <remote>", EXIT_EXTERNAL)
    branch = args.default_branch or default_branch(repo.root, args.remote)
    if not branch:
        raise ChantierError(
            f"Git does not know the default branch of {args.remote!r}: read "
            "AGENTS.md or ask the user, then pass --default-branch"
        )
    return {
        "default_branch": branch,
        "remote": args.remote,
        "max_rounds": repo.config["max_rounds"],
    }


def release_grant(args: argparse.Namespace) -> dict[str, Any] | None:
    """The grant of the release CR, when `--release` names one."""
    if args.release is None:
        if args.autonomous_releases or args.grant_fixes:
            raise ChantierError(
                "--autonomous-releases and --grant-fixes need --release", EXIT_USAGE
            )
        return None
    if not 1 <= args.release <= len(args.items):
        raise ChantierError("--release: the item number of the release CR", EXIT_USAGE)
    release = {
        "autonomous": args.autonomous_releases,
        "fixes": args.grant_fixes,
        "published": 0,
    }
    check_grant(release, args.budget)
    return release


def new_record(
    args: argparse.Namespace,
    host: str,
    settings: dict[str, Any],
    release: dict[str, Any] | None,
    chief: str | None,
) -> dict[str, Any]:
    """The record of a batch that has no CR yet."""
    return {
        "id": None,
        "version": __version__,
        "created": now(),
        "status": "running",
        "host": host,
        "mode": args.mode,
        "slots": args.slots,
        "budget_usd": args.budget,
        "spent_usd": None,
        "foreman": None,
        "foreman_epoch": 0,
        "foreman_transcript": None,
        "foreman_transcripts": [],
        "foreman_claims": [],
        "steering": "direct" if args.direct else "foreman",
        "chief_transcript": chief,
        "chief_transcripts": [chief] if chief else [],
        "stack_agent": None,
        "heartbeat": None,
        "heartbeat_stopped": None,
        "settings": settings,
        "orders": [],
        "asks": [],
        "crs": [],
        "release": release,
    }


def instruction_files(root: Path) -> str:
    return ", ".join(n for n in INSTRUCTIONS if (root / n).is_file()) or "none"
