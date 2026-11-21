"""One conformance test every backend of the plan's store passes. A case whose feature the backend
does not declare is skipped by feature, never failed."""

from __future__ import annotations

import os
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path

import pytest
from conftest import live_writer

from chantier.core.errors import EXIT_CONFLICT, EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.files import rel_in
from chantier.store import READ_ONLY, FolderStore, PlanStore, SurfaceStore
from chantier.store import folder as folder_module
from chantier.store.base import LOCAL_FILES, PUBLISHES, REFUSES_WITHOUT_PUBLISHER

ARTIFACT_ROWS = [
    ("3-ready/x/work/artifacts-1/a.txt", False),
    ("3-ready/x/work/debugger/artifacts-99/deep/a.bin", False),
    ("4-batch/x/work/a/b/artifacts-7/x", False),
    ("3-ready/x/work/artifacts-1/", False),
    ("3-ready/x/work/artifacts-1", True),
    ("3-ready/x/work/artifacts.md", True),
    ("3-ready/x/evidence/artifacts-1/a.txt", True),
    ("3-ready/x/artifacts-1/a.txt", True),
]


BACKENDS = [
    "folder",
    "surface",
    pytest.param(
        "dedicated-branch",
        marks=pytest.mark.skip(reason="dedicated-branch backend: a later CR (planning-server-Q19)"),
    ),
]


@pytest.fixture(params=BACKENDS)
def store(request: pytest.FixtureRequest, tmp_path: Path) -> PlanStore:
    if request.param == "folder":
        return FolderStore(tmp_path / "project" / ".agents" / "changes")
    project = tmp_path / "surface" / "projects" / "demo"
    return SurfaceStore(project / "changes", project, tmp_path / "surface" / ".git")


def needs(store: PlanStore, feature: str) -> None:
    if feature not in store.features:
        pytest.skip(f"the backend does not declare {feature}")


def tree(root: Path) -> dict[str, bytes | None]:
    return {
        p.relative_to(root).as_posix(): (p.read_bytes() if p.is_file() else None)
        for p in sorted(root.rglob("*"))
    }


def test_building_a_store_creates_nothing(store: PlanStore) -> None:
    assert not store.root.exists()


def test_text_round_trip(store: PlanStore) -> None:
    store.write_text("a/x.md", "é ü 日本\nline\n")
    assert store.read_text("a/x.md") == "é ü 日本\nline\n"
    raw = (store.root / "a" / "x.md").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert raw == "é ü 日本\nline\n".encode()
    assert store.exists("a/x.md")
    assert not store.exists("a/none.md")
    store.write_text("a/y.md", "")
    assert store.listdir("a") == ["x.md", "y.md"]
    assert store.listdir(".") == ["a"]


def test_json_and_bytes(store: PlanStore) -> None:
    store.write_json("r/x.json", {"k": "é", "n": [1]})
    assert store.read_text("r/x.json") == '{\n  "k": "\\u00e9",\n  "n": [\n    1\n  ]\n}\n'
    store.write_json("r/y.json", {"k": "é"}, ensure_ascii=False)
    assert '"é"' in store.read_text("r/y.json")
    data = b"\xef\xbb\xbfone\r\ntwo\r\n"
    store.write_bytes("r/z.md", data)
    assert (store.root / "r" / "z.md").read_bytes() == data


