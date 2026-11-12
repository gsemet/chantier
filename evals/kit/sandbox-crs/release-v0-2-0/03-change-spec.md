# Release v0.2.0

## Change

- Version: `0.2.0`.
- Scope: everything merged on `main`.
- Procedure: `RELEASING.md`, at the repository's root.
- The maintainer approves the release notes before they go anywhere.

## Files

By `RELEASING.md`:

- `pyproject.toml`
- `src/shelf/__init__.py`
- `CHANGELOG.md`

## Done when

- the tag `v0.2.0` is on the origin;
- a GitHub release `v0.2.0` holds that version's `CHANGELOG.md` section;
- the version `0.2.0` is in `pyproject.toml` and `src/shelf/__init__.py`;
- `uv run python scripts/release_check.py` ends with `release check passed` at the tag.
