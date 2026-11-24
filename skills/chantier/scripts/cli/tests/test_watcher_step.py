"""The Chief of Staff's cards carry the step that starts the watcher where it reads it."""

from pathlib import Path

import pytest
from conftest import PLUGIN_ROOT, SKILL
from test_startup_manifest import _lf_bytes, _section_span

SKILL_MD = PLUGIN_ROOT / "skills" / "chief-of-staff" / "SKILL.md"
CARD = SKILL / "references" / "chief-of-staff.md"
START = SKILL / "references" / "chief-of-staff-batch-start.md"
SENTENCE = "run the printed command as is: no flag added"

# (file, heading, the texts that section must hold)
CARRIES = [
    (SKILL_MD, "## Startup core", ["`watch: not running`", SENTENCE]),
    (SKILL_MD, "# chantier: Chief of Staff", ["but its Startup core"]),
    (START, "## Starting a batch", ["5. **Start the watcher.**", SENTENCE]),
    (CARD, "## Entry points", ["\n| a `watch: not running` line", SENTENCE]),
    (CARD, "## Entry points", ["still running: …"]),
]


@pytest.mark.parametrize(("path", "heading", "texts"), CARRIES)
def test_the_chief_of_staff_cards_carry_the_watcher_step(
    path: Path, heading: str, texts: list[str]
) -> None:
    start, end = _section_span(path, heading)
    body = _lf_bytes(path)[start:end].decode("utf-8")
    for text in texts:
        assert text in body, f"{path.name} {heading}: missing {text!r}"
