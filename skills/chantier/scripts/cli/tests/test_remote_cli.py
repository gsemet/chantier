"""Remote commands: the profiles file, `login` and `logout`, which command goes to a profile's
server (and which never does), the call a forwarded command makes, and the server's `cli.run`
op (its refusals, the child's environment, the idle count). The HTTP call is faked; one real
`cli.run` shows the command a profile forwards runs here, with no loop."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from api_client import call_op
from conftest import Chantier
from test_board_prs import Board

from chantier.board import cli_run
from chantier.board.idle import LOOK_S, Runs
from chantier.clients import profiles as store
from chantier.clients import remote
from chantier.clients.profiles import Profile, Profiles
from chantier.core.origin import normalize_origin
from chantier.core.remote_wire import FORWARDED_ENV, VIA_SERVER
from chantier.core.repo import Repo
from chantier.hub import autostart
from chantier.plugin_files import cli_command

URL = "http://10.0.0.5:9000/"
LINK = f"{URL}?k=secret"
BAD_ARGS, CONFLICT_CODE, EXTERNAL, OK, PRECONDITION, MODE, TWO = 400, 404, 4, 200, 2, 0o600, 2


def _profile(**kw: Any) -> Profile:
    base: dict[str, Any] = {
        "url": URL,
        "key": "secret",
        "access": "write",
        "projects": [],
        "origin": None,
        "served": "/srv/surface",
        "version": "9.9.9",
        "saved": "t",
    }
    return Profile(**{**base, **kw})


def _login(project: str, **kw: Any) -> None:
    store.save(Profiles("default", {"default": _profile(projects=[project], **kw)}))


class Server:
    """What the faked `remote.post` answers, and the calls it got."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.board: dict[str, Any] = {"version": "9.9.9", "served": "/srv", "projects": []}
        self.access: str | None = "write"
        self.status = OK
        self.run: dict[str, Any] = {"code": 0, "stdout": "", "stderr": "", "launch": "REMOTE"}
        self.down = False

    def post(
        self, base: str, key: str, op: str, body: dict[str, Any], timeout: float
    ) -> remote.Reply:
        self.calls.append((op, key, body))
        if self.down:
            raise remote.Unreachable("connection refused")
        data = self.board if op == "board.get" else self.run
        return remote.Reply(
            self.status, self.access, data, "refused" if self.status != OK else None
        )


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> Server:
    fake = Server()
    monkeypatch.setattr(remote, "post", fake.post)
    return fake


def _project(repo: Path) -> str:
    return repo.name


@pytest.mark.parametrize(
    ("platform", "environ", "want"),
    [
        ("linux", {"CHANTIER_CONFIG_HOME": "/c"}, Path("/c")),
        ("win32", {"APPDATA": "/a"}, Path("/a/chantier")),
        ("linux", {"XDG_CONFIG_HOME": "/x"}, Path("/x/chantier")),
        ("linux", {}, Path.home() / ".config" / "chantier"),
    ],
)
def test_the_config_folder(platform: str, environ: dict[str, str], want: Path) -> None:
    assert store.config_dir(platform, environ) == want


@pytest.mark.parametrize(
    ("url", "want"),
    [
        ("https://GitHub.com/a/b.git", "github.com/a/b"),
        ("git@github.com:a/b.git", "github.com/a/b"),
        ("ssh://git@github.com:22/a/b/", "github.com/a/b"),
        ("", None),
    ],
)
def test_one_repository_is_one_origin(url: str, want: str | None) -> None:
    assert normalize_origin(url) == want


def test_login_stores_the_profile_lists_it_and_logout_forgets_it(
    repo: Path, chantier: Chantier, server: Server
) -> None:
    server.board["projects"] = [{"id": "a"}, {"id": "b"}]
    server.board["home"] = "a"
    code, out, _ = chantier("login", LINK, "--project", "b", "--project", "a")
    assert code == 0 and "for b, a" in out[0] and "the default" in out[0]
    stored = store.load()
    assert stored.default == "default" and stored.items["default"].projects == ["b", "a"]
    if sys.platform != "win32":
        assert store.path().stat().st_mode & 0o777 == MODE
    server.access = "read"
    assert chantier("login", LINK, "--profile", "ro", "--no-default")[0] == 0
    code, out, _ = chantier("login")
    assert code == 0 and len(out) == TWO and all("secret" not in x for x in out)
    assert chantier("logout", "--profile", "ro")[0] == 0
    assert chantier("logout")[1] == ["logged out: profile default; commands run here again"]
    assert store.load().items == {}


