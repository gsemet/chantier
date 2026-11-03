# Releasing tasks-cli

Run these steps in order, from a branch on a fresh `main`. If you change anything in the code,
start again from step 1.

1. **Heavy check:** `uv run python scripts/release_check.py` must end with `release check passed`.
2. **Notes:** write the release notes, one bullet per user-visible change since the last release.
   A maintainer reviews and edits them before they go anywhere.
3. **Release commit:** set the version in `pyproject.toml`, add the reviewed notes at the top of
   `CHANGELOG.md` under `## <version>`, and commit `release: v<version>`. Open a pull request.
4. **CI** must be green on that pull request.
5. **Merge** the pull request by rebase.
6. **Tag** the merged commit on `main`: `git tag v<version> origin/main`, then
   `git push origin v<version>`.
7. **Check:** `git ls-remote --tags origin` lists the tag.

Steps 5 and 6 cannot be taken back.
