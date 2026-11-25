"""The published model of a Driver's `msg@1` line (`chantier msg steering`) and its text (see
`schemas.py`). `unit`, `kind` and `steering` are plain strings, as the module's open sets are: the
command's own `choices` close them today."""

from __future__ import annotations

from typing import Any

from chantier.hub.schemas_base import Payload


class Msg1(Payload):
    batch: str
    unit: str
    kind: str
    text: str
    wakes: bool
    steering: str


def msg_text(e: dict[str, Any]) -> str:
    """The line a `msg@1` event is told by: a Driver's message to the batch's steering session."""
    return (
        f"message from {e.get('unit')}'s Driver ({e.get('kind')}, seq {e.get('seq')}): "
        f'"{e.get("text")}"; for the steering session: act on it, then inbox --read {e.get("seq")} '
        "--epoch <n>"
    )
