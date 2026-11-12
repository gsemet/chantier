# Refuse a duplicate URL

## Change

- Adding an item (`POST /items`) whose URL is already another item's: 400, the list page with the values entered and the message `Already on the shelf:` followed by a link to the existing item (`href="/items/<id>"`, its title as the link's text); nothing added. Two URLs are the same when they are equal after trimming, ignoring the case of the scheme and the host and one trailing `/`. An item with no URL never clashes.
- The same check on the edit form (`POST /items/<id>/edit`, released in 0.2.0), where an item's own URL is not a clash.

## Files

The expected footprint; a Coder may add a helper module, never a dependency.

- `src/shelf/models.py`
- `src/shelf/app.py`
- `src/shelf/templates/index.html`
- `src/shelf/templates/edit.html`
- `README.md`
- `tests/test_items.py`

## Done when

- each behaviour of "Change" has a test, in `tests/test_items.py`, using the `client` fixture;
- the README's "Routes" table lists every new route and every new query parameter of `/`;
- all user text is HTML-escaped; no JavaScript; no new runtime dependency; a known path with the wrong method gets 405, like the base routes;
- the fast gate (`uv run pytest -q -x`) and the long gate (`uv run --locked pytest -q`) pass.
