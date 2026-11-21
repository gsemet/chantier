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
    uv run --locked --group dev pytest -q -n auto --dist worksteal {{args}}

# The scripted scenario, no model: independent units in parallel (4 at a time), GitHub and the GitLab unit
scenario *args:
    {{run-cli}} scenario/run_scenario.py {{args}}

# The eval kit's dry run: reset, setup, a staged run, the audit and the judge, on a local sandbox; no model, no GitHub
eval-dry-run:
    {{run-cli}} evals/kit/dry_run.py

# Refresh the Copilot model catalog from GitHub's tables (network; by hand, not in check)
copilot-models *args:
    {{run-cli}} scripts/copilot_models.py {{args}}

# Add the journal's missing published types to hub/schemas.json (by hand, not in check)
journal-schemas:
    {{run-cli}} scripts/journal_schemas.py

# Write board/api/protocol.json from the protocol's models (by hand, not in check)
protocol-schema:
    {{run-cli}} scripts/protocol_schema.py

# The mod's checks: `claude plugin validate .` then `claude plugin test .` (not part of check: CI has no claude)
mod:
    uv run --no-project python scripts/mod.py

# Retake the web board's screenshots in docs/ from docs/demo/ (by hand: when the UI changes, before a release; not in check)
docs-screenshots:
    uv run --script scripts/docs_screenshots.py

# The reviewed release notes and thread of the current version (none needed before 0.8.0)
release-notes:
    uv run --script scripts/release_notes.py --check

# The code standards: format, lint, types, the lock and the web frame's Biome (tools pinned above, the types against the locked dependencies)
lint:
    uvx {{ruff}} format --check skills scripts
    uvx {{ruff}} check skills scripts
    uv run --locked --group dev --with {{mypy}} --with types-psutil mypy
    uv lock --check
    uvx --from {{node}} npx --yes {{biome}} check skills/chantier/scripts/cli/src/chantier/clients/web

# Fetch the pinned check tools into the caches, running nothing (CI runs it before `check`, retried once)
tools:
    uv sync --locked --group dev
    uv run --locked --group dev --with {{mypy}} --with types-psutil mypy --version
    uvx {{ruff}} --version
    uvx --from {{node}} npx --yes {{biome}} --version

# Everything a change must pass
check: lint test release-notes

# Prepare a release on a new branch: bump, check and commit (pushes nothing)
release part="patch": (bump-version part) check
    git add docs/release-notes
    git commit -am "release: v$(uv run --script scripts/version.py show)"

# After the release PR is merged, from the main checkout: fast-forward main, tag the version on origin/main and push the tag
tag:
    uv run --script scripts/version.py ff-main
    uv run --script scripts/version.py check-tag
    git tag "v$(uv run --script scripts/version.py show)" origin/main
    git push origin "v$(uv run --script scripts/version.py show)"
