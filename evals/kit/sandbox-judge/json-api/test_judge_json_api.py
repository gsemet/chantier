"""Hidden judge tests for the CR json-api. Never pushed to the sandbox."""
import json
import re
from html.parser import HTMLParser


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.hrefs.append(dict(attrs).get("href"))


def add(client, title, url=""):
    assert client.post("/items", {"title": title, "url": url}).status == 303


def test_an_empty_shelf_is_an_empty_array(client):
    response = client.get("/api/items")
    assert response.status == 200
    assert response.headers["content-type"].startswith("application/json")
    assert json.loads(response.text) == []


def test_the_items_come_in_id_order_with_their_fields(client):
    add(client, "Judge api one", "https://example.com/one")
    add(client, "Judge api two")
    assert client.post("/items/2/status", {"status": "reading"}).status == 303
    items = json.loads(client.get("/api/items").text)
    assert [i["id"] for i in items] == [1, 2]
    assert all(isinstance(i["id"], int) for i in items)
    assert [i["title"] for i in items] == ["Judge api one", "Judge api two"]
    assert items[0]["url"] == "https://example.com/one"
    assert items[1]["url"] is None
    assert [i["status"] for i in items] == ["to-read", "reading"]
    assert all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", i["added"]) for i in items)


def test_a_title_comes_back_raw(client):
    add(client, "<b>&")
    assert json.loads(client.get("/api/items").text)[0]["title"] == "<b>&"
    assert json.loads(client.get("/api/items/1").text)["title"] == "<b>&"


def test_one_item_and_an_unknown_one(client):
    add(client, "Judge api one")
    response = client.get("/api/items/1")
    assert response.status == 200
    assert response.headers["content-type"].startswith("application/json")
    assert json.loads(response.text)["title"] == "Judge api one"
    missing = client.get("/api/items/9")
    assert missing.status == 404
    assert json.loads(missing.text) == {"error": "not found"}
    assert missing.headers["content-type"].startswith("application/json")


def test_other_methods_are_405(client):
    add(client, "Judge api one")
    assert client.post("/api/items", {}).status == 405
    assert client.post("/api/items/1", {}).status == 405


def test_the_list_page_links_to_the_api(client):
    links = Links()
    links.feed(client.get("/").text)
    assert "/api/items" in links.hrefs
