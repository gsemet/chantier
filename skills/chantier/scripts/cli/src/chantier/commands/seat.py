"""`chantier foreman` and `chantier seat`."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from chantier.core.batch import check_epoch, read_batch, require_epoch, resolve_batch
from chantier.core.clock import now
from chantier.core.errors import EXIT_CONFLICT, EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.files import write_json
from chantier.core.records import ClaimRecord, SeatRecord, chief_sessions
from chantier.core.repo import Repo
from chantier.core.seat import read_seat
from chantier.lifecycle.session import RenderedBatch
from chantier.lifecycle.stages import changes_lock
from chantier.plugin_files import detect_host


def foreman(args: argparse.Namespace) -> list[str]:
    repo = Repo.find()
    batch = resolve_batch(repo, args.batch)
    if args.action == "get":
        d = read_batch(repo, batch)
        return [f"{d.foreman or 'none'} epoch {d.foreman_epoch}"]
    if args.action == "set":
        if not args.value:
            raise ChantierError("foreman set <session-id> --epoch <n>", EXIT_USAGE)
        require_epoch(args.epoch, "foreman set <session-id> --epoch <n>")
    else:
        require_epoch(args.epoch, "foreman transcript <uuid> --epoch <n>")
    with RenderedBatch(repo, batch, actor="foreman") as b:
        if args.action == "set":
            return _claim(b, args)
        check_epoch(b, args.epoch)
        return _transcript(b, args)


def _claim(b: RenderedBatch, args: argparse.Namespace) -> list[str]:
    current = b.record.foreman_epoch
    if args.epoch != current + 1:  # one number per Foreman: the first to claim it runs it
        raise ChantierError(
            f"Foreman n°{args.epoch} of {b.id} cannot be claimed: the batch is at "
            f"Foreman n°{current}; stop now",
            EXIT_CONFLICT,
        )
    b.record.foreman = args.value
    b.record.foreman_epoch = args.epoch
    b.record.foreman_transcript = None
    b.log("foreman", None, session=args.value, epoch=b.record.foreman_epoch)
    return [f"foreman {args.value} epoch {b.record.foreman_epoch}"]


def _transcript(b: RenderedBatch, args: argparse.Namespace) -> list[str]:
    if not args.value:
        raise ChantierError("foreman transcript <session-uuid>", EXIT_USAGE)
    claimed = b.record.foreman_transcript
    if claimed and claimed != args.value:
        # One number, one Foreman: a second session that starts as Foreman must not take over.
        raise ChantierError(
            f"Foreman n°{b.record.foreman_epoch} of {b.id} is already run "
            f"by transcript {claimed}; stop now",
            EXIT_CONFLICT,
        )
    b.record.foreman_transcript = args.value
    if args.value not in b.record.foreman_transcripts:  # a relay keeps the earlier ones
        b.record.append("foreman_transcripts", args.value)
    claims = b.record.foreman_claims
    if not claims or claims[-1].transcript != args.value:
        # each steering stint is priced from its claim to the next one, a returning session too
        b.record.append("foreman_claims", ClaimRecord(transcript=args.value, since=now()))
    out = [f"transcript {args.value}"]
    chief = b.record.chief_transcript
    if b.record.steering == "direct" and chief and args.value != chief:
        b.record.steering = "foreman"  # a Foreman took the batch over from the Chief of Staff
        b.log("steering", None, steering="foreman", transcript=args.value)
    elif b.record.steering == "foreman" and chief and args.value == chief:
        b.record.steering = "direct"  # the Chief of Staff took the batch over from its Foreman
        b.log("steering", None, steering="direct", transcript=args.value)
        n = b.record.foreman_epoch
        out.append(f"steering direct: the Chief of Staff steers {b.id} as Foreman n°{n}")
    b.log("foreman-transcript", None, transcript=args.value)
    return out


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
            if transcript != b.record.chief_transcript:
                _set_chief(b, transcript)
                lines.append(f"{b.id}: Chief of Staff transcript {transcript}")
    return lines


def _set_chief(b: RenderedBatch, transcript: str) -> None:
    seen = chief_sessions(b.record)  # before the old one is replaced
    if transcript not in seen:
        seen.append(transcript)
    b.record.chief_transcript = transcript
    b.record.chief_transcripts = seen
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
    repo = Repo.find()
    path = repo.changes / "seat.json"
    if args.action == "get":
        return _get(repo)
    if not args.session:
        raise ChantierError(f"seat {args.action} <session-id>", EXIT_USAGE)
    with changes_lock(repo):
        if args.action == "leave":
            return _leave(repo, path, args.session)
        return _take(repo, path, args)
