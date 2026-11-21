"""The sentence a `board@1` event is told by."""

from __future__ import annotations

from typing import Any


def board_text(e: dict[str, Any]) -> str:
    """The line a `board@1` event is told by: the write, then what the Chief of Staff does with
    it (a destination to write, and for the running batch the go for `order add`)."""
    head = f"board wrote ({e.get('action')}): {e.get('text')}; "
    text = str(e.get("text"))
    if e.get("action") == "running-batch":
        return head + (
            "for the Chief of Staff: the user's go for the running batch: write its destination, "
            "then `order add --note <folder>` once its specification is final "
            "(at once for a CR in `3-ready`)"
        )
    if e.get("action") == "move" and ("running-batch mark cleared" in text or "→ 3-ready" in text):
        return head + "for the Chief of Staff: write its destination, act on nothing else"
    return head + "for the Chief of Staff: tell the user, act on nothing"
