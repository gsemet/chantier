# Search the titles

## Change

- `GET /?q=<text>`: the items whose title contains the text, trimmed, ignoring case. `q` absent or blank: all items.
- The list page has `<form method="get" action="/">` with `<input name="q">`, whose `value` is the current query (escaped), and a button `Search`.
- A query that matches nothing shows `No items match "<query>".` (the query escaped).

## Files

The expected footprint; a Coder may add a helper module, never a dependency.

- `src/shelf/app.py`
- `src/shelf/views.py`
- `src/shelf/templates/index.html`
- `README.md`
- `tests/test_pages.py`

## Done when

- each behaviour of "Change" has a test, in `tests/test_pages.py`, using the `client` fixture;
- the README's "Routes" table lists every new route and every new query parameter of `/`;
- all user text is HTML-escaped; no JavaScript; no new runtime dependency; a known path with the wrong method gets 405, like the base routes;
- the fast gate (`uv run pytest -q -x`) and the long gate (`uv run --locked pytest -q`) pass.
