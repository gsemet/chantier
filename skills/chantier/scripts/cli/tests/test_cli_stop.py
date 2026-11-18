"""CR-363: a session whose chantier CLI cannot run stops at once; the rule is in the cards."""

import pytest
from conftest import PLUGIN_ROOT

CLI_STOP_CLAUSE = "(never `$CHANTIER`: a CLI that cannot run is a stop, `startup-core.md`)"
CLI_STOP_CARDS = (
    "concepts",
    "chief-of-staff",
    "driver",
    "coder",
    "conflict-resolver",
    "debugger",
    "demo-explorer",
    "inspector",
    "investigator",
    "review-step",
    "verifier",
)


@pytest.mark.parametrize(
    "path, needles",
    [
        (
            "skills/chantier/references/startup-core.md",
            (
                "in either mode, at any call",
                "report the exact error and stop",
                "no seat",
                "nothing written in the planning folder",
                "retry once only on a transient network error",
                "the launch fails",
                "keep their handling",
                "The CLI is never a tool a role works without",
            ),
        ),
        *[
            (
                f"skills/{name}/SKILL.md",
                (
                    "Any failure of the sync or of `$CHANTIER`, in either mode, "
                    "at any call, follows `startup-core.md`",
                ),
            )
            for name in ("chantier", "chief-of-staff", "griller", "status")
        ],
        *[(f"skills/chantier/references/{card}.md", (CLI_STOP_CLAUSE,)) for card in CLI_STOP_CARDS],
    ],
)
def test_cli_that_cannot_run_is_a_stop(path: str, needles: tuple[str, ...]) -> None:
    """A CLI that cannot run stops the session, in every mode and role (CR-363): the rule is
    written once in the startup core, every `$CHANTIER` failure points to it, and each
    "work without it" line excludes the CLI."""
    text = " ".join((PLUGIN_ROOT / path).read_text(encoding="utf-8").split())
    for needle in needles:
        assert needle in text, f"{path} lacks: {needle}"
