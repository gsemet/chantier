# chantier: plugin, skill and CLI. Run `just` to list the recipes.

set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

cli := "skills/chantier/scripts/cli"

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
    cd {{cli}}; uv run --group dev pytest -q {{args}}

# Optional: one whole batch, end to end through the real CLI and a fake gh, then glab, no model
scenario:
    uv run --no-project python scenario/run_scenario.py --forge github
    uv run --no-project python scenario/run_scenario.py --forge gitlab

# The reviewed release notes and thread of the current version (none needed before 0.8.0)
release-notes:
    uv run --script scripts/release_notes.py --check

# Everything a change must pass
check: test release-notes

# Prepare a release on a new branch: bump, check and commit (pushes nothing)
release part="patch": (bump-version part) check
    git add docs/release-notes
    git commit -am "release: v$(uv run --script scripts/version.py show)"

# After the release PR is merged: tag the version on origin/main and push the tag
tag:
    git fetch origin main
    git tag "v$(uv run --script scripts/version.py show)" origin/main
    git push origin "v$(uv run --script scripts/version.py show)"
