"""The board's HTTP server and its command."""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from chantier.board.collect import collect, settings
from chantier.board.render import esc, file_link, page, project_name, render_body
from chantier.commands.registry import NO_BATCH, Subparsers, add_command
from chantier.core.errors import EXIT_EXTERNAL, ChantierError
from chantier.core.files import retry
from chantier.core.repo import Repo
from chantier.core.seat import read_seat

SEAT_CHECK_S = 10  # the board looks at the seat at least this often, and at each request


FILE_LIMIT = 1_000_000  # bytes of a file shown


HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; "
    "form-action 'none'; frame-ancestors 'none'",
}


def _inside(root: Path, rel: str) -> Path | None:
    """The path in the planning folder, or None when it leaves it or does not exist."""
    if (
        "\x00" in rel
        or rel.startswith(("/", "\\"))
        or re.match(r"^[A-Za-z]:", rel)
        or Path(rel).is_absolute()
    ):
        return None
    try:
        target = (root / rel).resolve()
    except (OSError, ValueError):
        return None
    return target if target.is_relative_to(root) and target.exists() else None


def _visible(root: Path, child: Path) -> bool:
    try:
        return child.resolve().is_relative_to(root)
    except OSError:
        return False


def _listing(root: Path, target: Path) -> str:
    entries = []
    for child in sorted(retry(lambda: list(target.iterdir()))):
        if _visible(root, child):
            label = child.name + ("/" if child.is_dir() else "")
            entries.append(f"<li>{file_link(child.relative_to(root).as_posix(), label)}</li>")
    return "".join(entries)


def _file_page(root: Path, target: Path, name: str) -> str:
    shown = target.relative_to(root).as_posix() if target != root else "."
    if target.is_dir():
        body = f"<section><h2>{esc(shown)}</h2><ul>{_listing(root, target)}</ul></section>"
    else:
        raw = retry(target.read_bytes)
        text = raw[:FILE_LIMIT].decode("utf-8", errors="replace")
        note = '<p class="muted">cut at 1 MB</p>' if len(raw) > FILE_LIMIT else ""
        body = f"<section><h2>{esc(shown)}</h2><pre>{esc(text)}</pre>{note}</section>"
    return page(body, name, title=f"{name}: {shown}")


NOT_FOUND = (404, "not found\n", "text/plain")


def _route(repo: Repo, seat: str | None, name: str, raw_path: str) -> tuple[int, str, str]:
    """The answer to a GET: status, body, content type."""
    url = urlparse(raw_path)
    root = repo.changes.resolve()
    try:
        if url.path == "/":
            data = collect(repo, seat)
            return 200, page(render_body(data), name, data["updated"]), "text/html"
        if url.path == "/api/status":
            body = json.dumps(collect(repo, seat), indent=2, ensure_ascii=False) + "\n"
            return 200, body, "application/json"
        if url.path == "/file":
            target = _inside(root, parse_qs(url.query).get("p", [""])[0])
            if target is None:
                return NOT_FOUND
            return 200, _file_page(root, target, name), "text/html"
    except (OSError, ValueError, KeyError, ChantierError):
        return 500, "the record could not be read just now\n", "text/plain"
    return NOT_FOUND


def _handler(repo: Repo, seat: str | None, stop: Callable[[], None]) -> type:
    name = project_name(repo)

    class Handler(BaseHTTPRequestHandler):
        server_version = "chantier-board"
        sys_version = ""

        def _send(
            self,
            code: int,
            body: str,
            ctype: str,
            head: bool = False,
            extra: dict[str, str] | None = None,
        ) -> None:
            raw = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", f"{ctype}; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            for key, value in {**HEADERS, **(extra or {})}.items():
                self.send_header(key, value)
            self.end_headers()
            if not head:
                self.wfile.write(raw)

        def _serve(self, head: bool) -> None:
            code, body, ctype = _route(repo, seat, name, self.path)
            self._send(code, body, ctype, head)
            if seat and _seat_gone(repo, seat):
                stop()

        def do_GET(self) -> None:
            self._serve(False)

        def do_HEAD(self) -> None:
            self._serve(True)

        def _refuse(self) -> None:
            self._send(405, "read only: GET and HEAD\n", "text/plain", extra={"Allow": "GET, HEAD"})

        do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _refuse

        def log_message(self, *args: Any) -> None:
            pass

    return Handler


