"""`chantier board`: a read-only web view of the planning folder, for the user in remote.

It serves the record the CLI already keeps, nothing more: the batch, its CRs, the inbox and the
backlog, as a small page that reloads itself, as JSON, and the planning folder's own files as
text. It writes no file and takes no lock, before, while and after serving; it knows no role; it
uses the standard library only. There is no authentication: the default address is the local
machine's, and a wider one is the user's word (`chantier.yaml`, or an option of the command).

Its data is computed in memory at each request by the functions that write the STATUS files
(`status.dashboard_view`, `status.batch_view`), so the board says what the next `STATUS.json`
would say, and works before any exists.
"""
from __future__ import annotations

import html
import ipaddress
import json
import posixpath
import re
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from . import playbook as pb
from .commands import _read_seat
from .lifecycle import stage_layout
from .state import (EXIT_EXTERNAL, ChantierError, Repo, _retry, age_minutes, read_batch_json,
                    read_events)
from .status import batch_view, dashboard_view, forge_word, shape_word, steering_word

DEFAULT_HOST, DEFAULT_PORT = "127.0.0.1", 8765
SEAT_CHECK_S = 10  # the board looks at the seat at least this often, and at each request
REFRESH_S = 30
EVENTS_SHOWN = 12
EVENTS_HIDDEN = ("heartbeat", "cost")
FILE_LIMIT = 1_000_000  # bytes of a file shown
HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; "
                               "form-action 'none'; frame-ancestors 'none'",
}


# ---- the data -----------------------------------------------------------------------------------

def _tail_events(folder: Path) -> list[dict]:
    events = [e for e in _retry(read_events, folder) if e.get("kind") not in EVENTS_HIDDEN]
    return events[-EVENTS_SHOWN:]


def collect(repo: Repo, seat: str | None) -> dict:
    """What the next `STATUS.json` of the index would say, the batch's own view, its recent
    events, and the board's three own fields. Nothing is written."""
    view = dashboard_view(repo, stage_layout(repo))
    batch, events = None, []
    for folder in repo.batch_folders():
        batch = batch_view(repo, read_batch_json(folder / "batch.json"), folder)
        events = _tail_events(folder)
    return {**view, "batch": batch, "events": events,
            "planning_folder": repo.changes.resolve().as_posix(), "seat": seat, "board": True}


# ---- the page -----------------------------------------------------------------------------------

def _e(text) -> str:
    return html.escape(str(text), quote=True)


def _file_link(path: str, label: str) -> str:
    return f'<a href="/file?p={quote(path, safe="/")}">{_e(label)}</a>'


def _url_link(url: str | None, label: str) -> str:
    """A link only for an http(s) URL; anything else is text."""
    if url and re.match(r"https?://", url):
        return f'<a href="{_e(url)}">{_e(label)}</a>'
    return _e(label)


def subject(title: str) -> str:
    return re.sub(r"^﻿?[#\s]*(?:Change Specification:\s*)?", "", title or "").strip()


def _money(usd) -> str:
    return "-" if usd is None else f"${usd:.2f}"


def _ago(ts: str | None) -> str:
    try:
        minutes = age_minutes(ts)
    except ValueError:
        return str(ts)
    if minutes is None:
        return "-"
    minutes = int(minutes)
    return f"{minutes} min ago" if minutes < 120 else f"{minutes // 60} h ago"


def _details(summary: str, body: str, open_: bool = False) -> str:
    return f'<details class="sec"{" open" if open_ else ""}><summary>{summary}</summary>{body}</details>'


def _cr_row(c: dict, batch_folder: str) -> str:
    spec = posixpath.normpath(f"{batch_folder}/{c['specification']}") if c.get("specification") else None
    title = _file_link(spec, subject(c["title"])) if spec else _e(subject(c["title"]))
    word = forge_word([c.get("pr")])
    number = re.search(r"(\d+)/?$", c["pr"]) if c.get("pr") else None
    pr = _url_link(c.get("pr"), f"{word} #{number[1]}" if number else word) if c.get("pr") else "-"
    blocked = f'<div class="blk">{_e(c["blocked"])}</div>' if c.get("blocked") else ""
    waits = f'<div class="muted">waits for {_e(", ".join(c["waits"]))}</div>' if c.get("waits") else ""
    return (f'<div class="cr"><span class="dot {_e(c["severity"])}"></span><div class="crbody">'
            f'<div><b>{_e(c["cr"])}</b> {title}</div>'
            f'<div class="muted">{_e(c["label"])} · round {_e(c["round"])} · {_e(_money(c["cost_usd"]))}'
            f' · {pr}</div>{blocked}{waits}</div></div>')


