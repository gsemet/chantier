"""A fake `copilot-session-usage` driven by the scenario's JSONL records."""
import os
import re
import sys
from pathlib import Path

expected = ["--agent", "cli", "--session-root",
            str(Path(os.environ["COPILOT_HOME"]) / "session-state"),
            "calls", "--name", f"^{re.escape(os.environ['FAKE_USAGE_SESSION'])}$"]
if sys.argv[1:] != expected or os.environ.get("UV_INDEX") != os.environ["FAKE_EXPECT_UV_INDEX"]:
    print("fake session usage: unexpected arguments or environment", file=sys.stderr)
    sys.exit(2)

sys.stdout.write(Path(os.environ["FAKE_USAGE_RECORDS"]).read_text(encoding="utf-8"))
sys.stderr.write(os.environ["FAKE_USAGE_ERROR"])
sys.exit(int(os.environ["FAKE_USAGE_EXIT"]))
