"""Fixtures: an empty shelf per test, and a client that calls the WSGI app with no socket."""
from __future__ import annotations

import io
from dataclasses import dataclass
from urllib.parse import urlencode

import pytest

from shelf.app import app


@pytest.fixture(autouse=True)
def shelf_data(tmp_path, monkeypatch):
    path = tmp_path / "shelf.json"
    monkeypatch.setenv("SHELF_DATA", str(path))
    return path


@dataclass
class Response:
    status: int
    headers: dict
    text: str


class Client:
    def _call(self, method: str, path: str, body: bytes = b"") -> Response:
        path, _, query = path.partition("?")
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "QUERY_STRING": query,
            "CONTENT_TYPE": "application/x-www-form-urlencoded" if body else "",
            "CONTENT_LENGTH": str(len(body)),
            "wsgi.input": io.BytesIO(body),
        }
        seen = {}

        def start_response(status, headers):
            seen["status"] = int(status.split()[0])
            seen["headers"] = {k.lower(): v for k, v in headers}

        text = b"".join(app(environ, start_response)).decode("utf-8")
        return Response(seen["status"], seen["headers"], text)

    def get(self, path: str) -> Response:
        return self._call("GET", path)

    def post(self, path: str, data: dict) -> Response:
        return self._call("POST", path, urlencode(data).encode("utf-8"))


@pytest.fixture
def client() -> Client:
    return Client()
