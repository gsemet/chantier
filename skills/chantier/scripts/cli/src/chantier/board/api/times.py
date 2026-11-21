"""The API's times and limits, and the one environment variable that shortens the times (the
tests': read here and nowhere else)."""

from __future__ import annotations

import os

PUSH_EVERY_S = 2.0  # the push loop looks at what clients watch this often
HOLD_S = 20.0  # a long-poll is held this long, under a proxy's usual idle limit
TICK_S = 5.0  # a WebSocket gets a `tick` this often
HELLO_S = 5.0  # a WebSocket has this long to say `hello`
CHECK_S = 5.0  # with no file notifications, the server looks at the planning files this often
IDLE_STOP_S = 1800.0  # a board started with `--stop-idle` stops after this long with no client
# <push_every>:<hold>:<tick>:<hello>[:<check>[:<idle_stop>]]: four, five or six fields
TEST_ENV = "CHANTIER_API_TEST_TIMES"
FEWEST = 4  # fields of the test variable: the first four, the others at their shipped value
DEFAULTS = (PUSH_EVERY_S, HOLD_S, TICK_S, HELLO_S, CHECK_S, IDLE_STOP_S)

MAX_FRAME = 4 * 1024 * 1024  # bytes of a frame, or of an HTTP body, from a client
MAX_SUBS = 32  # subscriptions of one connection, or subs of one long-poll
MAX_POLLS = 16  # long-polls held at once: under the thread pool's 40, which they would starve
MAX_CLIENTS = 64  # WebSockets past `welcome`
MAX_WAITING = 16  # WebSockets that have not said `hello` yet
PING_S = 20.0  # the WebSocket library's ping interval and timeout
MAX_LINES = 200  # journal lines of one `events` event


def _test() -> tuple[float, ...] | None:
    """The test's times, the fields it leaves out at their shipped value; None for no variable,
    or one that is not four to six positive numbers."""
    text = os.environ.get(TEST_ENV)
    if not text:
        return None
    try:
        given = tuple(float(x) for x in text.split(":"))
    except ValueError:
        return None
    if not FEWEST <= len(given) <= len(DEFAULTS) or min(given) <= 0:
        return None
    return given + DEFAULTS[len(given) :]


def _pick(index: int) -> float:
    test = _test()
    return test[index] if test else DEFAULTS[index]


def push_every_s() -> float:
    return _pick(0)


def hold_s() -> float:
    return _pick(1)


def tick_s() -> float:
    return _pick(2)


def hello_s() -> float:
    return _pick(3)


def check_s() -> float:
    return _pick(4)


def idle_stop_s() -> float:
    return _pick(5)
