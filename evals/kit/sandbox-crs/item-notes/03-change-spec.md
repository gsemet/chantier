# Notes on an item

## Change

- Each item has `notes`, a text, empty by default; an item stored before this change reads as empty notes. At most 2000 characters, counted after removing leading and trailing whitespace.
- The item page shows the notes in an element with class `notes`, escaped, with their line breaks kept (`.notes { white-space: pre-wrap; }` in `style.css`), and has `<form method="post" action="/items/<id>/notes">` with `<textarea name="notes">` holding the current notes (escaped) and a button `Save notes`.
- `POST /items/<id>/notes` (`notes`): saves them trimmed, 303 to `/items/<id>`. Over 2000 characters: 400, the item page with `Notes are limited to 2000 characters.`, nothing saved. Unknown id: 404. `GET` on that path: 405.

## Files

The expected footprint; a Coder may add a helper module, never a dependency.

- `src/shelf/models.py`
- `src/shelf/store.py`
- `src/shelf/app.py`
- `src/shelf/templates/item.html`
- `src/shelf/static/style.css`
- `README.md`
- `tests/test_items.py`

## Done when

- each behaviour of "Change" has a test, in `tests/test_items.py`, using the `client` fixture;
- the README's "Routes" table lists every new route and every new query parameter of `/`;
- all user text is HTML-escaped; no JavaScript; no new runtime dependency; a known path with the wrong method gets 405, like the base routes;
- the fast gate (`uv run pytest -q -x`) and the long gate (`uv run --locked pytest -q`) pass.