def _batch_section(batch: dict, slots: dict | None, events: list[dict]) -> str:
    priced = batch["priced"]
    spent, budget = batch["spent_usd"], batch["budget_usd"]
    figures = ("unknown" if not priced else f"${spent:.2f}") + (f" of ${budget:g}" if budget else "")
    pct = min(100, int(100 * spent / budget)) if priced and budget else 0
    bar = f'<div class="bar"><div style="width:{pct}%"></div></div>' if priced and budget else ""
    asks = batch["asks_unread"]
    facts = [f"spent {figures}"]
    if slots:
        facts.append(f"slots {slots['taken']} taken, {slots['total'] - slots['taken']} free")
    facts.append("heartbeat stopped" if batch.get("heartbeat_stopped")
                 else f"heartbeat {_ago(batch['heartbeat'])}")
    if batch["orders_pending"]:
        facts.append(f"{batch['orders_pending']} order(s) pending")
    ask = f' · <b>{asks} question(s) waiting</b>' if asks else ""
    rows = "".join(_cr_row(c, batch["folder"]) for c in batch["crs"]) or '<p class="muted">No CR.</p>'
    lines = "".join(
        f'<li><span class="muted">{_e(ev.get("t", "")[11:16])}</span> {_e(ev.get("actor", ""))} '
        f'<b>{_e(ev.get("kind", ""))}</b> {_e(ev.get("cr") or "")}</li>' for ev in reversed(events))
    return (f'<section><h2>{_e(batch["batch"])} <span class="pill">{_e(batch["state"])}</span>'
            f'<span class="pill">{_e(steering_word(batch["steering"]))}</span>'
            f'<span class="pill">{_e(shape_word(batch["mode"]))}</span></h2>{bar}'
            f'<div class="muted">{_e(" · ".join(facts))}{ask}</div>{rows}'
            f'{_details("Recent events", f"<ul class=ev>{lines}</ul>") if lines else ""}</section>')


def _item_rows(items: list[dict]) -> str:
    return "<ul>" + "".join(
        f'<li>{_file_link(i["path"], i["item"])}'
        f'{" <span class=pill>" + _e(i["spec"]) + "</span>" if i.get("spec") else ""}'
        f'<div class="muted">{_e(i["title"])}</div></li>' for i in items) + "</ul>"


def _past_rows(rows: list[dict]) -> str:
    out = []
    for r in rows:
        pr = f' · {_url_link(r["pr"], forge_word([r["pr"]]))}' if r.get("pr") else ""
        out.append(f'<li>{_file_link(r["path"], r["cr"] or "CR")} {_e(subject(r["title"]))}'
                   f'<div class="muted">{_e(r["state"] or "-")} · {_e(_money(r["cost_usd"]))}{pr}</div></li>')
    return "<ul>" + "".join(out) + "</ul>"


def render_body(data: dict) -> str:
    parts = []
    batch = data["batch"]
    if batch:
        slots = next((b["slots"] for b in data["batches"] if b["batch"] == batch["batch"]), None)
        parts.append(_batch_section(batch, slots, data["events"]))
    else:
        parts.append('<section><p class="muted">No batch.</p></section>')
    groups: dict[str, list[dict]] = {}
    for item in data["backlog"]:
        groups.setdefault(item["priority"], []).append(item)
    for name in ("3-ready", "inbox"):
        if groups.get(name):
            parts.append(f'<section><h2>{_e(name)} ({len(groups[name])})</h2>{_item_rows(groups[name])}</section>')
    for name in sorted(k for k in groups if k not in ("3-ready", "inbox")):
        parts.append(_details(f"<b>Backlog {_e(name)}</b> ({len(groups[name])})", _item_rows(groups[name])))
    for key, label in (("merged", "Merged"), ("trashed", "Trashed")):
        if data[key]:
            parts.append(_details(f"<b>{label}</b> ({data[key + '_total']})", _past_rows(data[key])))
    return "".join(parts)


