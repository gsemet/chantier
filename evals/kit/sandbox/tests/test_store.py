import json

from shelf import store


def test_a_missing_file_is_an_empty_shelf(shelf_data):
    assert not shelf_data.exists()
    assert store.load() == []


def test_add_numbers_items_from_one_and_defaults_the_status():
    first = store.add("A book", "https://example.com")
    second = store.add("Another")
    assert (first["id"], second["id"]) == (1, 2)
    assert first["status"] == "to-read"
    assert len(first["added"]) == 10 and first["added"][4] == "-"


def test_items_survive_a_reload_and_the_save_leaves_no_temporary_file(shelf_data):
    store.add("Kept")
    assert json.loads(shelf_data.read_text(encoding="utf-8"))[0]["title"] == "Kept"
    assert [p.name for p in shelf_data.parent.iterdir()] == ["shelf.json"]


def test_set_status_and_unknown_item():
    item = store.add("Book")
    assert store.set_status(item["id"], "done")["status"] == "done"
    assert store.get(item["id"])["status"] == "done"
    assert store.set_status(99, "done") is None
    assert store.get(99) is None


def test_the_data_file_defaults_to_shelf_json_here(monkeypatch, tmp_path):
    monkeypatch.delenv("SHELF_DATA")
    monkeypatch.chdir(tmp_path)
    store.add("Local")
    assert (tmp_path / "shelf.json").exists()
