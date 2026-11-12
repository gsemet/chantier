# Read the items as JSON

## Change

- `GET /api/items`: 200, `Content-Type: application/json; charset=utf-8`, a JSON array of all items in id order. Each item is an object with at least `id` (integer), `title` (string), `url` (string, or `null` when the item has none), `status` (string) and `added` (`YYYY-MM-DD`).
- `GET /api/items/<id>`: that object. Unknown id: 404, body `{"error": "not found"}`, same content type.
- Any other method on these paths: 405. Titles are given as entered, not HTML-escaped.
- The list page links to `/api/items` with the text `JSON`.

## Files

The expected footprint; a Coder may add a helper module, never a dependency.

- `src/shelf/app.py`
- `src/shelf/api.py` (new)
- `src/shelf/templates/index.html`
- `README.md`
- `tests/test_api.py` (new)

## Done when

- each behaviour of "Change" has a test, in `tests/test_api.py`, using the `client` fixture;
- the README's "Routes" table lists every new route and every new query parameter of `/`;
- all user text is HTML-escaped; no JavaScript; no new runtime dependency; a known path with the wrong method gets 405, like the base routes;
- the fast gate (`uv run pytest -q -x`) and the long gate (`uv run --locked pytest -q`) pass.
