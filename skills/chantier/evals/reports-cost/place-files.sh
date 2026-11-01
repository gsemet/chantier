#!/bin/sh
# Stage the workspace (cwd): git repo, chantier set up, seed "cost".
set -e
exec python3 "$(cd "$(dirname "$0")" && pwd)/../lib/seed.py" cost
