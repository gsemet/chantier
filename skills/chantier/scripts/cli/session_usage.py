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
"""`copilot-session-usage` resolved by uv at run time, always from pypi.org (whatever the user's uv index): `uv run --script session_usage.py …`.

`chantier cost` runs this on Copilot only; the rest of the CLI has no dependency.
"""
from copilot_session_usage.cli import cli

cli()
