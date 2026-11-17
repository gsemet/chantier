"""The first `take stack` made due: `stack_due` and the `status` line `stack_line`."""

from __future__ import annotations

from typing import Any

import pytest

from chantier.core.records import BatchRecord, CrEntry
from chantier.stacks import stack_due, stack_line

PR = "https://github.com/o/r/pull/"


def cr(n: int, **kw: Any) -> CrEntry:
    fields: dict[str, Any] = {"status": "ready", "pr": f"{PR}{n}", "order": n}
    return CrEntry(id=f"CR-{n}", **{**fields, **kw})


LINE = (
    "stack: take stack now: CR-1, CR-2 ready with a PR, no stack made yet "
    "(`take stack --epoch <n>`)"
)


@pytest.mark.parametrize(
    ("crs", "batch", "due"),
    [
        ([cr(1), cr(2)], {}, ["CR-1", "CR-2"]),
        ([cr(2), cr(1)], {}, ["CR-1", "CR-2"]),
        ([cr(1), cr(2, pr=None)], {}, []),
        ([cr(1), cr(2, status="working")], {}, []),
        ([cr(1), cr(2)], {"stack_agent": "agent-s"}, []),
        ([cr(1, stacked=True), cr(2)], {}, []),
        ([cr(1, status="merged", stacked=True), cr(2), cr(3)], {}, []),
        ([cr(1), cr(2), cr(3, after=["CR-4"]), cr(4, status="working")], {}, ["CR-1", "CR-2"]),
        ([cr(1), cr(2, after=["CR-3"]), cr(3, status="working")], {}, []),
        ([cr(1), cr(2, after=["CR-3"]), cr(3, order=3)], {}, ["CR-1", "CR-2", "CR-3"]),
        ([cr(1), cr(2, kind="release"), cr(3, kind="fix")], {}, []),
        ([cr(1), cr(2)], {"mode": "parallel"}, []),
        ([cr(1), cr(2)], {"status": "paused"}, []),
    ],
)
def test_the_first_stack_is_due(crs: list[CrEntry], batch: dict[str, Any], due: list[str]) -> None:
    d = BatchRecord(**{"id": "batch-01", "mode": "stack", "crs": crs, **batch})
    assert [c.id for c in stack_due(d)] == due
    line = f"stack: take stack now: {', '.join(due)} ready with a PR, no stack made yet "
    assert stack_line(d) == ([line + "(`take stack --epoch <n>`)"] if due else [])
    assert due != ["CR-1", "CR-2"] or stack_line(d) == [LINE]
