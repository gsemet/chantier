"""`chantier live`'s terminal client: a read-only client of the surface server's published API
(`docs/server-api.md`), the second one after the web board. Three parts, each tested alone:
`link.py` (the transport: the WebSocket, else the HTTP long-poll), `model.py` (the screen's data,
fed with each event; no Rich, no network) and `screen.py` (the drawing, with Rich).

It imports nothing of chantier but itself, `chantier.__version__` and `chantier.core.errors`:
everything it shows comes through the API, so it is also the example of a client in Python."""