def project_name(repo: Repo) -> str:
    return (repo.project_dir or repo.root).name


def page(body: str, name: str, updated: str = "", title: str = "") -> str:
    foot = (f'<p class="muted">Updated {_e(updated)}, refreshes every {REFRESH_S} s · '
            '<a href="/api/status">JSON</a></p>') if updated else '<p class="muted"><a href="/">Board</a></p>'
    refresh = f'<meta http-equiv="refresh" content="{REFRESH_S}">' if updated else ""
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">{refresh}'
            f'<title>{_e(title or name)}</title><style>{STYLE}</style></head><body>'
            f'<h1>{_e(name)}</h1>{body}{foot}</body></html>')


STYLE = """
:root{color-scheme:light dark;--bg:#fafafa;--card:#fff;--fg:#222;--mut:#777;--line:#e4e4e4}
@media (prefers-color-scheme:dark){:root{--bg:#151515;--card:#1f1f1f;--fg:#e8e8e8;--mut:#999;--line:#333}}
body{font:15px/1.4 system-ui,sans-serif;background:var(--bg);color:var(--fg);margin:auto;padding:12px;max-width:760px}
h1{font-size:18px;margin:4px 0 12px}h2{font-size:16px;margin:0 0 8px}
section,.sec{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;margin-bottom:12px}
.pill{font-size:11px;font-weight:normal;border:1px solid var(--line);border-radius:9px;padding:1px 7px;margin-left:6px}
.bar{height:6px;background:var(--line);border-radius:3px;margin:6px 0}.bar div{height:100%;background:#4a7fd4;border-radius:3px}
.cr{display:flex;gap:10px;padding:8px 0;border-top:1px solid var(--line)}.crbody{flex:1;min-width:0}
.dot{width:10px;height:10px;border-radius:50%;margin-top:6px;flex:none;background:#888}
.green{background:#2e9d5b}.yellow{background:#d79b00}.red{background:#d1453b}.grey{background:#888}
.muted{color:var(--mut);font-size:13px}.blk{color:#d1453b;font-size:13px}
a{color:#4a7fd4;text-decoration:none}ul{padding-left:18px;margin:6px 0}li{margin:4px 0}
.ev{list-style:none;padding:0;font-size:13px}summary{cursor:pointer}pre{white-space:pre-wrap;word-wrap:break-word}
"""


# ---- the files ----------------------------------------------------------------------------------

def _inside(root: Path, rel: str) -> Path | None:
    """The path in the planning folder, or None when it leaves it or does not exist."""
    if "\x00" in rel or rel.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", rel) \
            or Path(rel).is_absolute():
        return None
    try:
        target = (root / rel).resolve()
    except (OSError, ValueError):
        return None
    return target if target.is_relative_to(root) and target.exists() else None


def _file_page(root: Path, rel: str, target: Path, name: str) -> str:
    shown = target.relative_to(root).as_posix() if target != root else "."
    if target.is_dir():
        entries = []
        for child in sorted(_retry(lambda: list(target.iterdir()))):
            try:
                if not child.resolve().is_relative_to(root):
                    continue
            except OSError:
                continue
            entries.append(f"<li>{_file_link(child.relative_to(root).as_posix(), child.name + ('/' if child.is_dir() else ''))}</li>")
        body = f"<section><h2>{_e(shown)}</h2><ul>{''.join(entries)}</ul></section>"
    else:
        raw = _retry(target.read_bytes)
        text = raw[:FILE_LIMIT].decode("utf-8", errors="replace")
        note = '<p class="muted">cut at 1 MB</p>' if len(raw) > FILE_LIMIT else ""
        body = f"<section><h2>{_e(shown)}</h2><pre>{_e(text)}</pre>{note}</section>"
    return page(body, name, title=f"{name}: {shown}")


# ---- the server ---------------------------------------------------------------------------------

