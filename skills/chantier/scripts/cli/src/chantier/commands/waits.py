"""`wait`: a CR's typed waits (answer, approval, pipeline, merge), recorded, cleared and shown.

In a batch the waits are the CR entry's (`batch.json`); on a backlog CR they are the folder's
`waits.json`, written through the store. A wait changes no rule: it is a fact `status`, `handoff`,
the board and the forge hub read. The hub only signals a wait met (`wait-cleared@1`); the steering
session clears it."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from chantier.commands.wait_view import GITLAB_NOTE, wait_line
from chantier.core import waits
from chantier.core.batch import (
    Batch,
    check_epoch,
    find_cr_batch,
    read_batch,
)
from chantier.core.clock import now
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.records import BatchRecord, CrEntry
from chantier.core.repo import Repo
from chantier.core.waits import what
from chantier.lifecycle.session import RenderedBatch
from chantier.lifecycle.stages import changes_lock, cr_stage, stage_layout

CR_ID = re.compile(r"CR-\d+")
TYPE_WORDS = "answer, approval, pipeline or merge"
BACKLOG_STAGES = ("inbox", "backlog", "ready")


def is_cr_id(value: str) -> bool:
    return CR_ID.fullmatch(value) is not None


# ---- building a wait ------------------------------------------------------------------------


def _recorded_pr(c: CrEntry) -> str | None:
    return c.pr if c.pr and re.match(r"https?://", c.pr) else None


def _full_sha(c: CrEntry, given: str | None, who: str) -> str:
    """The pipeline wait's sha: the given one (full, or a prefix of 7 or more of the recorded
    head, stored in full), else the recorded head."""
    if given is None:
        if not c.head:
            raise ChantierError(f"{who} pipeline: {c.id} has no recorded head", EXIT_PRECONDITION)
        given = c.head
    sha = given.strip().lower()
    if waits.FULL_SHA.fullmatch(sha):
        return sha
    head = (c.head or "").lower()
    if waits.PREFIX_SHA.fullmatch(sha) and waits.FULL_SHA.fullmatch(head) and head.startswith(sha):
        return head
    raise ChantierError(
        f"{who} pipeline: {given!r} is not a full sha (40 or 64 hex characters)", EXIT_PRECONDITION
    )


def _checked_link(link: str, who: str) -> None:
    from chantier import connectors  # noqa: PLC0415 - slow import

    if connectors.connector_for(link) is None:
        raise ChantierError(connectors.UNCLAIMED.format(link=link), EXIT_PRECONDITION)


def resolve(
    c: CrEntry, type_: str, ref: str | None, link: str | None, who: str
) -> tuple[str, str | None]:
    """The (ref, link) of a wait of a CR of the batch, with the defaults from its record; a
    refusal when none exists. `who` opens a message (`--wait` or `wait add`)."""
    if type_ not in waits.TYPES:
        raise ChantierError(f"--wait: {type_} is not a wait type: {TYPE_WORDS}", EXIT_PRECONDITION)
    if type_ == "answer":
        if not (ref and ref.strip()):
            raise ChantierError(
                f'{who} answer needs the question: {who} answer="<question>"'
                if who == "--wait"
                else 'wait add answer needs --ref "<the question>"',
                EXIT_PRECONDITION,
            )
        return " ".join(ref.split()), None
    if link is not None and type_ != "pipeline":
        raise ChantierError("--link is for a pipeline wait only", EXIT_PRECONDITION)
    pr = link or _recorded_pr(c)
    if type_ == "pipeline":
        if pr is None:
            raise ChantierError(f"{who} pipeline: {c.id} has no recorded PR", EXIT_PRECONDITION)
        sha = _full_sha(c, ref, who)
        _checked_link(pr, who)
        return sha, pr
    shown = ref or pr
    if shown is None:
        raise ChantierError(f"{who} {type_}: {c.id} has no recorded PR", EXIT_PRECONDITION)
    _checked_link(shown, who)
    return shown, shown


def outside_line(repo: Repo, d: BatchRecord, w: dict[str, Any]) -> str | None:
    """The line for a wait on a link of another repository than the batch's recorded PRs."""
    link = w.get("link")
    if not link or w["type"] not in waits.FORGE_TYPES:
        return None
    from chantier import connectors  # noqa: PLC0415 - slow import
    from chantier.hub import waits as hub_waits  # noqa: PLC0415 - slow import

    reference, connector = hub_waits.batch_place(d, repo), connectors.connector_for(link)
    if reference is None or connector is None or connector.place(link) == reference:
        return None
    return (
        f"{w['id']} {w['type']}: {link} is not in the batch's repository: the hub does not "
        "read it; clear it by hand"
    )


