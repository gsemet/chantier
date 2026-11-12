# Export the shelf as CSV

## Change

- `GET /export.csv`: 200, `Content-Type: text/csv; charset=utf-8`, `Content-Disposition: attachment; filename="shelf.csv"`. The body is written with Python's `csv` module, default dialect (comma, minimal quoting, `\r\n` line ends): the header `id,title,url,status,added`, then one row per item in id order; `url` empty when the item has none. Exactly these five columns.
- The list page links to `/export.csv` with the text `Export CSV`. `POST /export.csv`: 405.

## Files

The expected footprint; a Coder may add a helper module, never a dependency.

- `src/shelf/app.py`
- `src/shelf/export.py` (new)
- `src/shelf/templates/index.html`
- `README.md`
- `tests/test_export.py` (new)

## Done when

- each behaviour of "Change" has a test, in `tests/test_export.py`, using the `client` fixture;
- the README's "Routes" table lists every new route and every new query parameter of `/`;
- all user text is HTML-escaped; no JavaScript; no new runtime dependency; a known path with the wrong method gets 405, like the base routes;
- the fast gate (`uv run pytest -q -x`) and the long gate (`uv run --locked pytest -q`) pass.
