#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""The chantier launcher: it picks the dev or plugin mode and runs the CLI by the one method.

    uv run --script "<this file>" [--project <folder>] <command> ...
    uv run --script "<this file>" --print [--project <folder>]
    uv run --script "<this file>" --sync [--project <folder>]

The logic lives in `chantier.launcher` (standard library only); this file holds none.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent / "cli" / "src"))

from chantier.launcher import main  # noqa: E402

raise SystemExit(main(sys.argv[1:], HERE.parents[3]))