def add_to_cr(
    repo: Repo, d: BatchRecord, c: CrEntry, specs: list[tuple[str, str | None]], note: str
) -> tuple[list[dict[str, Any]], list[str]]:
    """Add the waits `specs` (`(type, ref)`) to the CR's entry; the waits and the repository
    lines. Every spec is resolved before the first is added: a refusal adds none."""
    resolved = [resolve(c, t, r, None, "--wait") for t, r in specs]
    return _append(repo, d, c, [(t, *x) for (t, _), x in zip(specs, resolved, strict=True)], note)


def _append(
    repo: Repo, d: BatchRecord, c: CrEntry, items: list[tuple[str, str, str | None]], note: str
) -> tuple[list[dict[str, Any]], list[str]]:
    added: list[dict[str, Any]] = []
    for type_, ref, link in items:
        w = waits.make(waits.next_id(c.waits, added), type_, ref, link, note)
        added.append(w)
    c.waits = [*c.waits, *added]
    return added, [x for w in added if (x := outside_line(repo, d, w))]


# ---- the command ----------------------------------------------------------------------------


def _usage() -> ChantierError:
    return ChantierError(
        "wait [<cr>] | wait <cr> add <type> [--ref <ref>] --note <text> | "
        "wait <cr> clear <id> [--epoch <n>]",
        EXIT_USAGE,
    )


def wait(args: argparse.Namespace) -> list[str]:
    repo = Repo.find()
    if args.action is None:
        return _show(repo, args)
    if args.cr is None:
        raise _usage()
    if args.action == "add":
        if len(args.args) != 1:
            raise ChantierError(f"wait <cr> add <{'|'.join(waits.TYPES)}> …", EXIT_USAGE)
        if args.args[0] not in waits.TYPES:
            raise ChantierError(
                f"wait add: {args.args[0]} is not a wait type: {TYPE_WORDS}", EXIT_PRECONDITION
            )
        if not (args.note and args.note.strip()):
            raise ChantierError('wait add needs --note "<why it waits>"', EXIT_PRECONDITION)
    elif len(args.args) != 1 or not waits.ID.fullmatch(args.args[0]):
        raise ChantierError("wait <cr> clear <w<n>>", EXIT_USAGE)
    if is_cr_id(args.cr):
        return _in_batch(repo, args)
    return _in_backlog(repo, args)


def _in_batch(repo: Repo, args: argparse.Namespace) -> list[str]:
    batch = find_cr_batch(repo, args.cr, args.batch)
    if args.action == "clear" and args.epoch is None:
        raise ChantierError(
            f"wait clear in a batch is the steering session's: wait {args.cr} clear "
            f"{args.args[0]} --epoch <n>",
            EXIT_PRECONDITION,
        )
    with (
        changes_lock(repo),
        RenderedBatch(repo, batch, actor="driver" if args.epoch is None else "foreman") as b,
    ):
        check_epoch(b, args.epoch)
        c = b.cr(args.cr)
        if args.action == "add":
            return _add_in_batch(repo, b, c, args)
        return _clear_in_batch(b, c, args.args[0], args.epoch)


def _add_in_batch(repo: Repo, b: Batch, c: CrEntry, args: argparse.Namespace) -> list[str]:
    if not waits.counted(c.status):
        raise ChantierError(f"{c.id} is {c.status}: it waits for nothing", EXIT_PRECONDITION)
    type_ = args.args[0]
    ref, link = resolve(c, type_, args.ref, args.link, "wait add")
    if type_ == "pipeline" and args.link:
        _checked_link(link or "", "wait add")
    added, lines = _append(repo, b.record, c, [(type_, ref, link)], " ".join(args.note.split()))
    b.touch(c)
    b.log("wait", c.id, action="add", wait=added[0]["id"], wait_type=type_, ref=ref)
    return [f"{c.id} {added[0]['id']} {type_} added", *lines]


def _clear_in_batch(b: Batch, c: CrEntry, wait_id: str, epoch: int | None) -> list[str]:
    found = next((w for w in waits.open_of(c.waits) if w["id"] == wait_id), None)
    if found is None:
        raise ChantierError(f"{c.id} has no open wait {wait_id}", EXIT_PRECONDITION)
    found["cleared_at"], found["cleared_by"] = now(), f"epoch {epoch}"
    c.waits = [*c.waits]
    b.touch(c)
    b.log("wait", c.id, action="clear", wait=wait_id)
    return [f"{c.id} {wait_id} cleared"]


def _folder(repo: Repo, item: str) -> Path:
    """A backlog CR's folder; refused under `4-batch/` and when it is not a CR folder."""
    folder = repo.planning_path(item, "CR folder")
    paths = stage_layout(repo)
    stage = cr_stage(paths, folder) if folder.is_dir() else None
    shown = repo.rel(folder) if folder.exists() else item
    if stage in ("pending", "actives", "done"):
        raise ChantierError(f"{shown} is in the batch: name its CR id", EXIT_PRECONDITION)
    if stage not in BACKLOG_STAGES:
        raise ChantierError(
            f"not a CR folder of the inbox, the backlog or 3-ready: {item}", EXIT_USAGE
        )
    return folder


