"""Where the board listens, the address the user can reach, and the probe of a running board."""

from __future__ import annotations

import ipaddress
import json
import re
import socket
import urllib.error
import urllib.request
from http import HTTPStatus
from typing import Any

from chantier.board.guard import NEEDS_KEY
from chantier.board.key import HEADER
from chantier.core.errors import ChantierError
from chantier.core.repo import Repo
from chantier.playbook.board_check import MAX_PORT
from chantier.playbook.layers import load_board

DEFAULT_HOST, DEFAULT_PORT = "127.0.0.1", 8765
NETWORK = "network"
EVERYWHERE = ("0.0.0.0", "::", "")


def settings(repo: Repo, host: str | None, port: int | None) -> tuple[str, int, bool]:
    """The address: the command's options, else `chantier.yaml`'s `board` key, else the default.
    Port 0 is the system's pick, from the option only. The third value is True when
    `board.host: network` found no local network address at this start (the board then stays
    on this machine)."""
    found, problems = load_board(repo)
    if problems:
        raise ChantierError(problems[0])
    no_network = False
    if not host and found.get("host") == NETWORK:
        if is_loopback(_default_route_address()):
            host, no_network = DEFAULT_HOST, True
        else:
            host = "0.0.0.0"
    host = host or DEFAULT_HOST
    port = port if port is not None else found.get("port", DEFAULT_PORT)
    if not 0 <= port <= MAX_PORT:
        raise ChantierError(f"--port {port}: a port is 0 (any free one) to 65535", 1)
    if re.search(r"\s", host):
        raise ChantierError(f"--host {host!r}: an address holds no whitespace", 1)
    return host, port, no_network


def is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def _default_route_address() -> str:
    """This machine's address on the network of its default route; a UDP `connect` sends
    nothing. 127.0.0.1 when the machine has no network."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("192.0.2.1", 9))
            return str(s.getsockname()[0])
        except OSError:
            return "127.0.0.1"


def reachable(host: str) -> str:
    """The address in the link: the `--host` when it is a specific one, else the machine's."""
    return _default_route_address() if host in EVERYWHERE else host


def _bracket(host: str) -> str:
    return f"[{host}]" if ":" in host and not host.startswith("[") else host


def url(host: str, port: int, key: str | None = None) -> str:
    link = f"http://{_bracket(reachable(host))}:{port}/"
    return f"{link}?k={key}" if key else link


def _loopback_of(host: str) -> str:
    return {"0.0.0.0": "127.0.0.1", "": "127.0.0.1", "::": "::1"}.get(host, host)


def local_url(host: str, port: int, key: str | None = None) -> str | None:
    """The 127.0.0.1 (or `[::1]`) link, with the key when one is given, when the board listens
    on every address and its main link is not already a loopback one; None otherwise."""
    if host not in EVERYWHERE or is_loopback(reachable(host)):
        return None
    return f"{_base(host, port)}/?k={key}" if key else f"{_base(host, port)}/"


def _base(host: str, port: int) -> str:
    return f"http://{_bracket(_loopback_of(host))}:{port}"


def loopback_base(host: str, port: int) -> str:
    """The board's address on this machine's loopback, for a client of this machine."""
    return _base(host, port) + "/"


def _call(  # noqa: PLR0913, PLR0917 - the address, the key, the request, its body and its wait
    base: str, key: str, method: str, route: str, body: Any = None, timeout: float = 2
) -> Any:
    address = f"{base}{route}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {HEADER: key, **({"Content-Type": "application/json"} if data else {})}
    request = urllib.request.Request(address, data, headers, method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=timeout) as r:
        return json.loads(r.read(5_000_000))


def _says_needs_key(e: urllib.error.HTTPError) -> bool:
    try:
        return NEEDS_KEY in e.read(10_000).decode("utf-8", "replace")
    except OSError:
        return False


def probe(host: str, port: int, key: str) -> dict[str, Any] | str | None:
    """None: nothing answers. A dict: a chantier board's `/api/board`, behind this key.
    "another-key": a chantier board that refused this key. "other": something else holds the
    port."""
    try:
        data = _call(_base(host, port), key, "GET", "/api/board")
    except urllib.error.HTTPError as e:
        return (
            "another-key" if e.code == HTTPStatus.UNAUTHORIZED and _says_needs_key(e) else "other"
        )
    except ValueError:
        return "other"
    except OSError:
        return None
    return data if isinstance(data, dict) and data.get("board") is True else "other"


def register_seat(host: str, port: int, key: str, project: str, session: str) -> bool:
    """Add a seat to the board already running there; True when it took it."""
    try:
        _call(
            _base(host, port),
            key,
            "POST",
            "/api/v1/call/seats.register",
            {"project": project, "session": session},
        )
    except (OSError, ValueError):
        return False
    return True


def call_op(host: str, port: int, key: str, op: str, timeout: float) -> tuple[int, dict[str, Any]]:
    """One op with no arguments, over HTTP, on the board there: the HTTP status and the answer's
    body (`ok`, `data`, `error`). An OSError or a ValueError when nothing answers in `timeout`
    seconds or the answer is not JSON."""
    try:
        data = _call(_base(host, port), key, "POST", f"/api/v1/call/{op}", {}, timeout)
        status: int = HTTPStatus.OK
    except urllib.error.HTTPError as e:
        status, data = e.code, json.loads(e.read(100_000).decode("utf-8", "replace") or "null")
    return status, data if isinstance(data, dict) else {}
