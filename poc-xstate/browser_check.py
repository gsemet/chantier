# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.49"]
# ///
"""The PRs feed on the real board, in Chromium: the worktree's `chantier board` on a copy of the
fictional demo (loopback, any free port), the page's clock driven by Playwright, the forge's
answers made up by the test (no `gh`, no network). It prints each check and fails on the first
wrong one. Run from the repository: `uv run --script poc-xstate/browser_check.py`."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from playwright.sync_api import Route, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from docs_screenshots import make_surface, start_board, stop  # noqa: E402

asked: list[float] = []
answer = {"all_done": False}


def fake_prs(route: Route) -> None:
    asked.append(0.0)
    body = {"batch": "batch-05", "rows": [], "all_done": answer["all_done"], "now": None}
    route.fulfill(json=body)


def check(name: str, got: int, want: int) -> None:
    print(f"{'ok  ' if got == want else 'FAIL'} {name}: {got} reads (want {want})")
    if got != want:
        raise SystemExit(1)


def advance(page, ms: int) -> None:
    """Move the page's clock, then give the page real time to send and read its requests."""
    page.clock.run_for(ms)
    page.wait_for_timeout(60)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        surface = make_surface(Path(tmp))
        proc, url = start_board(surface, Path(tmp) / "home")
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                page = browser.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.on("console", lambda m: m.type == "error" and errors.append(m.text))
                page.clock.install()
                page.route("**/api/projects/shop-api/prs", fake_prs)
                base = url.split("#")[0]
                sep = "&" if "?" in base else "?"
                page.goto(f"{base}{sep}p=shop-api&v=prs&lang=en")
                page.wait_for_selector(".prview")
                # The view opens before or after the project's record arrives: with its PR
                # links, the feed may read once more. Wait for that, then count by windows.
                for _ in range(3):
                    advance(page, 1_000)
                print(f"     opening: {len(asked)} reads")

                def window(name: str, seconds: int, want: int) -> None:
                    before = len(asked)
                    for _ in range(seconds):
                        advance(page, 1_000)
                    check(name, len(asked) - before, want)

                window("open PRs, visible, 30 s", 30, 3)
                show = "Object.defineProperty(document,'visibilityState',{value:%r,configurable:true});"
                event = "document.dispatchEvent(new Event('visibilitychange'))"
                page.evaluate(show % "hidden" + event)
                window("open PRs, hidden, 30 s", 30, 0)
                page.evaluate(show % "visible" + event)
                window("open PRs, shown again: one read at once", 1, 1)
                window("open PRs, visible again, 10 s", 10, 1)
                answer["all_done"] = True
                window("the next read finds every PR done", 10, 1)
                window("every PR done, 60 s", 60, 0)
                answer["all_done"] = False
                page.evaluate(show % "hidden" + event)
                window("every PR done, hidden, 30 s", 30, 0)
                page.evaluate(show % "visible" + event)
                window("every PR done, shown again", 1, 0)
                page.goto(f"{base}{sep}p=shop-api&v=home&lang=en")
                page.wait_for_selector("[data-key]", state="attached")
                window("the view left, 60 s", 60, 0)
                print("ok   no page error" if not errors else f"FAIL page errors: {errors}")
                if errors:
                    raise SystemExit(1)
                browser.close()
        finally:
            stop(proc)


if __name__ == "__main__":
    main()
