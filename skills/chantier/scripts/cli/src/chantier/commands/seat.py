"""`chantier foreman` and `chantier seat`."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from chantier.commands.registry import BATCH_EPOCH, NO_BATCH, Subparsers, add_command
from chantier.core.batch import check_epoch, read_batch, resolve_batch
from chantier.core.clock import now
from chantier.core.errors import EXIT_CONFLICT, EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.files import write_json
from chantier.core.records import SeatRecord, chief_sessions
from chantier.core.repo import Repo
from chantier.core.seat import read_seat
from chantier.lifecycle.convert import open_repo
from chantier.lifecycle.session import RenderedBatch
from chantier.lifecycle.stages import changes_lock
from chantier.plugin_files import detect_host


def foreman(args: argparse.Namespace) -> list[str]:
    repo = open_repo()
    batch = resolve_batch(repo, args.batch)
    if args.action == "get":
        d = read_batch(repo, batch)
        return [f"{d.get('foreman') or 'none'} epoch {d.get('foreman_epoch', 0)}"]
    with RenderedBatch(repo, batch, actor="foreman") as b:
        if args.action == "set":
            if not args.value or args.epoch is None:
                raise ChantierError("foreman set <session-id> --epoch <n>", EXIT_USAGE)
            current = b.data.get("foreman_epoch", 0)
            if args.epoch != current + 1:  # one session per epoch: the first to claim it runs it
                raise ChantierError(
                    f"epoch {args.epoch} cannot be claimed: batch {b.id} is at "
                    f"epoch {current}; stop now",
                    EXIT_CONFLICT,
                )
            b.data["foreman"] = args.value
            b.data["foreman_epoch"] = args.epoch
            b.data["foreman_transcript"] = None
            b.log("foreman", None, session=args.value, epoch=b.data["foreman_epoch"])
            return [f"foreman {args.value} epoch {b.data['foreman_epoch']}"]
        check_epoch(b, args.epoch)
        if not args.value:
            raise ChantierError("foreman transcript <session-uuid>", EXIT_USAGE)
        claimed = b.data.get("foreman_transcript")
        if claimed and claimed != args.value:
            # One epoch, one Foreman: a second session that starts as Foreman must not take over.
            raise ChantierError(
                f"epoch {b.data.get('foreman_epoch', 0)} of batch {b.id} is already run "
                f"by transcript {claimed}; stop now",
                EXIT_CONFLICT,
            )
        b.data["foreman_transcript"] = args.value
        seen = b.data.setdefault("foreman_transcripts", [])  # a relay keeps the earlier ones
        if args.value not in seen:
            seen.append(args.value)
            # each steering transcript is priced from its claim to the next one
            b.data.setdefault("foreman_claims", []).append(
                {"transcript": args.value, "since": now()}
            )
        if (
            b.data.get("steering") == "direct"
            and b.data.get("chief_transcript")
            and args.value != b.data["chief_transcript"]
        ):
            b.data["steering"] = "foreman"  # a Foreman took the batch over from the Chief of Staff
            b.log("steering", None, steering="foreman", transcript=args.value)
        b.log("foreman-transcript", None, transcript=args.value)
        return [f"transcript {args.value}"]


def own_transcript(host: str) -> str | None:
    """This session's transcript id, from the host's environment; None when unknown."""
    return (
        os.environ.get(
            "COPILOT_AGENT_SESSION_ID" if host == "copilot" else "CLAUDE_CODE_SESSION_ID"
        )
        or None
    )


def _get(repo: Repo) -> list[str]:
    held = read_seat(repo)
    if not held:
        return ["seat none"]
    return [
        f"seat {held.session} env {held.env or 'unknown'} "
        f'title "{held.title or ""}" link {held.link or "unknown"}',
        f"transcript {held.transcript or 'unknown'}",
    ]


def _leave(repo: Repo, path: Path, session: str) -> list[str]:
    held = read_seat(repo)
    if not held:
        return ["seat none"]
    if held.session != session:
        raise ChantierError(f"the seat is held by {held.session}", EXIT_PRECONDITION)
    path.unlink()
    return ["seat none"]


def _record_transcript(repo: Repo, transcript: str) -> list[str]:
    """The batch's files exist until `close`: it is the (single) non-closed batch."""
    lines = []
    for batch_id in repo.batch_ids():
        with RenderedBatch(repo, batch_id, actor="chief-of-staff") as b:
            if transcript != b.data.get("chief_transcript"):
                _set_chief(b, transcript)
                lines.append(f"{b.id}: Chief of Staff transcript {transcript}")
    return lines


def _set_chief(b: RenderedBatch, transcript: str) -> None:
    seen = chief_sessions(b.data)  # before the old one is replaced
    if transcript not in seen:
        seen.append(transcript)
    b.data["chief_transcript"] = transcript
    b.data["chief_transcripts"] = seen
    b.log("chief", None, transcript=transcript)


def _take(repo: Repo, path: Path, args: argparse.Namespace) -> list[str]:
    held = read_seat(repo)
    if held and held.session not in (args.session, args.over):
        raise ChantierError(
            f"the seat is held by {held.session} "
            f"({held.link or 'unknown'}): take it over only on the "
            f"user's word, with --over {held.session}",
            EXIT_PRECONDITION,
        )
    transcript = own_transcript(detect_host())
    record = SeatRecord(
        session=args.session,
        transcript=transcript,
        env=args.env,
        title=args.title,
        link=args.link,
    )
    write_json(path, record.to_data())
    return [f"seat {args.session}", *(_record_transcript(repo, transcript) if transcript else [])]


def seat(args: argparse.Namespace) -> list[str]:
    """The repository's Chief of Staff session: it records a session and refuses a silent
    take-over; who may take it is the cards' to say."""
    repo = open_repo()
    path = repo.changes / "seat.json"
    if args.action == "get":
        return _get(repo)
    if not args.session:
        raise ChantierError(f"seat {args.action} <session-id>", EXIT_USAGE)
    with changes_lock(repo):
        if args.action == "leave":
            return _leave(repo, path, args.session)
        return _take(repo, path, args)


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "foreman",
        foreman,
        "the Foreman claims its epoch (set) and records its transcript",
        BATCH_EPOCH,
    )
    s.add_argument("action", choices=["set", "get", "transcript"])
    s.add_argument("value", nargs="?")

    s = add_command(
        sub,
        "seat",
        seat,
        "the repository's Chief of Staff session: show, take or leave the seat",
        NO_BATCH,
    )
    s.add_argument("action", nargs="?", choices=["get", "take", "leave"], default="get")
    s.add_argument("session", nargs="?", help="the session id, for take and leave")
    s.add_argument("--env", help="take: the machine's name, or Remote")
    s.add_argument("--title", help="take: the session's current title")
    s.add_argument("--link", help="take: the session's link")
    s.add_argument(
        "--over",
        metavar="SESSION",
        help="take: the session whose seat this one takes, on the user's word",
    )
