"""`python -m shelf [--host H] [--port P]`: serve the reading list."""
from __future__ import annotations

import argparse
from wsgiref.simple_server import WSGIRequestHandler, make_server

from shelf.app import app


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 - the base class's name
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="shelf", description="Serve the reading list.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    with make_server(args.host, args.port, app, handler_class=QuietHandler) as server:
        print(f"shelf serving on http://{args.host}:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("shelf stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
