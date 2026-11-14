"""Where the board listens, the address the user can reach, and the probe of a running board."""

from __future__ import annotations

import ipaddress
import json
import re
import socket
import urllib.error
import urllib.request
from typing import Any

from chantier.board.key import HEADER
from chantier.core.errors import ChantierError
from chantier.core.repo import Repo
from chantier.playbook.config import FILE, MAX_PORT, load_board

DEFAULT_HOST, DEFAULT_PORT = "0.0.0.0", 8765
EVERYWHERE = ("0.0.0.0", "::", "")


def settings(repo: Repo, host: str | None, port: int | None) -> tuple[str, int]:
    """The address: the command's options, else `chantier.yaml`'s `board` key, else the default.
    Port 0 is the system's pick, from the option only."""
    found, problems = load_board(repo.root / FILE)
    if problems:
        raise ChantierError(problems[0])
    host = host or found.get("host") or DEFAULT_HOST
    port = port if port is not None else found.get("port", DEFAULT_PORT)
    if not 0 <= port <= MAX_PORT:
        raise ChantierError(f"--port {port}: a port is 0 (any free one) to 65535", 1)
    if re.search(r"\s", host):
        raise ChantierError(f"--host {host!r}: an address holds no whitespace", 1)
    return host, port


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


def _base(host: str, port: int) -> str:
    return f"http://{_bracket(_loopback_of(host))}:{port}"


def _call(base: str, key: str, method: str, route: str, body: Any = None) -> Any:
    address = f"{base}{route}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {HEADER: key, **({"Content-Type": "application/json"} if data else {})}
    request = urllib.request.Request(address, data, headers, method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=2) as r:
        return json.loads(r.read(5_000_000))


def probe(host: str, port: int, key: str) -> dict[str, Any] | str | None:
    """None: nothing answers. A dict: a chantier board's `/api/board`, behind this key. "other":
    something else holds the port."""
    try:
        data = _call(_base(host, port), key, "GET", "/api/board")
    except (urllib.error.HTTPError, ValueError):
        return "other"
    except OSError:
        return None
    return data if isinstance(data, dict) and data.get("board") is True else "other"


def register_seat(host: str, port: int, key: str, project: str, session: str) -> bool:
    """Add a seat to the board already running there; True when it took it."""
    try:
        _call(
            _base(host, port), key, "POST", "/api/seats", {"project": project, "session": session}
        )
    except (OSError, ValueError):
        return False
    return True
