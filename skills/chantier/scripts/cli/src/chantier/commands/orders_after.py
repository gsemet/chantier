"""`order after`: what a queued CR waits for, replaced (`--note`) or changed by one ref (`--add`,
`--remove`); a ref names a CR of the batch by its id, its folder slug or its path."""

from __future__ import annotations

from pathlib import Path

from chantier.commands.opening import check_cycles
from chantier.commands.orders_word import Word, target
from chantier.core.batch import Batch
from chantier.core.errors import ChantierError
from chantier.core.ids import normalize_cr
from chantier.core.records import CrEntry
from chantier.lifecycle.filing import slugify
from chantier.lifecycle.stages import cr_slug
from chantier.rails import is_release

USAGE = (
    'order after <cr> --note "<refs>" (replaces the list; - for none) | --add "<refs>" | '
    '--remove "<refs>"; a ref is a CR of the batch: its id (CR-447, 447), its folder slug, or '
    "its path (3-ready/<slug>, 4-batch/1-pending/<n>-<slug>), comma separated"
)
_FORMS = (
    "its id (CR-447, 447), its folder slug, or its path "
    "(3-ready/<slug>, 4-batch/1-pending/<n>-<slug>)"
)


def resolve_ref(b: Batch, ref: str) -> CrEntry:
    """The CR of the batch a ref names: its id, else its folder slug or path."""
    text = normalize_cr(ref.strip())
    by_id = next((x for x in b.record.crs if x.id == text), None)
    if by_id is not None:
        return by_id
    key = slugify(cr_slug(Path(text.rstrip("/\\")).name))
    found = [x for x in b.record.crs if cr_slug(Path(x.path or "").name) == key]
    if len(found) == 1:
        return found[0]
    if found:
        ids = ", ".join(x.id for x in found)
        raise ChantierError(
            f"order after: {ref.strip()} names several CRs of {b.id}: {ids}; name it by its id"
        )
    raise ChantierError(f"order after: {ref.strip()} is not a CR of {b.id}; a ref is {_FORMS}")


def refs_of(text: str) -> list[str]:
    return [s.strip() for s in text.split(",") if s.strip()]


def _checked(b: Batch, cr_id: str, refs: list[str]) -> list[str]:
    """The ids the refs name, checked: not the release CR, not itself; a merged CR is met and
    not recorded; each once."""
    ids: list[str] = []
    for ref in refs:
        dep = resolve_ref(b, ref)
        if is_release(dep):
            raise ChantierError(
                f"order after: {dep.id} is the release CR, which waits for every "
                f"other CR: {cr_id} waiting for it is a cycle"
            )
        if dep.id == cr_id:
            raise ChantierError(f"order after: {cr_id} cannot wait for itself")
        if dep.status != "merged" and dep.id not in ids:
            ids.append(dep.id)
    return ids


def _wanted(w: Word, c: CrEntry) -> list[str]:
    """The list the order asks for, as ids: the typed one, the current one plus, or minus."""
    b, cr_id = w.b, w.cr_id
    if w.add:
        added = _checked(b, cr_id, refs_of(w.add))
        return [*c.after, *(x for x in added if x not in c.after)]
    if w.remove:
        gone = {x.id for x in (resolve_ref(b, r) for r in refs_of(w.remove))}
        return [x for x in c.after if x not in gone]
    return [] if w.note.strip() == "-" else _checked(b, cr_id, refs_of(w.note))


def after(w: Word) -> list[str]:
    b, c, cr_id = w.b, target(w), w.cr_id
    if is_release(c):
        raise ChantierError(
            f"order after: {cr_id} is the release CR: the CLI keeps what it "
            "waits for (every other CR of the batch)"
        )
    if c.status != "queued":
        stack = "; in a stack, its place and base are set by `stack`"
        raise ChantierError(
            f"cannot change what {cr_id} waits for: it is {c.status}, not queued"
            + (stack if b.record.mode == "stack" else "")
        )
    ids = _wanted(w, c)
    previous = list(c.after)
    _set_after(c, ids)
    try:
        check_cycles(b)
    except ChantierError:
        _set_after(c, previous)
        raise
    b.touch(c)
    b.log("depends", cr_id, after=ids)
    w.recorded = ", ".join(ids) if ids else "-"
    line = f"{cr_id} now waits for {', '.join(ids)}" if ids else f"{cr_id} waits for nothing"
    return [line + (" (unchanged)" if ids == previous else "")]


def _set_after(c: CrEntry, ids: list[str]) -> None:
    if ids:
        c.after = ids
    else:
        c.unset("after")
