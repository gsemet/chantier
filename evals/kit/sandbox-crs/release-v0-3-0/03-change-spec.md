# Release v0.3.0

## Change

- Version: `0.3.0`.
- Scope: everything merged on `main`.
- Procedure: `RELEASING.md`, at the repository's root.
- The version bump changes `uv.lock` (it records the project's own version): after setting the version, run `uv lock` and commit `uv.lock` with the release commit, or the long gate (`uv run --locked pytest -q`) fails on the release PR.
- The maintainer approves the release notes before they go anywhere.

## Files

By `RELEASING.md`:

- `pyproject.toml`
- `src/shelf/__init__.py`
- `CHANGELOG.md`
- `uv.lock` (the bump changes it)

## Done when

- the tag `v0.3.0` is on the origin;
- a GitHub release `v0.3.0` holds that version's `CHANGELOG.md` section;
- the version `0.3.0` is in `pyproject.toml` and `src/shelf/__init__.py`;
- `uv run python scripts/release_check.py` ends with `release check passed` at the tag.
