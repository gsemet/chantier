"""Which forge a project uses, for the board's "PR" or "MR" words: told from its PR links, else
from its `origin` host."""

from __future__ import annotations

from typing import Any

import pytest

from chantier.board.forge_kind import forge_of

GITLAB = "https://gitlab.example.com/acme/demo/-/merge_requests/4"
GITHUB = "https://github.com/acme/demo/pull/4"


@pytest.mark.parametrize(
    ("state", "origin", "forge"),
    [
        ({"batch": {"crs": [{"pr": GITLAB}]}, "history": []}, "", "gitlab"),
        ({"batch": None, "history": [{"crs": [{"pr": GITLAB}]}]}, "", "gitlab"),
        ({"batch": {"crs": [{"pr": GITHUB}]}, "history": []}, "", "github"),
        (
            {"batch": {"crs": [{"pr": None}]}, "history": []},
            "git@gitlab.example.com:a/b.git",
            "gitlab",
        ),
        ({"batch": None, "history": []}, "https://github.com/a/b", "github"),
        ({"batch": {"crs": [{"pr": GITHUB}]}, "history": []}, "https://gitlab.com/a/b", "github"),
        ({"batch": None, "history": []}, "https://forge.example.com/a/b", None),
        ({"batch": None, "history": []}, "", None),
    ],
)
def test_the_forge_is_told_from_the_links_first_then_from_the_origin_host(
    state: dict[str, Any], origin: str, forge: str | None
) -> None:
    assert forge_of(state, origin) == forge
