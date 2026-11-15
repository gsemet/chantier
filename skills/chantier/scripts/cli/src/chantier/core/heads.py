"""Comparing a recorded head with a head, and reading whether a long gate passed at one."""

from __future__ import annotations

from chantier.core.records import EventRecord


def same_head(recorded: str | None, head: str | None) -> bool:
    """Heads are recorded as the full SHA. One recorded short before (an open batch from an older
    version) matches the full SHA it is a prefix of."""
    if not recorded or not head:
        return False
    return recorded == head or head.startswith(recorded) or recorded.startswith(head)


def gate_passed(events: list[EventRecord], head: str | None) -> bool:
    """A long gate passed at a head: the last `gate` invocation at that head passed every command
    it was given. The events of one invocation share a `run`; it stops at its first failure, so
    its last event says. An event with no `run` (an older record) is an invocation by itself."""
    here = [e for e in events if e.kind == "gate" and same_head(e.head, head)]
    if not here:
        return False
    run = here[-1].run
    if run is None:
        return bool(here[-1].result == "pass")
    return all(e.result == "pass" for e in here if e.run == run)
