"""The code's own targets: the sizes of files and functions, no import cycle, and one project
for the CLI. `just lint` holds the style; these two checks hold what a linter does not."""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

CLI = Path(__file__).resolve().parents[1]
MAX_FILE_LINES = 400
MAX_FUNCTION_LINES = 50
MAX_SCRIPT_LINES = 300
SCOPE = [
    path
    for path in sorted(CLI.rglob("*.py"))
    if not {".venv", "__pycache__"} & set(path.relative_to(CLI).parts)
]


def _module(path: Path) -> str:
    parts = list(path.relative_to(CLI / "src").with_suffix("").parts)
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _imports(path: Path) -> set[str]:
    """The `chantier` modules a file imports, imports inside functions included."""
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("chantier"):
            found.add(node.module)
            found.update(f"{node.module}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Import):
            found.update(a.name for a in node.names if a.name.startswith("chantier"))
    return found


def _cycle(graph: dict[str, set[str]]) -> list[str] | None:
    state: dict[str, int] = {}
    trail: list[str] = []

    def visit(name: str) -> list[str] | None:
        state[name] = 1
        trail.append(name)
        for nxt in sorted(graph[name]):
            if state.get(nxt) == 1:
                return [*trail[trail.index(nxt) :], nxt]
            if nxt in graph and nxt not in state and (found := visit(nxt)):
                return found
        trail.pop()
        state[name] = 2
        return None

    for name in sorted(graph):
        if name not in state and (found := visit(name)):
            return found
    return None


def _size_problems(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    problems = []
    if len(text.splitlines()) > MAX_FILE_LINES:
        problems.append(f"{path.relative_to(CLI)}: over {MAX_FILE_LINES} lines")
    functions = [
        n
        for n in ast.walk(ast.parse(text))
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
    ]
    for node in functions:
        size = (node.end_lineno or node.lineno) - node.lineno + 1
        if size > MAX_FUNCTION_LINES:
            problems.append(f"{path.relative_to(CLI)}: {node.name} has {size} lines")
    return problems


def test_files_and_functions_are_small_and_the_imports_have_no_cycle() -> None:
    problems = [p for path in SCOPE for p in _size_problems(path)]
    graph = {_module(p): _imports(p) for p in SCOPE if (CLI / "src") in p.parents}
    cycle = _cycle({name: {m for m in deps if m in graph} for name, deps in graph.items()})
    if cycle:
        problems.append("import cycle: " + " -> ".join(cycle))
    assert not problems, "\n".join(problems)


def test_one_root_project_holds_the_dependencies_and_nothing_else_is_a_script() -> None:
    root = CLI.parents[3]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert all("==" in dep for dep in project["project"]["dependencies"]), "pin each with =="
    assert project["tool"]["uv"]["no-build"] is True
    assert not (CLI / "pyproject.toml").exists()
    assert not (CLI / "chantier.py").exists()
    blocks = [
        path.name
        for path in SCOPE
        if re.search(r"(?m)^# /// script\r?$", path.read_text(encoding="utf-8"))
    ]
    assert blocks == ["session_usage.py"], blocks


def test_the_web_frame_has_small_scripts_and_both_word_files_share_their_keys() -> None:
    web = CLI / "src" / "chantier" / "board" / "web"
    scripts = sorted((web / "js").rglob("*.js"))
    assert scripts, "no script in the web frame"
    problems = []
    for path in scripts:
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > MAX_SCRIPT_LINES:
            problems.append(f"{path.relative_to(web)}: {lines} lines (max 300)")
    keys = {
        lang: set(
            re.findall(
                r"^\s*'([\w.]+)':",
                (web / "js" / "i18n" / f"{lang}.js").read_text(encoding="utf-8"),
                re.M,
            )
        )
        for lang in ("en", "fr")
    }
    if keys["en"] != keys["fr"]:
        problems.append(f"word files differ: {sorted(keys['en'] ^ keys['fr'])}")
    assert not problems, "\n".join(problems)


START_UP_PROGRAM = """
import contextlib
import io
import sys
from chantier.cli import main
with contextlib.redirect_stdout(io.StringIO()), contextlib.suppress(SystemExit):
    main(sys.argv[1:])
print("\\n".join(sorted({name.split(".")[0] for name in sys.modules})))
"""
SITE_HOOKS = {"_virtualenv", "_distutils_hack", "sitecustomize", "usercustomize"}


def test_the_start_up_imports_only_the_standard_library_and_chantier() -> None:
    problems = []
    for argv in (["--version"], ["--help"]):
        run = subprocess.run(
            [sys.executable, "-c", START_UP_PROGRAM, *argv],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            env={**os.environ, "PYTHONPATH": str(CLI / "src")},
        )
        allowed = set(sys.stdlib_module_names) | SITE_HOOKS | {"chantier", "__main__"}
        extra = sorted(set(run.stdout.split()) - allowed)
        if extra:
            problems.append(
                f"`chantier {argv[0]}` imports {', '.join(extra)} at start: "
                "import them in the command that needs them"
            )
    assert not problems, "\n".join(problems)


WEB = CLI / "src" / "chantier" / "board" / "web"
MAX_STYLE_LINES = 300
MAX_NESTING = 3
COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgb|rgba|hsl|hsla|oklch)\(")


def _inside(origin: Path, ref: str) -> str | None:
    """Why a reference leaves the web folder, else None."""
    if re.match(r"[a-z][a-z0-9+.-]*:|//|/", ref, re.I):
        return f"{ref!r} is not relative"
    target = (origin.parent / ref.split("?", maxsplit=1)[0].split("#", maxsplit=1)[0]).resolve()
    if WEB.resolve() not in target.parents:
        return f"{ref!r} leaves the web folder"
    return None if target.is_file() else f"{ref!r} does not exist"


def _reference_problems(path: Path, text: str) -> list[str]:
    pattern = {
        ".html": r"""(?:href|src)=["']([^"']+)["']""",
        ".js": r"""(?:from|import)\s*\(?\s*["'](\.[^"']*)["']""",
        ".css": r"""(?:@import\s+|url\()["']?([^"')\s;]+)""",
    }[path.suffix]
    found = [_inside(path, ref) for ref in re.findall(pattern, text)]
    return [f"{path.relative_to(WEB)}: {why}" for why in found if why]


def _markup_problems(text: str) -> list[str]:
    problems = []
    if re.search(r"<script(?![^>]*\bsrc=)", text) or "<style" in text:
        problems.append("index.html has an inline script or style")
    if re.search(r"""\sstyle\s*=|\son[a-z]+\s*=""", text):
        problems.append("index.html has a style or on... attribute")
    return problems


def _style_problems(path: Path, text: str) -> list[str]:
    bare = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    problems = []
    if len(text.splitlines()) > MAX_STYLE_LINES:
        problems.append(f"over {MAX_STYLE_LINES} lines")
    if any("#" in prelude for prelude in re.findall(r"([^{};]+)\{", bare)):
        problems.append("an id selector")
    depth = deepest = 0
    for char in bare:
        depth += (char == "{") - (char == "}")
        deepest = max(deepest, depth)
    if deepest > MAX_NESTING:
        problems.append(f"nesting {deepest} deep (max {MAX_NESTING})")
    if path.name != "tokens.css" and COLOUR.search(bare):
        problems.append("a colour outside tokens.css")
    return [f"{path.relative_to(WEB)}: {p}" for p in problems]


def _script_problems(path: Path, text: str) -> list[str]:
    problems = []
    if path.name != "dom.js" and re.search(r"innerHTML\s*=|insertAdjacentHTML|outerHTML\s*=", text):
        problems.append("sets HTML outside dom.js")
    if re.search(r"""\sstyle\s*=\s*["']|\son[a-z]+\s*=\s*["']""", text):
        problems.append("writes a style or on... attribute in markup")
    return [f"{path.relative_to(WEB)}: {p}" for p in problems]


def test_the_web_frame_is_self_contained_and_follows_the_style_rules() -> None:
    problems = _markup_problems((WEB / "index.html").read_text(encoding="utf-8"))
    for path in sorted(p for p in WEB.rglob("*") if p.suffix in {".html", ".js", ".css"}):
        text = path.read_text(encoding="utf-8")
        problems += _reference_problems(path, text)
        if re.search(r"https?://", text):
            problems.append(f"{path.relative_to(WEB)}: names another origin")
        if path.suffix == ".css":
            problems += _style_problems(path, text)
        elif path.suffix == ".js":
            problems += _script_problems(path, text)
    assert not problems, "\n".join(problems)
