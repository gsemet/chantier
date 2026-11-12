# Releasing shelf

Run these steps in order, from a branch on a fresh `main`. If anything in the code changes, start
again from step 1.

1. **Heavy check:** `uv run python scripts/release_check.py` must end with `release check passed`.
2. **Notes:** write one bullet per user-visible change since the previous version's entry in
   `CHANGELOG.md`. A maintainer approves them before they go anywhere.
3. **Release commit:** set the version in `pyproject.toml` and in `src/shelf/__init__.py`, add the
   approved notes at the top of `CHANGELOG.md` under `## <version>`, run step 1 again, and commit
   `release: v<version>`. Open a pull request.
4. **CI** is green on that pull request.
5. **Merge** it by rebase.
6. **Tag** the merged commit: `git fetch origin main`, then `git tag v<version> origin/main`, then
   `git push origin v<version>`.
7. **GitHub release:** `gh release create v<version> --title "v<version>" --notes-file <file>`,
   where the file holds that version's `CHANGELOG.md` section.
8. **Check:** `git ls-remote --tags origin` lists the tag, and `gh release view v<version>` shows
   the notes.

Steps 5 to 7 cannot be undone.
