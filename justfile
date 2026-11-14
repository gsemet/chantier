# chantier: plugin, skill and CLI. Run `just` to list the recipes.

set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

ruff := "ruff@0.17.5"
mypy := "mypy==1.20.0"
run-cli := "uv run --locked python"
node := "nodejs-wheel==24.19.0"
biome := "@biomejs/biome@2.6.7"

# List the recipes
default:
    @just --list

# Print the current version
version-show:
    uv run --script scripts/version.py show

# Set an exact version everywhere (just version 1.2.3)
version new_version:
    uv run --script scripts/version.py set {{new_version}}

# Bump the version everywhere: patch (default), minor or major
bump-version part="patch":
    uv run --script scripts/version.py bump {{part}}

# Structure tests: versions, manifests, agents, references, a smoke run
test *args:
    uv run --locked --group dev pytest -q {{args}}

# Optional: one whole batch, end to end through the real CLI and a fake gh, then glab, no model
scenario:
    {{run-cli}} scenario/run_scenario.py --forge github
    {{run-cli}} scenario/run_scenario.py --forge gitlab

# The eval kit's dry run: reset, setup, a staged run, the audit and the judge, on a local sandbox; no model, no GitHub
eval-dry-run:
    {{run-cli}} evals/kit/dry_run.py

# The mod's checks: `claude plugin validate .` then `claude plugin test .` (not part of check: CI has no claude)
mod:
    uv run --no-project python scripts/mod.py

# The reviewed release notes and thread of the current version (none needed before 0.8.0)
release-notes:
    uv run --script scripts/release_notes.py --check

# The code standards: format, lint, types, the lock and the web frame's Biome (tools pinned above, the types against the locked dependencies)
lint:
    uvx {{ruff}} format --check skills
    uvx {{ruff}} check skills
    uv run --locked --group dev --with {{mypy}} --with types-psutil mypy
    uv lock --check
    uvx --from {{node}} npx --yes {{biome}} check skills/chantier/scripts/cli/src/chantier/board/web

# Everything a change must pass
check: lint test release-notes

# Prepare a release on a new branch: bump, check and commit (pushes nothing)
release part="patch": (bump-version part) check
    git add docs/release-notes
    git commit -am "release: v$(uv run --script scripts/version.py show)"

# After the release PR is merged: tag the version on origin/main and push the tag
tag:
    git fetch origin main
    uv run --script scripts/version.py check-tag
    git tag "v$(uv run --script scripts/version.py show)" origin/main
    git push origin "v$(uv run --script scripts/version.py show)"
