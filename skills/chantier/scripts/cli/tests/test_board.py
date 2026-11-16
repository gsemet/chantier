"""The web board's structure: its modules, the lazy imports of its server, the frame it ships.
The behaviour (key, guard, state, files, costs, seats) belongs to `just scenario`."""

from __future__ import annotations

import ast
import io
import json
import os
import socket
import subprocess
import sys
import time
import tomllib
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest
from batch_helpers import prepared
from conftest import Chantier

from chantier.autosync.site import AutosyncSite
from chantier.board import address, autosync_tool
from chantier.board.guard import NEEDS_KEY
from chantier.core.errors import EXIT_EXTERNAL

CLI = Path(__file__).resolve().parents[1]
BOARD = CLI / "src" / "chantier" / "board"
MODULES = [
    "command",
    "address",
    "key",
    "projects",
    "state",
    "files",
    "fingerprint",
    "costs",
    "seats",
    "app",
    "routes",
    "guard",
    "reply",
    "static",
    "context",
    "journal",
    "write_api",
]
LAZY = ("starlette", "uvicorn")


def _top_level_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_the_board_is_one_package_of_small_modules_with_no_server_of_html() -> None:
    missing = [m for m in MODULES if not (BOARD / f"{m}.py").is_file()]
    gone = [m for m in ("collect", "render", "server") if (BOARD / f"{m}.py").exists()]
    assert not missing and not gone, f"missing {missing}, still there {gone}"


def test_the_web_framework_loads_only_when_the_board_serves() -> None:
    root = CLI.parents[3]
    ruff = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["ruff"]
    banned = ruff["lint"]["flake8-tidy-imports"]["banned-module-level-imports"]
    assert all(name in banned for name in LAZY), banned
    eager = [
        str(path.relative_to(CLI))
        for path in sorted((CLI / "src").rglob("*.py"))
        if set(LAZY) & _top_level_imports(path)
    ]
    assert not eager, eager


def test_the_frame_is_shipped_with_the_package() -> None:
    web = BOARD / "web"
    for name in (
        "index.html",
        "js/main.js",
        "js/core/store.js",
        "js/views/registry.js",
        "css/tokens.css",
        "css/shell.css",
        "js/i18n/en.js",
        "js/i18n/fr.js",
    ):
        assert (web / name).is_file(), name


def test_board_does_not_join_autosync_implicitly() -> None:
    source = (BOARD / "command.py").read_text(encoding="utf-8")
    assert "spawn_join" not in source
    assert "_join_autosync" not in source


def test_two_start_stop_cycles_reuse_one_live_board_participant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("liveness must neither signal a real process nor start autosync")

    monkeypatch.setattr(os, "kill", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    state = tmp_path / "git" / "ai-autosync"
    participants = state / "participants"
    participants.mkdir(parents=True)
    (participants / f"{os.getpid()}.json").write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "session_id": autosync_tool.SESSION_ID,
                "since": time.time(),
            }
        ),
        encoding="utf-8",
    )
    site = AutosyncSite(tmp_path, tmp_path / "script.py", "", state, False)
    assert autosync_tool.spawn_join(site, os.getpid()) is None
    assert autosync_tool.spawn_join(site, os.getpid()) is None
    assert len(list(participants.glob("*.json"))) == 1


@pytest.mark.parametrize("platform", ["win32", "linux"])
@pytest.mark.parametrize("state", ["live", "reused", "gone", "denied", "zombie", "invalid-pid"])
def test_existing_join_checks_process_identity_without_signals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str, state: str
) -> None:
    import psutil

    fake_pid = 42

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("liveness must never signal a process")

    def process(pid: int) -> SimpleNamespace:
        assert pid == fake_pid
        if state == "gone":
            raise psutil.NoSuchProcess(pid)
        if state == "denied":
            raise psutil.AccessDenied(pid)
        return SimpleNamespace(
            is_running=lambda: True,
            status=lambda: psutil.STATUS_ZOMBIE if state == "zombie" else psutil.STATUS_RUNNING,
            create_time=lambda: 200 if state == "reused" else 99,
        )

    monkeypatch.setattr(os, "kill", forbidden)
    monkeypatch.setattr(psutil, "Process", process)
    monkeypatch.setattr(sys, "platform", platform)
    participants = tmp_path / "participants"
    participants.mkdir()
    (participants / "42.json").write_text(
        json.dumps(
            {
                "pid": -1 if state == "invalid-pid" else fake_pid,
                "session_id": autosync_tool.SESSION_ID,
                "since": 100,
            }
        ),
        encoding="utf-8",
    )
    site = AutosyncSite(tmp_path, tmp_path / "script.py", "", tmp_path, False)
    expected = state == "live" or (state == "denied" and platform == "win32")
    assert autosync_tool._existing_join(site, autosync_tool.SESSION_ID) is expected