def _handler(repo: Repo, seat: str | None, stop):
    root = repo.changes.resolve()
    name = project_name(repo)

    class Handler(BaseHTTPRequestHandler):
        server_version = "chantier-board"
        sys_version = ""

        def _send(self, code: int, body: str, ctype: str, head: bool = False, extra=None) -> None:
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
            url = urlparse(self.path)
            try:
                if url.path == "/":
                    data = collect(repo, seat)
                    self._send(200, page(render_body(data), name, data["updated"]), "text/html", head)
                elif url.path == "/api/status":
                    data = collect(repo, seat)
                    self._send(200, json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                               "application/json", head)
                elif url.path == "/file":
                    rel = parse_qs(url.query).get("p", [""])[0]
                    target = _inside(root, rel)
                    if target is None:
                        self._send(404, "not found\n", "text/plain", head)
                    else:
                        self._send(200, _file_page(root, rel, target, name), "text/html", head)
                else:
                    self._send(404, "not found\n", "text/plain", head)
            except (OSError, ValueError, KeyError, ChantierError):
                self._send(500, "the record could not be read just now\n", "text/plain", head)
            if seat and _seat_gone(repo, seat):
                stop()

        def do_GET(self) -> None:  # noqa: N802
            self._serve(False)

        def do_HEAD(self) -> None:  # noqa: N802
            self._serve(True)

        def _refuse(self) -> None:
            self._send(405, "read only: GET and HEAD\n", "text/plain", extra={"Allow": "GET, HEAD"})

        do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _refuse  # noqa: N815

        def log_message(self, *args) -> None:
            pass

    return Handler


def _seat_gone(repo: Repo, seat: str) -> bool:
    """The seat no longer names this session (left, or taken over); an unreadable file is not."""
    try:
        held = _read_seat(repo)
    except (ChantierError, OSError):
        return False
    return not held or held["session"] != seat


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


def _probe(host: str, port: int):
    """None: nothing answers. A dict: a chantier board's status. "other": something else holds it."""
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


def settings(repo: Repo, host: str | None, port: int | None) -> tuple[str, int]:
    """The address: the command's options, else `chantier.yaml`'s `board` key, else the default."""
    found, problems = pb.load_board(repo.root / pb.FILE)
    if problems:
        raise ChantierError(problems[0])
    host = host or found.get("host") or DEFAULT_HOST
    port = port if port is not None else found.get("port", DEFAULT_PORT)
    if not 1 <= port <= 65535:
        raise ChantierError(f"--port {port}: a port is 1 to 65535", 1)
    if re.search(r"\s", host):
        raise ChantierError(f"--host {host!r}: an address holds no whitespace", 1)
    return host, port


def _not_started(reason) -> ChantierError:
    return ChantierError(f"board not started: {' '.join(str(reason).split())}", EXIT_EXTERNAL)


def serve(repo: Repo, host: str, port: int, seat: str | None) -> list[str]:
    if not repo.changes.is_dir():
        raise _not_started(f"no planning folder at {repo.changes}")
    where = f"http://{host}:{port}/"
    found = _probe(host, port)
    if isinstance(found, dict) and found.get("planning_folder") == repo.changes.resolve().as_posix():
        if found.get("seat") == seat:
            return [f"board already running at {where}"]
        for _ in range(SEAT_CHECK_S * 2 * 2):  # at most twice the seat check's period
            time.sleep(0.5)
            if _probe(host, port) is None:
                break
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    try:
        server = type("Server", (_Server,), {"address_family": family})((host, port), _handler(
            repo, seat, lambda: threading.Thread(target=lambda: server.shutdown(), daemon=True).start()))
    except (OSError, OverflowError) as e:
        raise _not_started(e) from e
    print(f"board on {where} over {repo.changes.resolve().as_posix()}", flush=True)
    if not is_loopback(host):
        every = ", on every network of this machine" if host in ("0.0.0.0", "::") else ""
        print(f"board: listens beyond this machine ({host}{every}), no password", flush=True)
    if seat:
        def watch() -> None:
            while not threading.Event().wait(SEAT_CHECK_S):
                if _seat_gone(repo, seat):
                    server.shutdown()
                    return
        threading.Thread(target=watch, daemon=True).start()
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return []


def board(args) -> list[str]:
    repo = Repo.find(readonly=True)
    host, port = settings(repo, args.host, args.port)
    return serve(repo, host, port, args.seat)
