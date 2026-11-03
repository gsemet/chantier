#!/bin/sh
# Stage the workspace (cwd): git repo and seed "running".
set -e
exec uv run --no-project python "$(cd "$(dirname "$0")" && pwd)/../lib/seed.py" running
