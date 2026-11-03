#!/bin/sh
# Stage the workspace (cwd): git repo and the user's own agents.
set -e
exec uv run --no-project python "$(cd "$(dirname "$0")" && pwd)/../lib/seed.py" agents
