# Filter the list by status

## Change

- `GET /?status=<s>`, `<s>` one of `to-read`, `reading`, `done`: only the items with that status. `status` absent or empty: all items. Any other value: 400, with the message `Unknown status: <value>` (the value escaped).
- Above the list, `<nav class="filters">` with four links in this order: `All` (`/`), `To read` (`/?status=to-read`), `Reading` (`/?status=reading`), `Done` (`/?status=done`). The link of the current filter (`All` with no filter) has `aria-current="page"`; no other link of that nav has it.
- A filter that matches nothing shows `No items with this status.`.

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
