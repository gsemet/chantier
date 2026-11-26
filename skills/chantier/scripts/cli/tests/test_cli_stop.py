"""CR-363: a session whose chantier CLI cannot run stops at once; the rule is floor line 4, and
every text that speaks of a missing tool or a failing command points to it."""

import pytest
from conftest import PLUGIN_ROOT

REFS = "skills/chantier/references"


@pytest.mark.parametrize(
    ("path", "needle"),
    [
        (f"{REFS}/floor.md", "4. A CLI that cannot run is a stop."),
        *[
            (
                f"skills/{name}/SKILL.md",
                "Any failure of the sync or of `$CHANTIER`, in either mode, at any call, "
                "is a stop: report its exact error (floor 4)",
            )
            for name in ("chantier", "chief-of-staff", "griller", "status")
        ],
        (f"{REFS}/topics/worker-shell.md", "A `$CHANTIER` that cannot run is a stop (floor 4)"),
        (f"{REFS}/concepts.md", "works without it, never without `$CHANTIER`"),
    ],
)
def test_cli_that_cannot_run_is_a_stop(path: str, needle: str) -> None:
    """A CLI that cannot run stops the session, in every mode and role (CR-363)."""
    text = " ".join((PLUGIN_ROOT / path).read_text(encoding="utf-8").split())
    assert needle in text, f"{path} lacks: {needle}"
