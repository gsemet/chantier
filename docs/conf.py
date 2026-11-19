"""Sphinx configuration of chantier's documentation (built by `just docs`, published on Read the Docs)."""

import tomllib
from pathlib import Path

_pyproject = tomllib.loads((Path(__file__).parent.parent / "pyproject.toml").read_text("utf-8"))

project = "chantier"
copyright = "chantier contributors"  # noqa: A001
release = _pyproject["project"]["version"]
version = release

extensions = [
    "myst_parser",
    "sphinx_design",
    "sphinx_copybutton",
]

myst_enable_extensions = ["colon_fence", "deflist"]
myst_heading_anchors = 3

exclude_patterns = ["_build", "demo/**", "release-notes/**", "*-texts.md", "**/*-texts.md"]

html_theme = "furo"
html_title = "chantier"
html_logo = "logo.svg"
html_theme_options = {
    "source_repository": "https://github.com/gsemet/chantier/",
    "source_branch": "main",
    "source_directory": "docs/",
}
