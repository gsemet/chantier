"""The retro's draft points, read from a window of the batch's numbered events and an optional
per-CR cost map: asks, refusals, blocks, Driver restarts, red long gates and cost outliers. Pure:
it reads no file, no forge and no git, and judges nothing (no tag, no fix, no field filled)."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from chantier.core.records import EventRecord

OUTLIER_FACTOR = 2.0  # a CR at this many times the window's median spend is drafted
MIN_COST_CRS = 3  # fewer CRs give no median worth judging
TEXT_CUT, NOTE_CUT, HEAD_CHARS = 160, 120, 7
KINDS = ("ask", "refusal", "block", "restart", "gate", "cost")
OPEN_MARK = "<!-- chantier retro draft:"
OPEN_LINE = f"{OPEN_MARK} facts from events.jsonl; judge, tag and fill each point, or delete it -->"
END_LINE = "<!-- end of chantier retro draft -->"
FIELDS = (
    "  - home: <CLI | refusal | next: or state line | help topic | card line>",
    "  - count:",
    "  - why not code:",
)

Numbered = list[tuple[int, EventRecord]]


@dataclass
class Point:
    """One draft point: its kind, its CR (or None), its problem text, the sequences it rests on."""

    kind: str
    cr: str | None
    text: str
    seqs: list[int] = field(default_factory=list)

    def problem(self) -> str:
        return f"{self.text} (events {', '.join(map(str, self.seqs))})"


def cut(text: str, n: int) -> str:
    """The first `n` characters, then `…` when the text is longer."""
    return text if len(text) <= n else text[:n] + "…"


def times(k: int, word: str = "time") -> str:
    return f"{k} {word}{'' if k == 1 else 's'}"


def window_crs(numbered: Numbered) -> list[str]:
    """The CR ids of the window's events (not the stack's), in first-seen order."""
    return list(dict.fromkeys(e.cr for _, e in numbered if e.cr and e.cr != "stack"))


def _refusal(e: EventRecord) -> str | None:
    """The refused text of a recorded refusal: a `refused:` note, or a blocked hand-back whose
    note starts `refused`; None for any other event."""
    note = e.note if isinstance(e.note, str) else ""
    if e.kind == "note" and note.startswith("refused:"):
        rest = note.removeprefix("refused:")
    elif e.kind == "handback" and e.result == "blocked" and note.startswith("refused"):
        rest = note.removeprefix("refused").removeprefix(":")
    else:
        return None
    return rest.strip()


def _asks(numbered: Numbered) -> list[Point]:
    return [
        Point(
            "ask",
            e.cr,
            f"ask {e.ask} to the user{f' on {e.cr}' if e.cr else ''}: "
            f"{cut(str(e.text or ''), TEXT_CUT)}",
            [n],
        )
        for n, e in numbered
        if e.kind == "ask"
    ]


def _refusals(numbered: Numbered) -> list[Point]:
    groups: dict[str, tuple[list[str], list[int]]] = {}
    for n, e in numbered:
        text = _refusal(e)
        if text is None:
            continue
        crs, seqs = groups.setdefault(text, ([], []))
        if e.cr and e.cr not in crs:
            crs.append(e.cr)
        seqs.append(n)
    return [
        Point(
            "refusal",
            crs[0] if len(crs) == 1 else None,
            f"refused on {', '.join(crs) or 'no CR'}: {text} ({times(len(seqs))})",
            seqs,
        )
        for text, (crs, seqs) in groups.items()
    ]


def _blocks(numbered: Numbered) -> list[Point]:
    return [
        Point("block", e.cr, f"{e.cr} handed back blocked: {cut(str(e.note or ''), TEXT_CUT)}", [n])
        for n, e in numbered
        if e.kind == "handback" and e.result == "blocked" and _refusal(e) is None
    ]


def _restarts(numbered: Numbered) -> list[Point]:
    by_cr: dict[str, list[tuple[int, EventRecord]]] = {}
    for n, e in numbered:
        if e.kind == "take" and e.restart is True and e.cr:
            by_cr.setdefault(e.cr, []).append((n, e))
    out = []
    for cr, takes in by_cr.items():
        note = takes[-1][1].note
        last = f" (last note: {cut(str(note), NOTE_CUT)})" if note else ""
        text = f"{cr}: {times(len(takes), 'Driver restart')}{last}"
        out.append(Point("restart", cr, text, [n for n, _ in takes]))
    return out


def _red_gates(numbered: Numbered) -> list[Point]:
    by_gate: dict[tuple[str, str], list[tuple[int, EventRecord]]] = {}
    for n, e in numbered:
        if e.kind == "gate" and e.result == "fail" and e.cr:
            by_gate.setdefault((e.cr, str(e.name or e.command or "")), []).append((n, e))
    out = []
    for (cr, name), fails in by_gate.items():
        heads = list(dict.fromkeys(str(e.head)[:HEAD_CHARS] for _, e in fails if e.head))
        at = f" at {', '.join(heads)}" if heads else ""
        text = f"{cr}: long gate `{name}` failed {times(len(fails))}{at}"
        out.append(Point("gate", cr, text, [n for n, _ in fails]))
    return out


def _outliers(numbered: Numbered, costs: dict[str, float] | None) -> list[Point]:
    crs = window_crs(numbered)
    spent = {cr: costs[cr] for cr in crs if costs and cr in costs}
    if len(spent) < MIN_COST_CRS:
        return []
    median = statistics.median(spent.values())
    if median <= 0:
        return []
    first: dict[str, int] = {}
    for n, e in numbered:
        if e.cr and e.cr in spent:
            first.setdefault(e.cr, n)
    return [
        Point(
            "cost",
            cr,
            f"{cr}: ${usd:.2f}, {usd / median:.1f} times the median ${median:.2f} of the "
            f"window's {len(spent)} CRs",
            [first[cr]],
        )
        for cr, usd in spent.items()
        if usd >= OUTLIER_FACTOR * median
    ]


def draft_points(numbered: Numbered, costs: dict[str, float] | None = None) -> list[Point]:
    """The window's draft points, in the order of the kinds, then by first sequence."""
    points = [
        *_asks(numbered),
        *_refusals(numbered),
        *_blocks(numbered),
        *_restarts(numbered),
        *_red_gates(numbered),
        *_outliers(numbered, costs),
    ]
    return sorted(points, key=lambda p: (KINDS.index(p.kind), p.seqs[0] if p.seqs else 0))


def draft_block(points: list[Point], day: str, crs: list[str], first: int, last: int) -> str:
    """The draft block, exactly the bytes `retro draft --write` appends (LF line ends)."""
    lines = [OPEN_LINE, f"## Draft: {day}: {', '.join(crs) or 'no CR'}", ""]
    for p in points:
        lines += [f"- [<tag>] {p.problem()}: <long-term fix>", *FIELDS]
    if not points:
        lines.append(
            "- no ask, refusal, block, Driver restart, red gate or cost outlier in events "
            f"{first}..{last}"
        )
    lines.append(END_LINE)
    return "\n".join(lines) + "\n"
