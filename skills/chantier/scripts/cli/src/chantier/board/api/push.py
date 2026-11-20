"""The API's push: what clients watch, and the loop that looks at it. `PushLoop.poll(now)` takes
the monotonic time (a test drives it with no sleep and no thread, as `HubLoop.poll`): every
`PUSH_EVERY_S`, for each topic and arguments that someone watches, it reads the rev and, when it
moved, sends the whole value once to every watcher. A topic nobody watches costs nothing."""

from __future__ import annotations

import json
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from chantier.board import key as keys
from chantier.board.api import ops, protocol, times, topics
from chantier.board.context import Context
from chantier.core import clock
from chantier.core.errors import ChantierError

JOIN_S = 5.0
KEY_CLOSE = 4401  # the close code of a socket whose key was replaced
Sink = Callable[[dict[str, Any]], None]
UNKNOWN_TOPIC = "unknown topic {name!r}"
TOO_MANY_POLLS = f"too many long-polls: at most {times.MAX_POLLS} at once"


@dataclass(eq=False)  # hashable by identity: a set holds them
class Subscription:
    id: str
    topic: str
    args: Any  # the topic's checked arguments
    sink: Sink
    last: str | None  # the rev this watcher has


@dataclass
class Want:
    """One sub of a long-poll: the client's key, the topic, its arguments and the last rev seen."""

    key: str
    topic: str
    args: Any
    rev: str | None


class PushLoop:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self._subs: set[Subscription] = set()
        self._lock = threading.Lock()
        self._next: float | None = None
        self._polls = 0  # long-polls held now

    def watching(self) -> int:
        with self._lock:
            return len(self._subs)

    def subscribe(
        self, name: str, args: Any, sink: Sink, last: str | None = None, sub_id: str = ""
    ) -> Subscription | ops.Result:
        """Watch a topic: 404 for an unknown topic or project, 400 for bad arguments. The first
        event is sent at once when the value's rev is not `last` (always, for no `last`)."""
        model = protocol.TOPIC_ARGS.get(name)
        if model is None:
            return ops.fail(404, UNKNOWN_TOPIC.format(name=name))
        checked = ops.checked(model, args)
        if isinstance(checked, str):
            return ops.fail(400, checked)
        reading = topics.read(self.ctx, name, checked, last)
        if reading is None:
            return ops.fail(404, ops.NOT_FOUND)
        sub = Subscription(sub_id, name, checked, sink, reading[0])
        if reading[1] is not None:
            sink(self._event(sub, reading[0], reading[1]))
        with self._lock:
            self._subs.add(sub)
        return sub

    def unsubscribe(self, sub: Subscription) -> None:
        with self._lock:
            self._subs.discard(sub)

    @staticmethod
    def _event(sub: Subscription, rev: str, data: dict[str, Any]) -> dict[str, Any]:
        return {"sub": sub.id, "topic": sub.topic, "rev": rev, "data": data, "now": clock.now()}

    def due(self, now: float) -> bool:
        return self._next is None or now >= self._next

    def poll(self, now: float) -> None:
        """One look at every watched topic, when due; one read per topic, arguments and rev."""
        if not self.due(now):
            return
        self._next = now + times.push_every_s()
        self._close_stale_keys()
        with self._lock:
            subs = list(self._subs)  # a snapshot: sinks and unsubscribes change the set meanwhile
        groups: dict[tuple[str, str, str | None], list[Subscription]] = {}
        for sub in subs:
            key = (sub.topic, json.dumps(sub.args.model_dump(), sort_keys=True), sub.last)
            groups.setdefault(key, []).append(sub)
        for members in groups.values():
            self._send(members)

    def _close_stale_keys(self) -> None:
        """A WebSocket whose key is no longer the board's (`--new-key` while it runs) is closed
        with 4401 at this pass."""
        current = self.ctx.key.current()
        for conn in list(self.ctx.sockets):
            if conn.welcomed and not keys.is_good(conn.credential, current):
                conn.drop(KEY_CLOSE)

    def _send(self, members: list[Subscription]) -> None:
        first = members[0]
        try:
            reading = topics.read(self.ctx, first.topic, first.args, first.last)
        except (OSError, ValueError, KeyError, ChantierError):
            return  # the record could not be read just now: the next pass looks again
        except Exception as e:  # one topic's fault never ends the loop, nor the server
            print(
                f"board: the API's push skipped {first.topic}: "
                f"{' '.join(str(e).split()) or type(e).__name__}",
                file=sys.stderr,
                flush=True,
            )
            return
        if reading is None or reading[1] is None:
            return
        for sub in members:
            sub.last = reading[0]
            try:
                sub.sink(self._event(sub, reading[0], reading[1]))
            except Exception:  # a sink that fails is a watcher that is gone
                self.unsubscribe(sub)

    def hold(
        self, wants: list[Want], seconds: float | None = None
    ) -> list[dict[str, Any]] | ops.Result:
        """A long-poll: answers at once with an event per sub whose rev is null or not the
        current one, else holds up to `seconds` (`HOLD_S`) for the loop to find one, and gives
        the events (none at the hold's end). The subs count as watching for the hold."""
        with self._lock:
            if self._polls >= times.MAX_POLLS:
                return ops.fail(429, TOO_MANY_POLLS)
            self._polls += 1
        try:
            return self._hold(wants, seconds)
        finally:
            with self._lock:
                self._polls -= 1

    def _hold(self, wants: list[Want], seconds: float | None) -> list[dict[str, Any]] | ops.Result:
        box = _Box()
        held: list[Subscription] = []
        for want in wants:
            got = self.subscribe(want.topic, want.args, box.sink(want.key), want.rev)
            if isinstance(got, ops.Result):
                for sub in held:
                    self.unsubscribe(sub)
                return got
            held.append(got)
        box.arrived.wait(times.hold_s() if seconds is None else seconds)
        for sub in held:
            self.unsubscribe(sub)
        return box.items


class _Box:
    """The events a long-poll has been sent, and the signal that one came."""

    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []
        self.arrived = threading.Event()

    def sink(self, key: str) -> Sink:
        def put(event: dict[str, Any]) -> None:
            data = {k: event[k] for k in ("topic", "rev", "data")}
            self.items.append({"key": key, **data})
            self.arrived.set()

        return put


class PushThread:
    """`PushLoop` in a daemon thread. A loop that dies ends the server: `on_death` is called
    after an error line on stderr."""

    def __init__(self, loop: PushLoop, on_death: Callable[[], None]) -> None:
        self.loop, self.on_death = loop, on_death
        self._done = threading.Event()
        self._thread = threading.Thread(target=self._run, name="api-push", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _run(self) -> None:
        try:
            while not self._done.wait(times.push_every_s()):
                self.loop.poll(time.monotonic())
        except Exception as e:
            print(
                f"board: the API's push stopped: {' '.join(str(e).split()) or type(e).__name__}",
                file=sys.stderr,
                flush=True,
            )
            self.on_death()

    def stop(self) -> None:
        self._done.set()
        if self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(JOIN_S)