def _child(code: str) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [sys.executable, "-c", code],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def test_join_observe_reports_early_failure_exactly() -> None:
    proc = _child("import sys; sys.stderr.write('early diagnostic\\n'); sys.exit(7)")
    assert autosync_tool.observe_join(proc, timeout=1) == "early diagnostic"


def test_join_watch_reports_delayed_failure_exactly() -> None:
    proc = _child(
        "import sys; sys.stdin.buffer.read(1); "
        "sys.stderr.write('delayed diagnostic\\n'); sys.exit(9)"
    )
    messages: list[str] = []
    try:
        assert autosync_tool.observe_join(proc, timeout=0.01) is None
        watcher = autosync_tool.watch_join(proc, messages.append)
        assert proc.poll() is None
        assert proc.stdin is not None
        proc.stdin.write(b"x")
        proc.stdin.close()
        watcher.join(timeout=3)
        assert not watcher.is_alive()
        assert messages == ["board: autosync not joined: delayed diagnostic"]
    finally:
        if proc.poll() is None:
            proc.terminate()
        proc.wait(timeout=3)
        if proc.stdin is not None:
            proc.stdin.close()


def test_join_watch_does_not_report_a_success_that_stays_alive() -> None:
    proc = _child("import sys; sys.stdin.buffer.read(1)")
    messages: list[str] = []
    try:
        assert autosync_tool.observe_join(proc, timeout=0.01) is None
        watcher = autosync_tool.watch_join(proc, messages.append)
        assert proc.poll() is None
        assert messages == []
        assert proc.stdin is not None
        proc.stdin.close()
        watcher.join(timeout=3)
        assert not watcher.is_alive()
        assert proc.returncode == 0
        assert messages == []
    finally:
        if proc.poll() is None:
            proc.terminate()
        proc.wait(timeout=3)
        if proc.stdin is not None:
            proc.stdin.close()


def test_join_drains_large_output_without_deadlock() -> None:
    proc = _child(
        "import sys; sys.stdout.write('x'*2_000_000); "
        "sys.stderr.write('large-output diagnostic\\n'); sys.exit(4)"
    )
    assert autosync_tool.observe_join(proc, timeout=3) == "large-output diagnostic"


def test_a_held_port_is_refused_with_the_port_and_the_way_out(
    repo: Path, chantier: Chantier
) -> None:
    prepared(repo, chantier, "Board one")
    with socket.socket() as held:
        held.bind(("127.0.0.1", 0))
        held.listen()
        port = held.getsockname()[1]
        code, out, err = chantier("board", "--host", "127.0.0.1", "--port", str(port))
    assert code == EXIT_EXTERNAL and not out
    assert err.count("\n") == 1 and err.startswith("error: board not started: ")
    assert f"port {port}" in err and "--port" in err


@pytest.mark.parametrize(
    ("code", "body", "expected"),
    [(401, NEEDS_KEY, "another-key"), (401, "nope", "other"), (404, NEEDS_KEY, "other")],
)
def test_the_probe_tells_a_board_behind_another_key_from_any_other_answer(
    monkeypatch: pytest.MonkeyPatch, code: int, body: str, expected: str
) -> None:
    def call(*_a: object, **_k: object) -> None:
        raise urllib.error.HTTPError("u", code, "x", {}, io.BytesIO(body.encode()))  # type: ignore[arg-type]

    monkeypatch.setattr(address, "_call", call)
    assert address.probe("127.0.0.1", 1, "k") == expected
