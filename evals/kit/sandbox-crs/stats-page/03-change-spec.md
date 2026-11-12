# A statistics page

## Change

- `GET /stats`: a page whose `<h1>` is `Statistics`, with `<table class="stats">` of four rows in this order: `To read`, `Reading`, `Done`, `Total`; each row a `<th>` holding the label and a `<td>` holding the count. An empty shelf shows four zeros.
- The navigation in `base.html`, on every page, links to `/stats` with the text `Statistics`.
- `POST /stats`: 405. The page shows the version in its footer, like every page.

## Files

The expected footprint; a Coder may add a helper module, never a dependency.

- `src/shelf/app.py`
- `src/shelf/views.py`
- `src/shelf/templates/stats.html` (new)
- `src/shelf/templates/base.html`
- `README.md`
- `tests/test_pages.py`

## Done when

- each behaviour of "Change" has a test, in `tests/test_pages.py`, using the `client` fixture;
- the README's "Routes" table lists every new route and every new query parameter of `/`;
- all user text is HTML-escaped; no JavaScript; no new runtime dependency; a known path with the wrong method gets 405, like the base routes;
- the fast gate (`uv run pytest -q -x`) and the long gate (`uv run --locked pytest -q`) pass.
