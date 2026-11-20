"""The API's times and limits, and the one environment variable that shortens the times (the
tests': read here and nowhere else)."""

from __future__ import annotations

import os

PUSH_EVERY_S = 2.0  # the push loop looks at what clients watch this often
HOLD_S = 20.0  # a long-poll is held this long, under a proxy's usual idle limit
TICK_S = 5.0  # a WebSocket gets a `tick` this often
HELLO_S = 5.0  # a WebSocket has this long to say `hello`
TEST_ENV = "CHANTIER_API_TEST_TIMES"  # <push_every>:<hold>:<tick>:<hello>

MAX_FRAME = 4 * 1024 * 1024  # bytes of a frame, or of an HTTP body, from a client
MAX_SUBS = 32  # subscriptions of one connection, or subs of one long-poll
MAX_POLLS = 16  # long-polls held at once: under the thread pool's 40, which they would starve
MAX_CLIENTS = 64  # WebSockets past `welcome`
MAX_WAITING = 16  # WebSockets that have not said `hello` yet
PING_S = 20.0  # the WebSocket library's ping interval and timeout
MAX_LINES = 200  # journal lines of one `events` event


def _test() -> tuple[float, float, float, float] | None:
    text = os.environ.get(TEST_ENV)
    if not text:
        return None
    try:
        a, b, c, d = (float(x) for x in text.split(":"))
    except ValueError:
        return None
    return (a, b, c, d) if min(a, b, c, d) > 0 else None


def _pick(index: int, default: float) -> float:
    test = _test()
    return test[index] if test else default


def push_every_s() -> float:
    return _pick(0, PUSH_EVERY_S)


def hold_s() -> float:
    return _pick(1, HOLD_S)


def tick_s() -> float:
    return _pick(2, TICK_S)


def hello_s() -> float:
    return _pick(3, HELLO_S)
