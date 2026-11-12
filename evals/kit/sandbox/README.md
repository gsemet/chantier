# shelf

shelf is a small reading list served on the web. The backend uses the Python standard library
only, and the pages are hand-written HTML. It runs with [uv](https://docs.astral.sh/uv/).

This repository is chantier's eval sandbox: its `main` is reset by chantier's eval kit, so pull
requests and releases here do not last.

## Run

```bash
uv run python -m shelf              # http://127.0.0.1:8000
uv run python -m shelf --host 0.0.0.0 --port 9000
```

## Test

```bash
uv run pytest -q -x                 # fast
uv run --locked pytest -q           # the CI's command
```

## Routes

| Method | Path | Does |
| --- | --- | --- |
| GET | `/` | The list of items (title linked to its page, status, date added) and the add form |
| POST | `/items` | Adds an item from the form (`title`, `url`). On success: 303 to `/`. On invalid input: 400, the list page again with the error message and the values entered |
| GET | `/items/<id>` | The item's page; 404 page if unknown |
| POST | `/items/<id>/status` | Sets `status` from the form. 303 to the item's page; 400 on an unknown status; 404 on an unknown item |
| GET | `/static/style.css` | The stylesheet |
| GET | `/healthz` | `{"status": "ok", "version": "<version>"}` as JSON |

Any other path gets the 404 page. A known path with the wrong method gets 405.

## Data

The items live in a JSON file: the path in the `SHELF_DATA` environment variable, else
`shelf.json` in the current folder. A missing file is an empty shelf.

An item has an `id`, a `title` (1 to 200 characters), an optional `url` (starting with `http://`
or `https://`), a `status` (`to-read`, `reading` or `done`) and the date it was `added`.
