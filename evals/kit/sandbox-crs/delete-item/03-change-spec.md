# Delete an item

## Change

- The item page has `<form method="post" action="/items/<id>/delete">` with a button `Delete`.
- `POST /items/<id>/delete` removes the item and answers 303 to `/`. An unknown id: the 404 page. `GET` on that path: 405.
- After a delete, the item is gone from `/` and `/items/<id>` is 404; the other items stay.
- An id is never given twice: an item added after a delete gets an id higher than any id the shelf ever gave, the deleted one included (the store keeps the next id).

## Files

The expected footprint; a Coder may add a helper module, never a dependency.

- `src/shelf/store.py`
- `src/shelf/app.py`
- `src/shelf/templates/item.html`
- `README.md`
- `tests/test_items.py`

## Done when

- each behaviour of "Change" has a test, in `tests/test_items.py`, using the `client` fixture;
- the README's "Routes" table lists every new route and every new query parameter of `/`;
- all user text is HTML-escaped; no JavaScript; no new runtime dependency; a known path with the wrong method gets 405, like the base routes;
- the fast gate (`uv run pytest -q -x`) and the long gate (`uv run --locked pytest -q`) pass.
