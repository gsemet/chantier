#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""`chantier` without a virtual environment or a build: `uv run --script <skill>/scripts/cli/chantier.py …`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from chantier.cli import main  # noqa: E402

sys.exit(main())