@pytest.mark.parametrize(
    ("setup", "args", "want"),
    [
        ({"status": 401}, ["--project", "a"], (EXTERNAL, "refused the key")),
        ({"down": True}, [], (EXTERNAL, "no chantier server answers")),
        ({"access": None}, [], (EXTERNAL, "older chantier")),
        ({}, ["--project", "zz"], (1, "serves a")),
        ({}, ["--profile", "local"], (1, "not a profile name")),
    ],
)
def test_a_login_that_cannot_be_made_stores_nothing(
    chantier: Chantier,
    server: Server,
    setup: dict[str, Any],
    args: list[str],
    want: tuple[int, str],
) -> None:
    code, text = want
    server.board.update(projects=[{"id": "a"}], home="a")
    for name, value in setup.items():
        setattr(server, name, value)
    got, _, err = chantier("login", LINK, *args)
    assert (got, text in err) == (code, True), err
    assert not store.path().exists()


def test_a_malformed_profiles_file_stops_every_command(repo: Path, chantier: Chantier) -> None:
    store.path().parent.mkdir(parents=True, exist_ok=True)
    store.path().write_text("{nope", encoding="utf-8")
    code, _, err = chantier("rules")
    assert code == PRECONDITION and "fix or delete it" in err
    assert chantier("--profile", "local", "rules")[0] == 0  # the server's child never reads it


