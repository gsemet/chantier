"""The board's links: pure address text, with no import of the rest of chantier."""

from __future__ import annotations

import ipaddress
import socket

EVERYWHERE = ("0.0.0.0", "::", "")


def is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def default_route_address() -> str:
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
    return default_route_address() if host in EVERYWHERE else host


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
    return f"{base(host, port)}/?k={key}" if key else f"{base(host, port)}/"


def base(host: str, port: int) -> str:
    return f"http://{_bracket(_loopback_of(host))}:{port}"


def loopback_base(host: str, port: int) -> str:
    """The board's address on this machine's loopback, for a client of this machine."""
    return base(host, port) + "/"
