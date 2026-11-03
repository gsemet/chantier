#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["copilot-session-usage>=1"]
#
# [[tool.uv.index]]
# name = "pypi-org"
# url = "https://pypi.org/simple"
# default = true
# ///
"""`copilot-session-usage` is resolved by uv from this script's inline metadata.

`chantier cost` runs this on Copilot with uv configuration files and index variables ignored;
the rest of the CLI has no dependency.
"""
from copilot_session_usage.cli import cli

cli()
