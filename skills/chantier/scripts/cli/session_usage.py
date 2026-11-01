#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["copilot-session-usage>=1"]
# ///
"""`copilot-session-usage` resolved by uv at run time: `uv run --script session_usage.py …`.

`chantier cost` runs this on Copilot only; the rest of the CLI has no dependency.
"""
from copilot_session_usage.cli import cli

cli()