def _in_backlog(repo: Repo, args: argparse.Namespace) -> list[str]:
    folder = _folder(repo, args.cr)
    if args.epoch is not None:
        raise ChantierError(
            "wait on a backlog CR takes no --epoch (it is not in a batch)", EXIT_PRECONDITION
        )
    path = folder / waits.FILE
    if args.action == "add":
        type_ = args.args[0]
        ref, link = _backlog_ref(type_, args)
        note = " ".join(args.note.split())
    repo.check_publish([path])
    with changes_lock(repo):
        try:
            current = waits.read_file(repo.store, folder) or []
        except waits.WaitsInvalid as e:
            raise ChantierError(
                f"{repo.rel(path)}: {waits.FILE} is not valid: {e}; fix it or remove it",
                EXIT_PRECONDITION,
            ) from e
        if args.action == "add":
            w = waits.make(waits.next_id(current), type_, ref, link, note)
            current.append(w)
            out = f"{repo.rel(folder)} {w['id']} {type_} added"
        else:
            wait_id = args.args[0]
            found = next((w for w in waits.open_of(current) if w["id"] == wait_id), None)
            if found is None:
                raise ChantierError(
                    f"{repo.rel(folder)} has no open wait {wait_id}", EXIT_PRECONDITION
                )
            found["cleared_at"], found["cleared_by"] = now(), "hand"
            out = f"{repo.rel(folder)} {wait_id} cleared"
        repo.store.write_text(repo.rel(path), waits.file_text(current))
    return [out]


def _backlog_ref(type_: str, args: argparse.Namespace) -> tuple[str, str | None]:
    """A backlog wait's (ref, link): `--ref` is needed for every type, and `--link` too for a
    pipeline (a backlog CR has no recorded PR)."""
    if not (args.ref and args.ref.strip()):
        raise ChantierError(
            f"wait add {type_} on a backlog CR needs --ref "
            + ('"<the question>"' if type_ == "answer" else "<the link or sha>"),
            EXIT_PRECONDITION,
        )
    ref = args.ref.strip()
    if args.link is not None and type_ != "pipeline":
        raise ChantierError("--link is for a pipeline wait only", EXIT_PRECONDITION)
    if type_ == "answer":
        return " ".join(ref.split()), None
    if type_ == "pipeline":
        if not args.link:
            raise ChantierError(
                "wait add pipeline on a backlog CR needs --link <the PR or MR link>",
                EXIT_PRECONDITION,
            )
        if not waits.FULL_SHA.fullmatch(ref.lower()):
            raise ChantierError(
                f"wait add pipeline: {ref!r} is not a full sha (40 or 64 hex characters)",
                EXIT_PRECONDITION,
            )
        _checked_link(args.link, "wait add")
        return ref.lower(), args.link
    _checked_link(ref, "wait add")
    return ref, ref


def _show(repo: Repo, args: argparse.Namespace) -> list[str]:
    if args.cr is not None:
        return _show_one(repo, args)
    out: list[str] = []
    names = [args.batch] if args.batch else repo.open_batches() or repo.paused_batches()
    if names:
        d = read_batch(repo, find_batch_name(names))
        out += [x for c in sorted(d.crs, key=lambda c: c.order) if (x := wait_line(repo, d, c))]
    paths = stage_layout(repo)
    from chantier.lifecycle.stages import cr_folders  # noqa: PLC0415

    for folder in cr_folders(repo.store, paths):
        if cr_stage(paths, folder) in BACKLOG_STAGES and (line := _backlog_line(repo, folder)):
            out.append(line)
    return out or ["nothing waits"]


def find_batch_name(names: list[str]) -> str:
    from chantier.core.ids import normalize_batch  # noqa: PLC0415

    return normalize_batch(names[0])


def _backlog_line(repo: Repo, folder: Path) -> str | None:
    try:
        found = waits.read_file(repo.store, folder)
    except waits.WaitsInvalid:
        return None
    mine = waits.open_of(found or [])
    if not mine:
        return None
    from chantier.hub import waits as hub_waits  # noqa: PLC0415 - slow import

    parts = [what(w) + (GITLAB_NOTE if hub_waits.gitlab_unproved(w) else "") for w in mine]
    return f"{repo.rel(folder)} waits for: " + "; ".join(parts)


def _show_one(repo: Repo, args: argparse.Namespace) -> list[str]:
    if is_cr_id(args.cr):
        batch = find_cr_batch(repo, args.cr, args.batch)
        d = read_batch(repo, batch)
        c = next((x for x in d.crs if x.id == args.cr), None)
        if c is None:
            raise ChantierError(f"unknown CR {args.cr} in batch {batch}", EXIT_USAGE)
        return [wait_line(repo, d, c) or f"{c.id} waits for nothing"]
    folder = _folder(repo, args.cr)
    return [_backlog_line(repo, folder) or f"{repo.rel(folder)} waits for nothing"]