def _seat_gone(repo: Repo, seat: str) -> bool:
    """The seat no longer names this session (left, or taken over); an unreadable file is not."""
    try:
        held = read_seat(repo)
    except (ChantierError, OSError):
        return False
    return not held or held.session != seat


def is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def _probe_url(host: str, port: int) -> str:
    where = {"0.0.0.0": "127.0.0.1", "": "127.0.0.1", "::": "::1"}.get(host, host)
    return f"http://{'[' + where + ']' if ':' in where else where}:{port}/api/status"


def _probe(host: str, port: int) -> dict[str, Any] | str | None:
    """None: nothing answers. A dict: a chantier board's status. "other": something else holds
    it."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(_probe_url(host, port), timeout=2) as r:
            data = json.loads(r.read(5_000_000))
    except urllib.error.HTTPError:
        return "other"
    except ValueError:
        return "other"
    except OSError:
        return None
    return data if isinstance(data, dict) and data.get("board") is True else "other"


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    # On Windows SO_REUSEADDR lets a second socket take a port that is in use: never there.
    allow_reuse_address = sys.platform != "win32"


def _not_started(reason: object) -> ChantierError:
    return ChantierError(f"board not started: {' '.join(str(reason).split())}", EXIT_EXTERNAL)


def _wait_for_takeover(repo: Repo, host: str, port: int, seat: str | None) -> str | None:
    """A board of this folder already answers: its message when it is this seat's, else wait
    for it to leave."""
    found = _probe(host, port)
    if (
        not isinstance(found, dict)
        or found.get("planning_folder") != repo.changes.resolve().as_posix()
    ):
        return None
    if found.get("seat") == seat:
        return f"board already running at http://{host}:{port}/"
    for _ in range(SEAT_CHECK_S * 2 * 2):  # at most twice the seat check's period
        time.sleep(0.5)
        if _probe(host, port) is None:
            break
    return None


def _bind(repo: Repo, host: str, port: int, seat: str | None) -> ThreadingHTTPServer:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    cls = type("Server", (_Server,), {"address_family": family})
    holder: list[ThreadingHTTPServer] = []

    def stop() -> None:
        threading.Thread(target=holder[0].shutdown, daemon=True).start()

    try:
        server: ThreadingHTTPServer = cls((host, port), _handler(repo, seat, stop))
    except (OSError, OverflowError) as e:
        raise _not_started(e) from e
    holder.append(server)
    return server


def _watch(repo: Repo, seat: str, server: ThreadingHTTPServer) -> None:
    def watch() -> None:
        while not threading.Event().wait(SEAT_CHECK_S):
            if _seat_gone(repo, seat):
                server.shutdown()
                return

    threading.Thread(target=watch, daemon=True).start()


def serve(repo: Repo, host: str, port: int, seat: str | None) -> list[str]:
    if not repo.changes.is_dir():
        raise _not_started(f"no planning folder at {repo.changes}")
    running = _wait_for_takeover(repo, host, port, seat)
    if running:
        return [running]
    server = _bind(repo, host, port, seat)
    print(f"board on http://{host}:{port}/ over {repo.changes.resolve().as_posix()}", flush=True)
    if not is_loopback(host):
        every = ", on every network of this machine" if host in ("0.0.0.0", "::") else ""
        print(f"board: listens beyond this machine ({host}{every}), no password", flush=True)
    if seat:
        _watch(repo, seat, server)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return []


def board(args: argparse.Namespace) -> list[str]:
    repo = Repo.find(readonly=True)
    host, port = settings(repo, args.host, args.port)
    return serve(repo, host, port, args.seat)


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "board",
        board,
        "serve the planning folder's batch, CRs, inbox and backlog as a read-only web page, "
        "for the user in remote; writes nothing, no password",
        NO_BATCH,
    )
    s.add_argument(
        "--host",
        help="the address to listen on (default: chantier.yaml's board.host, else 127.0.0.1)",
    )
    s.add_argument(
        "--port", type=int, help="the port (default: chantier.yaml's board.port, else 8765)"
    )
    s.add_argument(
        "--seat",
        metavar="SESSION",
        help="the Chief of Staff session this board is for: it stops when the seat no "
        "longer names it",
    )
