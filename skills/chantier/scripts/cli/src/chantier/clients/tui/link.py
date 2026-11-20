"""The transport of `chantier live`: given a board's base address and key, the events of a list of
subscriptions, and the server's `now`.

The WebSocket first (`ws(s)://<base>/api/v1/ws`, the key in the header, `hello` with protocol 1),
then, in `auto`, the HTTP long-poll (`POST <base>/api/v1/poll`) when the socket does not open or
gives no `welcome` within 5 s. A refused key or protocol ends the run with the server's sentence,
never retried on the other transport. A lost link (no frame for 15 s, a close, a failed poll) is
retried every 5 s without end; the `events` subscriptions then carry `after: <the last seq seen>`,
so no journal line is lost or shown twice. It sends `hello`, `sub`, `unsub` and the poll, and
nothing else. `websockets` loads when a socket opens."""

from __future__ import annotations

import contextlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Generator, Iterator
from dataclasses import dataclass
from typing import Any

from chantier import __version__
from chantier.core.errors import EXIT_EXTERNAL, ChantierError

HEADER = "X-Chantier-Board-Key"
PROTOCOL = 1
CLIENT = f"chantier-live/{__version__}"
OPEN_S = 5.0  # the socket opens and says `welcome` within this, else HTTP (in `auto`)
SILENT_S = 15.0  # a socket with no frame for this long (three ticks missed) is lost
RETRY_S = 5.0  # a lost link is tried again this often
STEP_S = 1.0  # a socket's wait for a frame: the caller gets an `Idle` this often
POLL_S = 30.0  # a long-poll's own timeout, above the server's 20 s hold
MAX_FRAME = 64 * 1024 * 1024  # a project's state is one frame
BAD_KEY, OTHER_PROTOCOL = 4401, 4426
UNAUTHORIZED, NOT_FOUND = 401, 404
TRANSPORTS = ("auto", "ws", "http")

Wanted = tuple[str, str, dict[str, Any]]  # (key, topic, args)


@dataclass(frozen=True)
class Event:
    """A watched value: `key` the subscription's, `topic`, `data`, the server's `now`."""

    key: str
    topic: str
    data: dict[str, Any]
    now: str | None


@dataclass(frozen=True)
class Refused:
    """A subscription the server refused (a project that left the board: 404)."""

    key: str
    status: int
    error: str


@dataclass(frozen=True)
class Linked:
    """The link's state: `transport` (`ws` or `http`) while it is live, None while it is lost;
    `reason` why it was lost."""

    transport: str | None
    now: str | None = None
    reason: str = ""


@dataclass(frozen=True)
class Idle:
    """Nothing new; `now` the server's, when a frame said it."""

    now: str | None = None


Item = Event | Refused | Linked | Idle


class Lost(Exception):
    """The link is lost; the run goes on and tries again."""


class NoSocket(Exception):
    """The WebSocket did not open or said no `welcome`: HTTP, in `auto`."""


def refused(sentence: str) -> ChantierError:
    """A refused key or protocol: the run ends with the server's sentence."""
    return ChantierError(f"live: {' '.join(sentence.split())}", EXIT_EXTERNAL)


