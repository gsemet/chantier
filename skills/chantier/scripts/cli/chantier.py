#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pydantic>=2.11",
#     "ruamel.yaml>=0.18",
#     "psutil>=7",
# ]
#
# [tool.uv]
# no-build = true
# ///
"""`chantier` with no virtual environment or build: `uv run --script <skill>/.../chantier.py`."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from chantier.cli import main  # the path above must be set before this import

sys.exit(main())
