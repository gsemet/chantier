# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.49"]
# ///
"""Take the screenshots of docs/web-board/ from the real web board, on the fictional demo.

It copies docs/demo/ to a temporary folder outside the repository, starts `chantier board` on the
copy (loopback, any free port, the clock fixed), opens the board's pages in Chromium at a laptop
and a phone size, and writes `docs/web-board/<view>-pc.png` and `<view>-phone.png`. The server is
stopped whatever happens. Nothing falls back: a step that fails stops the script.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import Page, Route, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "docs" / "demo"
OUT = ROOT / "docs" / "web-board"
CLOCK = "2026-06-18T10:30:00Z"
SIZES = {"pc": {"width": 1400, "height": 860}, "phone": {"width": 375, "height": 812}}
SURFACE_SHOWN = "/home/demo/planning-surface"  # the surface's name and path in the pictures
INCIDENT = "staged-0123456789abcdef0123"


def run(*cmd: str, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def make_surface(parent: Path) -> Path:
    """A copy of the demo, a git repository, and the autosync tool's state files."""
    surface = parent / "surface"
    shutil.copytree(DEMO, surface)
    git = (
        "git",
        "-c",
        "core.autocrlf=false",
        "-c",
        "user.name=demo",
        "-c",
        "user.email=demo@example.com",
    )
    # The project's clone holds a chantier.yaml: the repository layer overrides one Copilot role.
    clone = surface / "projects" / "shop-api" / ".repo"
    clone.mkdir()
    (clone / "chantier.yaml").write_text(
        "hosts:\n  copilot:\n    roles:\n      debugger:\n        model: gpt-6.1-terra\n",
        encoding="utf-8",
    )
    run(*git, "init", "-q", "-b", "main", cwd=surface)
    run(*git, "add", "-A", cwd=surface)
    run(*git, "commit", "-q", "-m", "demo", cwd=surface)
    state = surface / ".git" / "ai-autosync"
    state.mkdir()
    (state / "control.json").write_text(json.dumps({"enabled": True}), encoding="utf-8")
    (state / "status.json").write_text(
        json.dumps(
            {
                "state": "approval_required",
                "message": "3 staged files look like secrets: projects/shop-api/.env.local, "
                "projects/shop-api/keys/dev.pem, projects/mobile-app/google-services.json",
                "updated_at": 1781778000.0,
                "incident": INCIDENT,
            }
        ),
        encoding="utf-8",
    )
    return surface


def start_board(surface: Path, home: Path) -> tuple[subprocess.Popen[str], str]:
    env = {
        **{k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"},
        "HOME": str(home),
        "USERPROFILE": str(home),
        "CHANTIER_ROOT": str(surface),
        "CHANTIER_CLAUDE_PROJECTS": str(home / "no-transcripts"),
        "PYTHONUTF8": "1",
    }
    (home / "no-transcripts").mkdir(parents=True, exist_ok=True)
    cli = ROOT / "skills" / "chantier" / "scripts" / "cli"
    cmd = [
        "uv",
        "run",
        "--locked",
        "--project",
        str(ROOT),
        "chantier",
        "board",
        "--host",
        "127.0.0.1",
        "--port",
        "0",
        "--clock",
        CLOCK,
    ]
    if not (ROOT / ".git").exists() or not cli.exists():
        raise SystemExit("run this from chantier's own checkout")
    proc = subprocess.Popen(
        cmd,
        cwd=surface,
        env=env,
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        start_new_session=os.name != "nt",
    )
    assert proc.stdout is not None
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line:
            break
        found = re.match(r"board on (\S+) over", line)
        if found:
            return proc, found[1]
    stop(proc)
    raise SystemExit("the board did not print its address")


def stop(proc: subprocess.Popen[str]) -> None:
    """Stop the server and the processes it started (the launcher is not the server)."""
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(proc.pid)], check=False, capture_output=True
        )
    else:
        os.killpg(proc.pid, signal.SIGTERM)
    proc.wait(timeout=30)


def settle(page: Page) -> None:
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(400)


def goto(page: Page, url: str, view: str, project: str) -> None:
    base = url.split("#")[0]
    sep = "&" if "?" in base else "?"
    page.goto(f"{base}{sep}p={project}&v={view}&lang=en")
    page.wait_for_selector("[data-key]", state="attached")
    settle(page)


def shot(page: Page, name: str, size: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUT / f"{name}-{size}.png"), animations="disabled", caret="hide")
    print(f"wrote docs/web-board/{name}-{size}.png")


def fix_surface_path(route: Route) -> None:
    """The board shows the surface's path, a temporary folder of this machine: the pictures show
    this made-up path instead, the same on every run and revealing nothing of the machine. In the
    board's answer, `served`, `served_origin` and each project's `repo_path` and `origin` are
    replaced; the projects' `folder` and `repo` are the demo's own, relative."""
    response = route.fetch()
    body = response.json()
    body["served"] = SURFACE_SHOWN
    body["served_origin"] = "https://github.com/demo/planning-surface"
    for project in body.get("projects", []):
        project["repo_path"] = f"/home/demo/{project['id']}"
        project["origin"] = f"https://github.com/demo/{project['id']}"
    route.fulfill(response=response, json=body)