class Link:
    """One board's link. `want` sets the subscriptions (sent at once on a socket, at the next
    poll over HTTP); `items` yields what comes, without end, until a refusal raises. With a
    `deadline`, no poll is held past it: the poll is then lost, so the caller hears of it."""

    def __init__(
        self,
        base: str,
        key: str,
        transport: str = "auto",
        proxies: bool = False,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base = base if base.endswith("/") else base + "/"
        self.key, self.transport, self.proxies = key, transport, proxies
        self.sleep = sleep
        self.wants: dict[str, Wanted] = {}
        self.revs: dict[str, str] = {}
        self.seen: dict[str, int] = {}  # an `events` key: the last seq seen
        self.used: str | None = None  # the transport of the connection now
        self._ws: Any = None
        self._sent: set[str] = set()
        self.deadline: float | None = None  # a poll waits no later than this (`time.monotonic`)

    # what is watched

    def want(self, wants: list[Wanted]) -> None:
        new = {w[0]: w for w in wants}
        if self._ws is not None:
            for k in sorted(self._sent - new.keys()):
                self._send({"t": "unsub", "id": k})
                self._sent.discard(k)
            for k, w in new.items():
                if k not in self._sent:
                    self._sub(w)
        self.wants = new
        self.revs = {k: v for k, v in self.revs.items() if k in new}

    def _args(self, w: Wanted) -> dict[str, Any]:
        key, topic, args = w
        if topic == "events" and key in self.seen:
            return {**args, "after": self.seen[key]}
        return dict(args)

    def _took(self, key: str, topic: str, rev: Any, data: Any) -> Event | None:
        """An event received: its rev and last seq kept; None for a key no longer watched."""
        if key not in self.wants or not isinstance(data, dict):
            return None
        if isinstance(rev, str):
            self.revs[key] = rev
        if topic == "events":
            seqs = [x["seq"] for x in data.get("lines") or [] if type(x.get("seq")) is int]
            if seqs:
                self.seen[key] = max([*seqs, self.seen.get(key, 0)])
        return Event(key, topic, data, None)

    def _drop(self, key: str) -> None:
        self.wants.pop(key, None)
        self.revs.pop(key, None)
        self._sent.discard(key)

    # the connections

    def items(self) -> Generator[Item]:
        """What comes, without end; the socket is closed when the caller closes the iterator."""
        try:
            while True:
                try:
                    yield from self._connection()
                    reason = "the link closed"
                except Lost as e:
                    reason = str(e)
                self._close()
                self.used = None
                yield Linked(None, None, reason)
                self.sleep(RETRY_S)
        finally:
            self._close()

    def _connection(self) -> Iterator[Item]:
        self.revs.clear()  # whole values are taken again; `events` resume with `after`
        if self.transport == "http":
            yield from self._http()
            return
        try:
            welcome = self._open()
        except NoSocket as e:
            if self.transport == "ws":
                raise Lost(str(e)) from e
            yield from self._http()
            return
        yield from self._socket(welcome)

    def _close(self) -> None:
        ws, self._ws = self._ws, None
        self._sent.clear()
        if ws is not None:
            with contextlib.suppress(Exception):  # a socket already gone
                ws.__exit__(None, None, None)

    # the WebSocket

    def ws_address(self) -> str:
        parts = urllib.parse.urlsplit(urllib.parse.urljoin(self.base, "api/v1/ws"))
        scheme = "wss" if parts.scheme == "https" else "ws"
        return urllib.parse.urlunsplit((scheme, parts.netloc, parts.path, "", ""))

    def _open(self) -> dict[str, Any]:
        """The socket, `hello` said and `welcome` received; `NoSocket` otherwise."""
        from websockets.exceptions import InvalidStatus
        from websockets.sync.client import connect

        try:
            opened = connect(
                self.ws_address(),
                additional_headers={HEADER: self.key},
                user_agent_header=CLIENT,
                compression=None,
                proxy=True if self.proxies else None,
                open_timeout=OPEN_S,
                max_size=MAX_FRAME,
            )
        except InvalidStatus as e:
            if e.response.status_code == UNAUTHORIZED:
                raise refused(e.response.body.decode("utf-8", "replace")) from e
            raise NoSocket(f"the WebSocket was refused ({e.response.status_code})") from e
        except Exception as e:
            raise NoSocket(f"the WebSocket did not open: {e}") from e
        self._ws = opened.__enter__()  # the library's context: `_close` leaves it
        self._send({"t": "hello", "protocol": PROTOCOL, "client": CLIENT})
        deadline = time.monotonic() + OPEN_S
        while True:
            frame = self._frame(max(0.0, deadline - time.monotonic()), NoSocket)
            if frame is None:
                self._close()
                raise NoSocket("the WebSocket said no welcome within 5 s")
            if frame.get("t") == "welcome":
                return frame
            if frame.get("t") == "error":
                self._fault(frame)

    def _frame(self, wait: float, lost: type[Exception] = Lost) -> dict[str, Any] | None:
        """The next frame, None when none came within `wait`; a close is `lost`, or a refusal."""
        from websockets.exceptions import ConnectionClosed

        try:
            text = self._ws.recv(timeout=wait)
        except TimeoutError:
            return None
        except ConnectionClosed as e:
            code, reason = (e.rcvd.code, e.rcvd.reason) if e.rcvd is not None else (None, "")
            if code in (BAD_KEY, OTHER_PROTOCOL):
                raise refused(reason or f"the board closed the link ({code})") from e
            raise lost(f"the board closed the link ({code})") from e
        except OSError as e:
            raise lost(f"the link failed: {e}") from e
        try:
            frame = json.loads(text)
        except ValueError:
            return {}
        return frame if isinstance(frame, dict) else {}

    def _fault(self, frame: dict[str, Any]) -> None:
        error = str(frame.get("error") or frame.get("code"))
        if frame.get("code") in ("key", "protocol"):
            raise refused(error)
        raise Lost(f"the board ended the link: {error}")

    def _send(self, frame: dict[str, Any]) -> None:
        try:
            self._ws.send(json.dumps(frame))
        except Exception as e:  # the socket is gone: the next read says so
            raise Lost(f"the link failed: {e}") from e

    def _sub(self, w: Wanted) -> None:
        self._send({"t": "sub", "id": w[0], "topic": w[1], "args": self._args(w)})
        self._sent.add(w[0])

    def _socket(self, welcome: dict[str, Any]) -> Iterator[Item]:
        self.used = "ws"
        yield Linked("ws", welcome.get("now"))
        for w in list(self.wants.values()):
            self._sub(w)
        heard = time.monotonic()
        while True:
            frame = self._frame(STEP_S)
            if frame is None:
                if time.monotonic() - heard > SILENT_S:
                    raise Lost("no frame for 15 s")
                yield Idle()
                continue
            heard = time.monotonic()
            yield self._socket_item(frame)

    def _socket_item(self, frame: dict[str, Any]) -> Item:
        kind, now = frame.get("t"), frame.get("now")
        if kind == "event":
            sub, topic = str(frame.get("sub")), str(frame.get("topic"))
            got = self._took(sub, topic, frame.get("rev"), frame.get("data"))
            return Event(got.key, got.topic, got.data, now) if got else Idle(now)
        if kind == "result" and frame.get("ok") is False:
            key = str(frame.get("id"))
            self._drop(key)
            return Refused(key, int(frame.get("status") or 0), str(frame.get("error")))
        if kind == "error":
            self._fault(frame)
        return Idle(now if isinstance(now, str) else None)

    # the HTTP long-poll

    def _opener(self) -> urllib.request.OpenerDirector:
        if self.proxies:
            return urllib.request.build_opener()
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _post(self, subs: list[dict[str, Any]], timeout: float = POLL_S) -> dict[str, Any]:
        request = urllib.request.Request(
            urllib.parse.urljoin(self.base, "api/v1/poll"),
            json.dumps({"subs": subs}).encode("utf-8"),
            {HEADER: self.key, "Content-Type": "application/json", "User-Agent": CLIENT},
            method="POST",
        )
        with self._opener().open(request, timeout=timeout) as r:
            data = json.loads(r.read())
        return data if isinstance(data, dict) else {}

    def _poll_body(self, keys: list[str], fresh: bool = False) -> list[dict[str, Any]]:
        return [
            {
                "key": k,
                "topic": self.wants[k][1],
                "args": self._args(self.wants[k]),
                "rev": None if fresh else self.revs.get(k),
            }
            for k in keys
        ]

    def _poll(self, keys: list[str], fresh: bool = False) -> dict[str, Any]:
        """One poll; a refused key ends the run, a 404 is `LookupError`, any other fault lost."""
        timeout = OPEN_S if fresh else POLL_S
        if self.deadline is not None:  # a lapsed deadline: the poll fails at once, lost
            timeout = max(0.05, min(timeout, self.deadline - time.monotonic()))
        try:
            return self._post(self._poll_body(keys, fresh), timeout)
        except urllib.error.HTTPError as e:
            if e.code == UNAUTHORIZED:
                raise refused(e.read(10_000).decode("utf-8", "replace")) from e
            if e.code == NOT_FOUND:
                raise LookupError(e.code) from e
            raise Lost(f"a poll failed ({e.code})") from e
        except (OSError, ValueError) as e:
            raise Lost(f"a poll failed: {e}") from e

    def _http(self) -> Iterator[Item]:
        self.used = None
        while True:
            try:
                answer = self._poll(list(self.wants))
            except LookupError:
                yield from self._sort_refused()
                continue
            if self.used is None:
                self.used = "http"
                yield Linked("http", answer.get("now"))
            yield from self._events_of(answer)

    def _events_of(self, answer: dict[str, Any]) -> Iterator[Item]:
        now = answer.get("now") if isinstance(answer.get("now"), str) else None
        found = False
        for e in answer.get("events") or []:
            got = self._took(str(e.get("key")), str(e.get("topic")), e.get("rev"), e.get("data"))
            if got:
                found = True
                yield Event(got.key, got.topic, got.data, now)
        if not found:
            yield Idle(now)

    def _sort_refused(self) -> Iterator[Item]:
        """A poll refused with 404: each subscription asked alone (an answer at once, its rev
        not given); the ones refused are dropped."""
        for k in list(self.wants):
            try:
                answer = self._poll([k], fresh=True)
            except LookupError:
                self._drop(k)
                yield Refused(k, NOT_FOUND, "not found")
                continue
            yield from self._events_of(answer)
