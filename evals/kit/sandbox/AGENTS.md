# AGENTS.md

shelf is a small reading list served on the web, in Python. Run everything with `uv`.

- Run it: `uv run python -m shelf`.
- Fast gate (after each change): `uv run pytest -q -x`.
- Long gate (before a pull request): `uv run --locked pytest -q`.
- Default branch: `main`. Commits follow Conventional Commits (`feat: ...`, `fix: ...`). Pull
  requests merge by rebase (`gh pr merge --rebase`).
- The code lives in `src/shelf/`, with a test for every behavior in `tests/`. The HTML is
  hand-written in `src/shelf/templates/`. No JavaScript framework, no Node, and no new runtime
  dependency.
- Every route and page is in the "Routes" table of `README.md`; a change to a route updates it.

## chantier

- release: RELEASING.md
