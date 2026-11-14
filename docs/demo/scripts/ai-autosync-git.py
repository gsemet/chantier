# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""A stub of the surface's autosync tool, for the demo: it does nothing and ends at once. The
board runs it for `join`, `start`, `stop` and `approve`; the demo's state is written by the
capture script, and nothing here touches a git remote."""

import sys

print("demo autosync stub:", " ".join(sys.argv[1:]))
