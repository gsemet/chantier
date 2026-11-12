# Rate an item

## Change

- Each item has an optional `rating`, a whole number from 1 to 5, none by default; an item stored before this change has none.
- The item page shows `Rating: <n>/5`, or `Rating: none`, and has `<form method="post" action="/items/<id>/rating">` with `<select name="rating">` whose options are `""` (text `No rating`), then `1` to `5`; the current one is `selected`.
- The list page shows `<n>/5` in the row of each rated item.
- `POST /items/<id>/rating` (`rating`): `""` clears it, `1` to `5` sets it, 303 to `/items/<id>`. Any other value: 400, the item page with `Rating must be a whole number from 1 to 5.`, nothing saved. Unknown id: 404.

## Files

The expected footprint; a Coder may add a helper module, never a dependency.

- `src/shelf/models.py`
- `src/shelf/store.py`
- `src/shelf/app.py`
- `src/shelf/templates/item.html`
- `src/shelf/templates/index.html`
- `README.md`
- `tests/test_items.py`

## Done when

- each behaviour of "Change" has a test, in `tests/test_items.py`, using the `client` fixture;
- the README's "Routes" table lists every new route and every new query parameter of `/`;
- all user text is HTML-escaped; no JavaScript; no new runtime dependency; a known path with the wrong method gets 405, like the base routes;
- the fast gate (`uv run pytest -q -x`) and the long gate (`uv run --locked pytest -q`) pass.