def capture(url: str) -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            for size, viewport in SIZES.items():
                ctx = browser.new_context(
                    viewport=viewport,
                    locale="en-US",
                    timezone_id="UTC",
                    color_scheme="light",
                    reduced_motion="reduce",
                    device_scale_factor=1,
                    is_mobile=size == "phone",
                    has_touch=size == "phone",
                )
                ctx.clock.set_fixed_time("2026-06-18T10:30:00Z")
                ctx.route("**/api/board*", fix_surface_path)
                page = ctx.new_page()
                views(page, url, size)
                ctx.close()
        finally:
            browser.close()


def views(page: Page, url: str, size: str) -> None:
    goto(page, url, "home", "*")
    shot(page, "home", size)
    goto(page, url, "home", "shop-api")
    shot(page, "project", size)
    goto(page, url, "batch", "shop-api")
    shot(page, "batch", size)
    goto(page, url, "kanban", "shop-api")
    shot(page, "kanban", size)
    goto(page, url, "triage", "shop-api")
    shot(page, "triage", size)
    goto(page, url, "costs", "mobile-app")
    shot(page, "costs", size)
    goto(page, url, "config", "shop-api")
    page.wait_for_selector('.config[data-key="config"]')
    settle(page)
    if size == "pc":
        # The page scrolls inside its pane: show the Copilot section (its table, with the rows a
        # repository file overrides, and its open list of models with their plans), in a taller view.
        page.set_viewport_size({"width": SIZES["pc"]["width"], "height": 1500})
        page.locator("details.catalog").evaluate("el => { el.open = true; }")
        page.locator("section.host").nth(1).evaluate("el => el.scrollIntoView({block: 'start'})")
        page.wait_for_timeout(300)
    shot(page, "config", size)
    if size == "pc":
        page.set_viewport_size(SIZES["pc"])
    for step in EXTRA:
        step(page, url, size)


def panel(page: Page, url: str, size: str) -> None:
    goto(page, url, "batch", "shop-api")
    page.locator('[data-key="node-open-c:CR-145"], [data-key^="open-c:CR-145"]').first.click()
    page.wait_for_selector('[data-key^="file-"]')
    settle(page)
    shot(page, "panel", size)


def autosync(page: Page, url: str, size: str) -> None:
    goto(page, url, "home", "*")
    pill = page.locator('[data-key="autosync-pill"], [data-key="autosync-dot"]')
    pill.locator("visible=true").first.click()
    page.locator(".apop").locator("visible=true").first.wait_for()
    settle(page)
    shot(page, "autosync", size)


def editor(page: Page, url: str, size: str) -> None:
    goto(page, url, "kanban", "shop-api")
    page.locator('[data-open^="i:"][data-open*="saved-addresses"]').locator(
        "visible=true"
    ).first.click()
    page.wait_for_selector('[data-key^="file-"]', state="attached")
    page.locator('[data-file$="03-change-spec.md"]').locator("visible=true").first.click()
    page.locator('[data-key="edit-start"]').locator("visible=true").first.click()
    page.wait_for_selector("textarea")
    settle(page)
    shot(page, "editor", size)


def new_dialog(page: Page, url: str, size: str) -> None:
    goto(page, url, "triage", "shop-api")
    page.get_by_role("button", name="+ New").locator("visible=true").first.click()
    page.wait_for_selector("dialog[open]")
    settle(page)
    shot(page, "new", size)


def picker(page: Page, url: str, size: str) -> None:
    goto(page, url, "home", "shop-api")
    page.locator('[data-menu="toggle"]').locator("visible=true").first.click()
    page.locator('.menu[role="menu"]').locator("visible=true").first.wait_for()
    settle(page)
    shot(page, "picker", size)


def selection(page: Page, url: str, size: str) -> None:
    if size != "phone":
        return
    goto(page, url, "triage", "shop-api")
    for index in range(2):
        page.locator(".pi").locator("visible=true").nth(index).click(position={"x": 6, "y": 6})
    page.wait_for_selector(".selbar")
    settle(page)
    shot(page, "triage-selection", size)


EXTRA = [panel, editor, new_dialog, autosync, picker, selection]


def main() -> None:
    run(sys.executable, "-m", "playwright", "install", "chromium")
    work = Path(tempfile.mkdtemp(prefix="chantier-docs-"))
    proc: subprocess.Popen[str] | None = None
    try:
        surface = make_surface(work)
        home = work / "home"
        home.mkdir()
        proc, url = start_board(surface, home)
        capture(url)
    finally:
        if proc is not None:
            stop(proc)
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