def test_which_commands_go_to_the_server(
    repo: Path, chantier: Chantier, server: Server, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert chantier("rules")[0] == 0 and server.calls == []  # no profile: here
    _login(_project(repo))
    server.run.update(code=3, stdout="out\n", stderr="REMOTE says\n")
    code, out, err = chantier("rules")
    assert (code, out) == (3, ["out"]) and "REMOTE" not in err
    op, key, body = server.calls[-1]
    assert (op, key, body["argv"], body["project"]) == ("cli.run", "secret", ["rules"], repo.name)
    _login("elsewhere")
    server.calls.clear()
    assert chantier("rules")[0] == 0 and server.calls == []  # another project: here
    assert chantier("--profile", "default", "rules")[0] == 1  # named, but not for this project
    Repo.find(readonly=True).changes.mkdir(parents=True, exist_ok=True)  # a surface is here
    _login(_project(repo), origin="other.example/x/y")
    assert chantier("rules")[0] == 0 and server.calls == []  # another repository's surface


@pytest.mark.parametrize(
    "argv",
    [
        ["--profile", "local", "rules"],
        ["login"],
        ["watch"],
        ["live", "--once"],
        ["webui"],
    ],
)
def test_these_never_reach_the_server(
    repo: Path, chantier: Chantier, server: Server, argv: list[str]
) -> None:
    _login(_project(repo))
    chantier(*argv)
    assert server.calls == []


def test_a_command_goes_with_the_options_a_profile_takes_over_removed(
    repo: Path, chantier: Chantier, server: Server, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login(_project(repo))
    monkeypatch.setenv("CHANTIER_BATCH", "7")
    monkeypatch.setenv(VIA_SERVER, "1")
    chantier("--prof", "default", "rules", f"--proj={repo.name}", "--skill", "y")
    body = server.calls[-1][2]
    assert body["argv"] == ["rules"] and body["env"] == {"CHANTIER_BATCH": "7"}
    assert VIA_SERVER not in body["env"] and set(body["env"]) <= set(FORWARDED_ENV)


def test_gate_and_a_read_only_profile_are_refused_and_stdin_goes_for_a_journal_add(
    repo: Path, chantier: Chantier, server: Server, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login(_project(repo))
    assert chantier("gate", "CR-1", "scenario")[0] == 1 and server.calls == []
    code, _, err = chantier("push", "CR-1", "--lease", "1")
    assert code == 1 and "not through a profile" in err and server.calls == []
    monkeypatch.setattr(sys, "stdin", type("S", (), {"buffer": _Bytes(b'{"a": 1}')})())
    chantier("journal", "add", "issue@1", "--json", "-")
    assert server.calls[-1][2]["stdin"] == '{"a": 1}'
    _login(_project(repo), access="read")
    server.calls.clear()
    code, _, err = chantier("rules")
    assert code == 1 and "read-only" in err and server.calls == []


class _Bytes:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def read(self) -> bytes:
        return self.data


@pytest.mark.parametrize(
    ("setup", "text"),
    [
        ({"status": 401}, "refused the key"),
        ({"status": 403}, "read-only"),
        ({"status": 404, "board": {}}, "refused"),
        ({"down": True}, "no chantier server answers"),
        ({"status": 400}, "refused"),
    ],
)
def test_a_remote_refusal_is_exit_4_and_never_runs_the_command_here(
    repo: Path, chantier: Chantier, server: Server, setup: dict[str, Any], text: str
) -> None:
    _login(_project(repo))
    for name, value in setup.items():
        if name != "board":
            setattr(server, name, value)
    code, _, err = chantier("rules")
    assert code == EXTERNAL and text in err


def test_a_command_run_by_the_server_runs_here_with_no_loop(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The server's own config holds a default profile and a malformed file: its child ignores both
    (`--profile local`), and prints no `watch:` line."""
    store.path().parent.mkdir(parents=True, exist_ok=True)
    store.path().write_text("{nope", encoding="utf-8")
    board = Board(repo, [], monkeypatch)
    status, data = call_op(board.ctx, board.key, "cli.run", {"argv": ["status"]})
    assert status == OK and "profiles:" not in data["stderr"], data  # not read: no loop
    assert board.ctx.runs.busy() is True  # a run counts as a client until a look after it
    here = Repo.find(readonly=True)
    assert autostart.not_running_line(here)  # a session of its own is told
    monkeypatch.setenv(VIA_SERVER, "1")
    assert autostart.not_running_line(here) == []  # a client's command is not


@pytest.mark.parametrize(
    ("body", "status"),
    [
        ({"argv": ["status", "--nope"]}, BAD_ARGS),
        ({"argv": ["serve"]}, BAD_ARGS),
        ({"argv": ["watch"]}, BAD_ARGS),
        ({"argv": ["login", "x"]}, BAD_ARGS),
        ({"argv": ["push", "CR-1", "--lease", "1"]}, BAD_ARGS),
        ({"argv": ["status", "--proj=x"]}, BAD_ARGS),
        ({"argv": ["--sk=y", "status"]}, BAD_ARGS),
        ({"argv": ["status"], "env": {"PATH": "x"}}, BAD_ARGS),
        ({"argv": ["status"], "env": {VIA_SERVER: "0"}}, BAD_ARGS),
        ({"argv": ["status\x00"]}, BAD_ARGS),
        ({"argv": ["status"], "stdin": "a\x00"}, BAD_ARGS),
        ({"argv": []}, BAD_ARGS),
        ({"argv": ["status"], "project": "nowhere"}, CONFLICT_CODE),
    ],
)
def test_the_server_refuses_what_it_does_not_run(
    repo: Path, monkeypatch: pytest.MonkeyPatch, body: dict[str, Any], status: int
) -> None:
    board = Board(repo, [], monkeypatch)
    ran: list[Any] = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: ran.append(a))
    assert call_op(board.ctx, board.key, "cli.run", body)[0] == status and ran == []


def test_the_childs_environment_drops_the_servers_session_and_takes_the_clients() -> None:
    server = {"PATH": "p", "CHANTIER_BATCH": "server", "CLAUDE_CODE_SESSION_ID": "s"}
    got = cli_run.child_env(server, {"CHANTIER_BATCH": "client"})
    assert got == {"PATH": "p", "CHANTIER_BATCH": "client", VIA_SERVER: "1"}


def test_a_running_command_is_a_client_for_the_idle_stop_until_a_look_after_it() -> None:
    now = [0.0]
    runs = Runs(lambda: now[0])
    assert runs.busy() is False
    runs.begin()
    now[0] = 10_000.0
    assert runs.busy() is True
    runs.end()
    assert runs.busy() is True
    now[0] += LOOK_S + 2
    assert runs.busy() is False


def test_the_reply_replaces_the_servers_launch_form_with_this_machines(
    repo: Path, chantier: Chantier, server: Server
) -> None:
    _login(_project(repo))
    server.run.update(stdout="run REMOTE now\n")
    out = chantier("rules")[1]
    assert out == ["run " + cli_command(None) + " now"] or "REMOTE" not in out[0]
    assert json.loads(json.dumps(server.run))["launch"] == "REMOTE"
