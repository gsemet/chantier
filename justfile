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

# Regenerate the plugin's agent files from the skill's templates
agents:
    uv run --script scripts/plugin_agents.py

# Fail if the plugin's agent files are out of date
check-agents:
    uv run --script scripts/plugin_agents.py --check

# Structure tests: versions, manifests, agents, model lists, roles, links, a smoke run
test *args:
    cd {{cli}}; uv run --group dev pytest -q {{args}}

# Optional: one whole batch, end to end through the real CLI and a fake gh, no model
scenario:
    uv run --no-project python skills/chantier/evals/scenario/run_scenario.py

# Everything a change must pass
check: check-agents test

# Prepare a release on a clean main: bump, check, commit and tag (pushes nothing)
release part="patch": (bump-version part) check
    git commit -am "release: v$(uv run --script scripts/version.py show)"
    git tag "v$(uv run --script scripts/version.py show)"
