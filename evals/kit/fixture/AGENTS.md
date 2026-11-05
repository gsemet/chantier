# AGENTS.md

tasks-cli is a small Python to-do list. Run everything with `uv`.

- Fast gate (after each change): `uv run pytest -q -x`.
- Long gate (before a pull request): `uv run pytest -q`.
- Default branch: `main`. Commits follow Conventional Commits (`feat: …`, `fix: …`). Pull
  requests merge by rebase (`gh pr merge --rebase`).
- Every command and option of the CLI is documented in `README.md`; a change to the CLI updates it.
- Keep the code in `src/tasks_cli/` and a test for every behavior in `tests/`.

## chantier

- docs-review: `chantier-eval-docs-reviewer`, after the Inspector: every new or changed CLI
  command or option is documented in README.md, with an example
- style-review: `chantier-eval-strict-reviewer`, after the Inspector: the house style of the
  command line
- release: RELEASING.md
