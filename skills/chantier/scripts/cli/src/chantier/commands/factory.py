"""The factory switch: a batch whose CRs made ready with `triage --ready` join it on their own."""

from __future__ import annotations

import re

from chantier.core.batch import Batch
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.records import BatchRecord
from chantier.core.repo import Repo
from chantier.lifecycle.stages import stage_layout
from chantier.rails import ENDED, all_merged, is_release

_TOKEN = re.compile(r" Factory: (?:on|off)\.")


FACTORY_ON = " factory: on"


def factory_word(on: bool) -> str:
    return "on" if on else "off"


def set_factory(b: Batch, on: bool, why: str) -> None:
    """Switch the batch's factory: the record, its log, and the token of `brief.md`'s first
    bullet (the bullet `- Factory: on|off.` is appended when the brief has no token)."""
    b.record.factory = on
    b.log("factory", None, factory=on, note=why)
    brief = b.dir / "brief.md"
    if not brief.is_file():
        return
    with open(brief, encoding="utf-8", newline="") as f:
        text = f.read()
    token = f" Factory: {factory_word(on)}."
    if _TOKEN.search(text):
        text = _TOKEN.sub(token, text, count=1)
    else:
        eol = "\r\n" if "\r\n" in text else "\n"
        text = text.rstrip("\r\n") + f"{eol}-{token}{eol}"
    with open(brief, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def ready_not_joined(repo: Repo) -> list[str]:
    """The folders of `3-ready`, sorted by name, each as `order add --note` reads it (relative
    to the planning folder)."""
    ready = stage_layout(repo)["ready"]
    if not ready.is_dir():
        return []
    return [d.relative_to(repo.changes).as_posix() for d in sorted(ready.iterdir()) if d.is_dir()]


def not_joined_line(repo: Repo, skip: set[str] | None = None) -> str | None:
    """`3-ready holds <n> CRs not joined: <folder>, ...`; None when none is left. `skip` holds
    folders to leave out (the CRs an `open` has just taken)."""
    folders = [f for f in ready_not_joined(repo) if f not in (skip or set())]
    if not folders:
        return None
    return f"3-ready holds {len(folders)} CRs not joined: {', '.join(folders)}"


def not_joined_text(line: str, batch: str) -> str:
    """The `3-ready holds <n> CRs not joined` line, with what the Chief of Staff does."""
    return (
        f"{line}: the factory's go covers them: `order add --note <folder> --batch {batch}` "
        "each, a release CR excepted"
    )


def factory_lines(repo: Repo, d: BatchRecord) -> list[str]:
    """`status`, a factory batch: the CRs in `3-ready` that did not join (the Chief of Staff adds
    them, the factory's go covering them)."""
    out = no_cr_lines(d)
    line = not_joined_line(repo) if d.factory else None
    if line:
        out.append(f"factory: {line}: `order add --note <folder>` each, a release CR excepted")
    return out


USAGE = 'order factory on|off --note "<the user\'s words>"'


def switch_factory(b: Batch, to: str, note: str) -> list[str]:
    """`order factory on|off --note <words>`: a factory batch takes each CR made ready with
    `triage --ready` on its own. The order is done at once by the caller: the CLI did its whole
    part, and an open order would block `close`."""
    if to not in ("on", "off") or not note.strip():
        raise ChantierError(USAGE, EXIT_USAGE)
    on = to == "on"
    if b.record.closing:
        raise ChantierError(f"order factory: {b.id} is closing", EXIT_PRECONDITION)
    if on == b.record.factory:
        raise ChantierError(
            f"{b.id} is already a factory batch" if on else f"{b.id} is not a factory batch",
            EXIT_PRECONDITION,
        )
    if on and any(is_release(x) and x.status not in ENDED for x in b.record.crs):
        raise ChantierError(
            f"a release CR is in {b.id}: it ends the factory; open a new factory batch "
            "after the close",
            EXIT_PRECONDITION,
        )
    set_factory(b, on, note.strip())
    if on:
        out = [
            "factory on: each CR made ready with `triage --ready` joins "
            f"{b.id} on its own; it stays open until the user's `close`"
        ]
        left = not_joined_line(b.repo)
        return [*out, not_joined_text(left, b.id)] if left else out
    out = [
        f"factory off: ready CRs no longer join {b.id}; it ends as any batch: at its last CR's "
        "end, the retro, then the close offer"
    ]
    if b.record.status == "paused" and all_merged(b.record):
        out.append(
            "every CR is merged or cancelled: next: the retro (with its critic), then offer "
            "the close"
            if b.record.crs
            else f"no CR ever joined {b.id}: next: offer the close (`chantier close`, then "
            "`close --yes` on the user's yes); no retro"
        )
    return out


def no_cr_lines(d: BatchRecord) -> list[str]:
    """A paused batch that never held a CR: how a CR joins it."""
    if d.status != "paused" or d.crs:
        return []
    if d.factory:
        return ["no CR yet: `triage <folder> --ready` joins one on its own"]
    return [f"no CR yet: `order add --note <folder> --batch {d.id}` joins one"]
