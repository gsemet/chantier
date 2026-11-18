"""`summary lint`'s hint: the path it prints is the one `summary set` reads."""

from pathlib import Path

import pytest
from conftest import Chantier

from chantier.core.errors import EXIT_PRECONDITION


@pytest.mark.parametrize("cell", ["repo", "surface"])
def test_the_summary_lint_hint_is_a_path_summary_set_reads(
    cell: str, chantier: Chantier, request: pytest.FixtureRequest
) -> None:
    place = request.getfixturevalue(cell)
    root = place if isinstance(place, Path) else place.root
    _, out, _ = chantier("file", "Fix login")
    folder = root / out[0].removeprefix("filed ").split(";")[0]
    (folder / "03-change-spec.md").write_text("# Fix login\n\nDo it.\n")
    code, lines, _ = chantier("summary", "lint")
    assert code == EXIT_PRECONDITION, lines
    command = lines[1].split("summary set ", 1)[1].split(" ")[0]
    assert not command.startswith((".agents/", "projects/")), command
    code, _, err = chantier("summary", "set", command, "--title", "T", "--summary", "S")
    assert code == 0, err
    assert chantier("summary", "lint") == (0, ["no gap (1 CRs)"], "")
