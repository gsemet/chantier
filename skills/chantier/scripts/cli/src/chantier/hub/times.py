"""The hub's and the watcher's constants and the one environment variable that shortens them
(see the package's docstring)."""

from __future__ import annotations

import os

CYCLE_S = 20.0  # the hub reads the forge at most this often (the board's page keeps its own 10 s)
QUIET_S = 20.0  # a watcher ends this long after the last new event of its project
IDLE_END_S = 7200.0  # a watcher with no event for it that wakes ends this long after its start
POLL_S = 1.0  # a watcher looks about this often
TEST_ENV = "CHANTIER_HUB_TEST_TIMES"
FIELDS = (2, 3)  # `<cycle>:<quiet>[:<idle_end>]`


def _test() -> tuple[float, float, float] | None:
    text = os.environ.get(TEST_ENV)
    if not text:
        return None
    try:
        found = [float(x) for x in text.split(":")]
    except ValueError:
        return None
    if len(found) not in FIELDS or min(found) <= 0:
        return None
    return found[0], found[1], found[2] if len(found) == FIELDS[1] else IDLE_END_S


def cycle_s() -> float:
    test = _test()
    return test[0] if test else CYCLE_S


def quiet_s() -> float:
    test = _test()
    return test[1] if test else QUIET_S


def idle_end_s() -> float:
    test = _test()
    return test[2] if test else IDLE_END_S


def wake_every_s(configured: float | None) -> float:
    """The least a watcher runs before it may end: `events.wake_every`, 0 for none; under the
    test times, no more than the test's quiet (the tests keep their short times)."""
    if configured is None:
        return 0.0
    test = _test()
    return min(configured, test[1]) if test else float(configured)


def poll_s() -> float:
    return min(POLL_S, cycle_s())
