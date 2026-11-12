import json
import threading
import urllib.request
from wsgiref.simple_server import make_server

from shelf import __version__
from shelf.__main__ import QuietHandler
from shelf.app import app


def test_a_real_server_answers_healthz():
    with make_server("127.0.0.1", 0, app, handler_class=QuietHandler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/healthz"
            with urllib.request.urlopen(url, timeout=10) as response:
                assert json.load(response) == {"status": "ok", "version": __version__}
        finally:
            server.shutdown()
            thread.join(timeout=10)
