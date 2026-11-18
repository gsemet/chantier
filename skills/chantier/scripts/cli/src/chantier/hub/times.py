"""The hub's two constants and the one environment variable that shortens them (see the
package's docstring)."""

from __future__ import annotations

import os

CYCLE_S = 20.0  # the hub reads the forge at most this often (the board's page keeps its own 10 s)
QUIET_S = 20.0  # a watcher ends this long after the last new event of its project
POLL_S = 1.0  # a watcher looks about this often
TEST_ENV = "CHANTIER_HUB_TEST_TIMES"


def _test() -> tuple[float, float] | None:
    text = os.environ.get(TEST_ENV)
    if not text:
        return None
    try:
        cycle, quiet = (float(x) for x in text.split(":"))
    except ValueError:
        return None
    return (cycle, quiet) if cycle > 0 and quiet > 0 else None


def cycle_s() -> float:
    test = _test()
    return test[0] if test else CYCLE_S


def quiet_s() -> float:
    test = _test()
    return test[1] if test else QUIET_S


def poll_s() -> float:
    return min(POLL_S, cycle_s())
