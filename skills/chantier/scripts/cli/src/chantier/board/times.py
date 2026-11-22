"""A CR's times as the board's Gantt and time cards draw them,
derived from the batch's `events.jsonl` (already read once per state): nothing is recorded."""

from __future__ import annotations

from typing import Any

from chantier.core.cr_times import ended as _ended
from chantier.core.cr_times import last_event as _last
from chantier.core.records import CrEntry, EventRecord

END = "end"
STATE_KINDS = {"take", "round", "handback", "pr-draft", "cancel"}


def _moves(e: EventRecord) -> bool:
    return e.kind in STATE_KINDS or (e.kind == "order" and e.order_kind in {"merged", "drop"})


def _state_after(e: EventRecord) -> str | None:
    """The state that holds from this event, `END` where the bar ends, `None` if none changes."""
    if e.kind in {"take", "round"}:
        return "working"
    if e.kind == "handback":
        return {"blocked": "blocked", "ready": "draft", "merged": END}.get(e.result or "")
    if e.kind == "pr-draft":
        return "draft" if e.draft is not False else "ready"
    if e.kind == "cancel" or (e.kind == "order" and e.order_kind in {"merged", "drop"}):
        return END
    return None


def _segments(own: list[EventRecord], ended: str | None) -> list[dict[str, Any]]:
    """The periods the CR spent in a state, from its first `take`."""
    taken = [i for i, e in enumerate(own) if e.kind == "take"]
    segments: list[dict[str, Any]] = []
    for e in own[taken[0] :] if taken else []:
        state = _state_after(e)
        if state is None or (state == END and ended):
            continue  # the bar then closes at `ended`, below
        if segments and segments[-1]["to"] is None:
            if state == segments[-1]["state"]:
                continue
            segments[-1]["to"] = e.t
        if state != END:
            segments.append({"state": state, "from": e.t, "to": None})
    if ended and segments and segments[-1]["to"] is None:
        segments[-1]["to"] = ended
    return segments


def _rounds(own: list[EventRecord]) -> list[dict[str, Any]]:
    """One entry per round: its coder time and the first inspector phase before the next round."""
    rounds: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for e in own:
        if e.kind == "round":
            n = e.round if e.round is not None else (rounds[-1]["n"] + 1 if rounds else 1)
            current = None
            if n not in [r["n"] for r in rounds]:
                current = {"n": n, "coder_at": e.t, "inspector_at": None}
                rounds.append(current)
        elif (
            e.kind == "phase"
            and e.phase == "inspector"
            and current
            and current["inspector_at"] is None
        ):
            current["inspector_at"] = e.t
    return rounds


def cr_times(events: list[EventRecord], c: CrEntry) -> dict[str, Any]:
    """The CR's started and ended times, last state change, state segments, rounds and verdict."""
    own = [e for e in events if e.cr == c.id]
    take = next((e for e in own if e.kind == "take"), None)
    ended = _ended(own, c)
    moved = [e.t for e in own if _moves(e)]
    if ended and c.status == "merged":
        moved.append(ended)
    verifier = _last(own, "phase", phase="verifier")
    verdict = _last(own, "verdict")
    return {
        "started_at": take.t if take else None,
        "ended_at": ended,
        "state_at": max(moved) if moved else None,
        "segments": _segments(own, ended),
        "rounds": _rounds(own),
        "verifier_at": verifier.t if verifier else None,
        "verdict": verdict.result if verdict else None,
        "verdict_at": verdict.t if verdict else None,
    }