def test_move_remove_and_make_folder(store: PlanStore) -> None:
    store.write_bytes("2-backlog/P3/cr/01-intent.md", b"a\r\nb")
    store.write_text("2-backlog/P3/cr/sub/n.md", "n\n")
    before = tree(store.root)
    store.move("2-backlog/P3/cr", "3-ready/cr")
    assert not store.exists("2-backlog/P3/cr")
    assert (store.root / "3-ready" / "cr" / "01-intent.md").read_bytes() == b"a\r\nb"
    assert tree(store.root / "3-ready")["cr/sub/n.md"] == before["2-backlog/P3/cr/sub/n.md"]
    store.write_text("2-backlog/P3/cr/other.md", "o")
    snapshot = tree(store.root)
    with pytest.raises(ChantierError, match="refusing to overwrite CR folder") as refused:
        store.move("2-backlog/P3/cr", "3-ready/cr")
    assert refused.value.code == EXIT_CONFLICT
    assert tree(store.root) == snapshot
    with pytest.raises(ChantierError, match="CR folder not found") as missing:
        store.move("2-backlog/P3/none", "3-ready/none")
    assert missing.value.code == EXIT_USAGE
    store.remove("3-ready/cr/sub/n.md")
    store.remove("3-ready/cr/sub")
    assert not store.exists("3-ready/cr/sub")
    store.make_folder("1-inbox/new", exist_ok=False)
    store.write_text("1-inbox/new/k.md", "k")
    with pytest.raises(FileExistsError):
        store.make_folder("1-inbox/new", exist_ok=False)
    store.make_folder("1-inbox/new", exist_ok=True)
    assert store.read_text("1-inbox/new/k.md") == "k"


def test_every_method_refuses_a_path_outside_the_root(store: PlanStore, tmp_path: Path) -> None:
    store.write_text("in.md", "x")
    outside = [
        "../x",
        "a/../../x",
        str(tmp_path / "abs.txt"),
        "/abs.txt",
        "C:abs.txt",
        "a\x00b",
    ]
    calls: list[Callable[[str], object]] = [
        store.read_text,
        store.exists,
        store.listdir,
        store.is_file,
        store.is_dir,
        store.stat,
        lambda rel: store.read_text(rel, "replace"),
        lambda rel: store.read_bytes(rel, 3),
        store.read_bytes,
        lambda rel: store.glob(rel, "*"),
        lambda rel: list(store.walk(rel)),
        lambda rel: store.write_text(rel, "x"),
        lambda rel: store.write_json(rel, {}),
        lambda rel: store.write_bytes(rel, b"x"),
        lambda rel: store.make_folder(rel, True),
        lambda rel: store.move(rel, "ok"),
        lambda rel: store.move("in.md", rel),
        store.remove,
        store.published,
        lambda rel: store.check_publish([rel]),
    ]
    for rel in outside:
        for call in calls:
            with pytest.raises(ChantierError, match="must be inside the planning folder") as e:
                call(rel)
            assert e.value.code == EXIT_USAGE
    assert sorted(p.name for p in tmp_path.rglob("*") if p.is_file()) == ["in.md"]


def link_folder(link: Path, target: Path) -> None:
    """A symlink to a folder, or on Windows without the privilege a junction (a reparse point)."""
    try:
        os.symlink(target, link, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            raise
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True
        )


