# Sort the list

## Change

- `GET /?sort=<order>`: `oldest` (id ascending; also when `sort` is absent or empty), `newest` (id descending), `title` (title A to Z ignoring case, ties by id). Any other value: 400, with `Unknown sort: <value>` (escaped).
- The list page has `<nav class="sort">` with three links: `Oldest` (`/?sort=oldest`), `Newest` (`/?sort=newest`), `Title` (`/?sort=title`); the current one (`Oldest` when absent) has `aria-current="page"`, no other link of that nav has it.
- The sort combines with the list page's other query parameters, when the page has some (in 0.2.0, the status filter and the search): its links keep them, and their links keep the sort.

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
