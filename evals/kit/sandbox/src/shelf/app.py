"""The WSGI application and its routes."""
from __future__ import annotations

import json
import re
from http import HTTPStatus
from pathlib import Path
from urllib.parse import parse_qs

from shelf import __version__, store, views
from shelf.models import STATUSES, validate_new

STATIC = Path(__file__).parent / "static"
ITEM = re.compile(r"^/items/(\d+)$")
ITEM_STATUS = re.compile(r"^/items/(\d+)/status$")
HTML = "text/html; charset=utf-8"


def _phrase(code: int) -> str:
    return f"{code} {HTTPStatus(code).phrase}"


def _form(environ) -> dict:
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        length = 0
    raw = environ["wsgi.input"].read(length).decode("utf-8") if length else ""
    return {k: v[0] for k, v in parse_qs(raw, keep_blank_values=True).items()}


def _respond(start_response, code: int, body: str | bytes, content_type: str = HTML, headers=()):
    data = body.encode("utf-8") if isinstance(body, str) else body
    start_response(_phrase(code), [("Content-Type", content_type), ("Content-Length", str(len(data))), *headers])
    return [data]


def _redirect(start_response, location: str):
    return _respond(start_response, 303, "", headers=[("Location", location)])


def _error(start_response, code: int, headers=()):
    return _respond(start_response, code, views.error(code, HTTPStatus(code).phrase), headers=headers)


def app(environ, start_response):
    method = environ["REQUEST_METHOD"]
    path = environ.get("PATH_INFO") or "/"

    if path == "/":
        if method != "GET":
            return _error(start_response, 405, [("Allow", "GET")])
        return _respond(start_response, 200, views.index(store.load()))

    if path == "/items":
        if method != "POST":
            return _error(start_response, 405, [("Allow", "POST")])
        form = _form(environ)
        values, problem = validate_new(form.get("title", ""), form.get("url", ""))
        if problem:
            return _respond(start_response, 400, views.index(store.load(), problem, values))
        store.add(values["title"], values["url"])
        return _redirect(start_response, "/")

    match = ITEM.match(path)
    if match:
        if method != "GET":
            return _error(start_response, 405, [("Allow", "GET")])
        entry = store.get(int(match.group(1)))
        if entry is None:
            return _error(start_response, 404)
        return _respond(start_response, 200, views.item(entry))

    match = ITEM_STATUS.match(path)
    if match:
        if method != "POST":
            return _error(start_response, 405, [("Allow", "POST")])
        item_id = int(match.group(1))
        if store.get(item_id) is None:
            return _error(start_response, 404)
        status = _form(environ).get("status", "")
        if status not in STATUSES:
            return _error(start_response, 400)
        store.set_status(item_id, status)
        return _redirect(start_response, f"/items/{item_id}")

    if path == "/static/style.css":
        if method != "GET":
            return _error(start_response, 405, [("Allow", "GET")])
        return _respond(start_response, 200, (STATIC / "style.css").read_bytes(), "text/css; charset=utf-8")

    if path == "/healthz":
        if method != "GET":
            return _error(start_response, 405, [("Allow", "GET")])
        body = json.dumps({"status": "ok", "version": __version__})
        return _respond(start_response, 200, body, "application/json")

    return _error(start_response, 404)
