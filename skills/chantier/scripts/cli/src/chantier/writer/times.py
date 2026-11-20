"""The writer's times, in seconds, and the one environment variable that shortens them:
`CHANTIER_WRITER_TEST_TIMES=<every>:<quiet>:<max_wait>:<fetch_every>:<late>`."""

from __future__ import annotations

import os

EVERY_S = 30.0  # a cycle at least this often
QUIET_S = 10.0  # the changes have not moved for this long: commit
MAX_WAIT_S = 120.0  # the oldest change is this old: commit even if it still moves
FETCH_EVERY_S = 60.0  # a fetch at least this often with nothing to push
LATE_S = 300.0  # the 5-minute promise: past it, `sync-late@1`
POLL_S = 1.0  # the loop looks at the wake file this often
FINAL_S = 30.0  # the final cycle's limit
TEST_ENV = "CHANTIER_WRITER_TEST_TIMES"
PARTS = 5


def _test() -> tuple[float, ...] | None:
    text = os.environ.get(TEST_ENV)
    if not text:
        return None
    try:
        found = tuple(float(x) for x in text.split(":"))
    except ValueError:
        return None
    return found if len(found) == PARTS and all(x > 0 for x in found) else None


def _at(index: int, default: float) -> float:
    test = _test()
    return test[index] if test else default


def every_s() -> float:
    return _at(0, EVERY_S)


def quiet_s() -> float:
    return _at(1, QUIET_S)


def max_wait_s() -> float:
    return _at(2, MAX_WAIT_S)


def fetch_every_s() -> float:
    return _at(3, FETCH_EVERY_S)


def late_s() -> float:
    return _at(4, LATE_S)


def poll_s() -> float:
    return min(POLL_S, every_s())
