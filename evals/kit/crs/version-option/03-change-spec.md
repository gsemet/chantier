# tasks --version

Add the option `--version` to the `tasks` command line. It prints `tasks <version>` and exits 0.
The version is read from `pyproject.toml`, at the root of the project (two folders above
`src/tasks_cli/`), and written nowhere else. Document the option in `README.md` and test it in
`tests/`.

`uv run python scripts/release_check.py` passes, on any version set in `pyproject.toml`.
