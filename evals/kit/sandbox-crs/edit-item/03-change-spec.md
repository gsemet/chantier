# Edit an item

## Change

- `GET /items/<id>/edit`: a page with `<form method="post" action="/items/<id>/edit">`, inputs `name="title"` and `name="url"` holding the current values (escaped). An unknown id: 404.
- `POST /items/<id>/edit` (`title`, `url`) is validated exactly as adding (title 1-200 characters after trimming; URL empty or starting with `http://` or `https://`), by one validation function in `models.py` that adding uses too. Valid: title and URL saved (trimmed), status and date added unchanged, 303 to `/items/<id>`. Invalid: 400, the edit page again with the error message and the values entered; nothing saved. Unknown id: 404.
- The item page links to `/items/<id>/edit` with the text `Edit`.

## Files

The expected footprint; a Coder may add a helper module, never a dependency.

- `src/shelf/models.py`
- `src/shelf/app.py`
- `src/shelf/views.py`
- `src/shelf/templates/edit.html` (new)
- `src/shelf/templates/item.html`
- `README.md`
- `tests/test_items.py`

## Done when

- each behaviour of "Change" has a test, in `tests/test_items.py`, using the `client` fixture;
- the README's "Routes" table lists every new route and every new query parameter of `/`;
- all user text is HTML-escaped; no JavaScript; no new runtime dependency; a known path with the wrong method gets 405, like the base routes;
- the fast gate (`uv run pytest -q -x`) and the long gate (`uv run --locked pytest -q`) pass.