def test_a_symlinked_folder_leaf_out_of_the_root_is_refused(
    store: PlanStore, tmp_path: Path
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("x", encoding="utf-8")
    store.write_text("a/in.md", "x")
    try:
        for link in (store.root / "leaf", store.root / "a" / "leaf"):
            link_folder(link, outside)
    except (OSError, NotImplementedError, subprocess.CalledProcessError):
        pytest.skip("this OS does not let the test make a link; the escape is not checked")
    calls: list[Callable[[str], object]] = [
        store.exists,
        store.is_dir,
        store.is_file,
        store.listdir,
        store.stat,
        store.read_text,
        lambda rel: store.glob(rel, "*"),
        lambda rel: list(store.walk(rel)),
    ]
    for rel in ("leaf", "a/leaf", "leaf/secret.md", "a/leaf/secret.md"):
        for call in calls:
            with pytest.raises(ChantierError, match="must be inside the planning folder"):
                call(rel)
    assert store.read_text("a/in.md") == "x"


def test_a_reading_pass_checks_again_in_the_next_pass(store: PlanStore, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    store.write_text("a/in.md", "x")
    with store.reading():
        assert store.listdir("a") == ["in.md"]
        with store.reading():
            assert store.is_dir("a")
    (store.root / "a" / "in.md").unlink()
    (store.root / "a").rmdir()
    try:
        link_folder(store.root / "a", outside)
    except (OSError, NotImplementedError, subprocess.CalledProcessError):
        pytest.skip("this OS does not let the test make a link; the escape is not checked")
    with pytest.raises(ChantierError, match="must be inside the planning folder"):
        store.listdir("a")


def test_reads(store: PlanStore) -> None:
    store.write_bytes("r/bad.md", b"ok \xff end")
    with pytest.raises(UnicodeDecodeError):
        store.read_text("r/bad.md")
    assert store.read_text("r/bad.md", "replace") == "ok \ufffd end"
    raw = b"\xef\xbb\xbfone\r\ntwo\r\n"
    store.write_bytes("r/bom.md", raw)
    assert store.read_text("r/bom.md") == "one\ntwo\n"  # universal newlines, as today
    assert store.read_bytes("r/bom.md") == raw
    assert store.read_bytes("r/bom.md", 5) == raw[:5]
    assert store.read_bytes("r/bom.md", 999) == raw
    assert store.is_file("r/bom.md") and not store.is_dir("r/bom.md")
    assert store.is_dir("r") and not store.is_file("r") and store.is_dir(".")
    assert not store.is_file("r/none") and not store.is_dir("r/none")
    for name in ("b-2.json", "a-1.json", "c.md"):
        store.write_text(f"g/{name}", "x")
    store.write_text("g/sub/a-3.json", "x")
    assert store.glob("g", "*.json") == ["a-1.json", "b-2.json"]
    assert store.glob("none", "*") == []
    for call in (store.read_text, store.read_bytes):
        with pytest.raises(FileNotFoundError):
            call("r/none.md")


def test_stat_and_no_cache(store: PlanStore) -> None:
    store.write_text("s/f.md", "abc")
    size, first = store.stat("s/f.md") or (0, 0)
    assert size == len("abc")
    assert store.read_text("s/f.md") == "abc"
    store.write_text("s/f.md", "abcdef")
    os.utime(store.root / "s" / "f.md", ns=(first + 10**9, first + 10**9))
    assert store.read_text("s/f.md") == "abcdef"
    assert store.read_bytes("s/f.md") == b"abcdef"
    new = store.stat("s/f.md")
    assert new is not None and new[0] == len("abcdef") and new[1] > first
    assert store.stat("s/none") is None


def test_walk(store: PlanStore) -> None:
    for rel in ("w/a.md", "w/x/b.md", "w/x/y/c.md", "w/skip/d.md"):
        store.write_text(rel, "x")
    seen = {}
    for folder, dirs, files in store.walk("w"):
        if folder == "w":
            assert "skip" in dirs
            dirs.remove("skip")
        seen[folder] = (sorted(dirs), sorted(files))
    assert seen == {"w": (["x"], ["a.md"]), "w/x": (["y"], ["b.md"]), "w/x/y": ([], ["c.md"])}
    assert list(store.walk("w/none")) == []
    assert next(f for f, _, _ in store.walk(".")) == "."


def test_reads_are_never_refused_without_a_writer(store: PlanStore) -> None:
    store.root.mkdir(parents=True)
    (store.root / "p.md").write_text("x")
    assert store.read_text("p.md") == "x"
    assert store.is_file("p.md") and store.glob(".", "*.md") == ["p.md"]


def test_rel_in(tmp_path: Path) -> None:
    assert rel_in(tmp_path, tmp_path / "a" / "b.md") == "a/b.md"
    assert rel_in(tmp_path, tmp_path) == "."
    with pytest.raises(ChantierError, match="must be inside the planning folder") as e:
        rel_in(tmp_path / "root", tmp_path / "elsewhere")
    assert e.value.code == EXIT_USAGE


def test_write_config_and_config_path(store: PlanStore) -> None:
    if PUBLISHES not in store.features:
        assert store.config_path is None
        with pytest.raises(ChantierError) as refused:
            store.write_config(b"x: 1\n")
        assert str(refused.value) == READ_ONLY
        assert refused.value.code == EXIT_PRECONDITION
        assert not store.root.exists()
        return
    assert isinstance(store, SurfaceStore)
    project = store.project
    assert store.config_path == project / "chantier.yaml"
    store.write_config(b"a: 1\r\n")
    assert (project / "chantier.yaml").read_bytes() == b"a: 1\r\n"
    (project / "chantier.yaml").unlink()
    (project / "chantier.yml").write_bytes(b"old\n")
    assert store.config_path == project / "chantier.yml"
    store.write_config(b"b: 2\n")
    assert (project / "chantier.yml").read_bytes() == b"b: 2\n"
    assert not (project / "chantier.yaml").exists()


def test_lock_is_exclusive(store: PlanStore, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(folder_module, "LOCK_WAIT_S", 0.2)
    held, release, outcome = threading.Event(), threading.Event(), []

    def holder() -> None:
        with store.lock():
            held.set()
            release.wait(5)

    def waiter() -> None:
        try:
            with store.lock():
                outcome.append("got it")
        except ChantierError as e:
            outcome.append(str(e))

    first = threading.Thread(target=holder)
    first.start()
    assert held.wait(5)
    second = threading.Thread(target=waiter)
    second.start()
    second.join(5)
    release.set()
    first.join(5)
    assert outcome == ["CR lifecycle is locked for over 30 s"]
    with store.lock():
        assert (store.root / ".lifecycle.lock").is_file()


def test_published_agrees_with_the_ignored_files(store: PlanStore) -> None:
    for rel in ("seat.json", "4-batch/batch.json", "work/gates/x.log", "3-ready/x/work/gates/a.md"):
        assert not store.published(rel), rel
    for rel in ("3-ready/x/01-intent.md", "5-archives/batches/batch-01.json", "x/batch.json"):
        assert store.published(rel), rel
    for rel, published in ARTIFACT_ROWS:
        assert store.published(rel) is published, rel


def test_check_publish_returns(store: PlanStore) -> None:
    if isinstance(store, SurfaceStore):
        live_writer(store.git_dir)
    store.check_publish(["3-ready/x/01-intent.md", "4-batch/batch.json"])
    store.check_publish([], config=True, command="file")
    store.check_publish(["3-ready/x/01-intent.md"], command="order merged")
    assert not store.root.exists()


def test_refuses_without_publisher(store: PlanStore) -> None:
    needs(store, REFUSES_WITHOUT_PUBLISHER)
    assert isinstance(store, SurfaceStore)
    with pytest.raises(ChantierError) as refused:
        store.check_publish(["3-ready/x/01-intent.md"], command="file")
    assert refused.value.code == EXIT_PRECONDITION
    assert "file: the surface's writer is not running" in str(refused.value)
    with pytest.raises(ChantierError) as config:
        store.check_publish([], config=True, command="board config")
    assert config.value.code == EXIT_PRECONDITION
    store.check_publish(["4-batch/batch.json"])  # a local file: no publisher needed
    assert not store.root.exists()
    live_writer(store.git_dir)
    store.check_publish(["3-ready/x/01-intent.md"], command="file")
    store.check_publish([], config=True, command="board config")


def test_local_files_are_declared(store: PlanStore) -> None:
    needs(store, LOCAL_FILES)
    store.ensure_gitignore()
    store.root.mkdir(parents=True, exist_ok=True)
    store.ensure_gitignore()
    assert "seat.json" in store.read_text(".gitignore")


@pytest.mark.parametrize(
    ("rel", "published"),
    [
        *ARTIFACT_ROWS,
        ("seat.json", False),
        ("4-batch/batch.json", False),
        ("3-ready/x/work/gates/a.md", False),
        ("3-ready/x/work/scratch/a", False),
        ("3-ready/x/01-intent.md", True),
    ],
)
def test_published_agrees_with_git_on_the_shipped_gitignore(
    tmp_path: Path, rel: str, published: bool
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "changes").mkdir()
    store = FolderStore(tmp_path / "changes")
    store.ensure_gitignore()
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", f"changes/{rel}"], cwd=tmp_path, check=False
    ).returncode
    assert (ignored != 0) is published is store.published(rel)
